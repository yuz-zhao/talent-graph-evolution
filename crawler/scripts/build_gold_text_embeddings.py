"""Build semantic embeddings for the 30 gold resumes and 100 gold JDs (offline cache).

The BGE-small-zh-v1.5 weights come from an external corpus, so the resulting
similarity is the one transfer signal that does not memorise any specific resume.
Everything is embedded once here and cached to JSON; the evaluator and trainer
then read the cache and never touch the model again.

Output: crawler/data/reference/gold_text_embeddings.json
  { "model": ..., "dimension": ..., "resumes": {id: vec}, "jds": {id: vec} }
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESUMES = ROOT / "crawler" / "data" / "gold" / "human" / "v1.1" / "gold_resume_v1.1.jsonl"
JDS = ROOT / "crawler" / "data" / "gold" / "human" / "v1.1" / "gold_jd_v1.1.jsonl"
OUT = ROOT / "crawler" / "data" / "reference" / "gold_text_embeddings.json"
MODEL = "BAAI/bge-small-zh-v1.5"


def read_jsonl(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def resume_text(r: dict) -> str:
    """The resume's semantic identity: evidence-rich prose first, then sparse labels."""
    skills = [s if isinstance(s, str) else (s.get("name") or s.get("standard_name") or "") for s in (r.get("skills") or [])]
    parts = [
        r.get("target_job") or "",
        "专业:" + (r.get("major") or ""),
        "学历:" + (r.get("highest_education") or ""),
        "技能:" + "、".join(skills),
        r.get("skill_evidence_text") or "",
        r.get("projects_text") or "",
        r.get("project_evidence_text") or "",
    ]
    return "\n".join(p for p in parts if p).strip()


def jd_text(j: dict) -> str:
    """The JD's semantic identity: full prose first, then the structured skill lists."""
    parts = [
        j.get("standard_job_name") or "",
        j.get("job_title") or "",
        "必备技能:" + "、".join(j.get("required_skills") or []),
        "加分技能:" + "、".join(j.get("bonus_skills") or []),
        j.get("original_text") or "",
    ]
    return "\n".join(p for p in parts if p).strip()


def main() -> int:
    from fastembed import TextEmbedding

    resumes = read_jsonl(RESUMES)
    jds = read_jsonl(JDS)
    resume_texts = [resume_text(r) for r in resumes]
    jd_texts = [jd_text(j) for j in jds]

    model = TextEmbedding(model_name=MODEL)

    all_ids = [r["resume_id"] for r in resumes] + [j["sample_id"] for j in jds]
    all_texts = resume_texts + jd_texts
    all_vecs = [v.tolist() for v in model.embed(all_texts, batch_size=16)]

    dimension = len(all_vecs[0])
    n_resume = len(resumes)
    result = {
        "model": MODEL,
        "dimension": dimension,
        "resumes": {all_ids[i]: all_vecs[i] for i in range(n_resume)},
        "jds": {all_ids[n_resume + i]: all_vecs[n_resume + i] for i in range(len(jds))},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "ok": True, "model": MODEL, "dimension": dimension,
        "resumes": n_resume, "jds": len(jds), "out": str(OUT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
