"""arXiv 学术前沿 v2：官方 Atom API 元数据、领域筛选和技能证据。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
from utils.skill_mapping import extract_skill_matches  # noqa: E402

API = "https://export.arxiv.org/api/query"
OUTPUT = BASE / "data/bronze/papers_trend.jsonl"
QUARANTINE = BASE / "data/quarantine/arxiv_irrelevant.jsonl"
RAW_ROOT = BASE / "data/bronze/papers/api"
ATOM = "http://www.w3.org/2005/Atom"
ARXIV = "http://arxiv.org/schemas/atom"
ALLOWED_CATEGORIES = {"cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.IR", "cs.DB", "cs.NI", "cs.RO"}
QUERY_TERMS = {
    "cs.AI": "artificial intelligence OR agent OR knowledge graph",
    "cs.LG": "machine learning OR deep learning OR federated learning",
    "cs.CL": "large language model OR natural language processing OR RAG",
    "cs.CV": "computer vision OR multimodal OR image generation",
    "cs.IR": "information retrieval OR recommender OR vector search",
    "cs.DB": "database OR data management OR vector database",
    "cs.NI": "network OR 5G OR internet of things OR edge computing",
    "cs.RO": "robotics OR autonomous system OR embodied intelligence",
}
DOMAIN_TERMS = re.compile(
    r"\b(artificial intelligence|machine learning|deep learning|large language model|llm|"
    r"natural language|computer vision|information retrieval|database|data management|"
    r"knowledge graph|neural network|transformer|agent|robot|robotics|recommender|"
    r"network protocol|wireless|5g|6g|internet of things|iot|edge computing|cloud computing|"
    r"federated learning|reinforcement learning|multimodal|diffusion|embedding|retrieval|rag)\b",
    re.IGNORECASE,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(path)


def legacy_ids() -> list[str]:
    path = BASE / "data/quarantine/arxiv_trend_legacy_20260802.jsonl"
    ids = []
    for row in load_jsonl(path):
        url = str(row.get("source_url") or row.get("abs_url") or "")
        match = re.search(r"/abs/([^/?#]+)", url)
        if match:
            ids.append(re.sub(r"v\d+$", "", match.group(1)))
    return list(dict.fromkeys(ids))


def evidence_sentence(text: str, start: int) -> str:
    left = max(text.rfind(". ", 0, start), text.rfind("? ", 0, start), text.rfind("! ", 0, start))
    right_values = [value for value in (text.find(". ", start), text.find("? ", start), text.find("! ", start)) if value >= 0]
    right = min(right_values) + 1 if right_values else min(len(text), start + 300)
    return text[left + 2:right].strip()[:500]


def skill_evidence(title: str, abstract: str) -> tuple[list[str], list[dict]]:
    evidence, skills, seen_skills = [], [], set()
    for field, text in (("title", title), ("abstract", abstract)):
        for match in extract_skill_matches(text):
            evidence.append({
                "skill": match.standard, "raw": match.raw, "source_field": field,
                "evidence_sentence": evidence_sentence(text, match.start),
                "method": "skill_ontology_alias_rule_v3",
            })
            key = match.standard.casefold()
            if key not in seen_skills:
                seen_skills.add(key)
                skills.append(match.standard)
    return skills, evidence


def parse_entry(entry: ET.Element, query_keyword: str, observed_at: str) -> dict:
    identity = clean(entry.findtext(f"{{{ATOM}}}id", "")).split("/abs/")[-1]
    version_match = re.search(r"v(\d+)$", identity)
    arxiv_id = re.sub(r"v\d+$", "", identity)
    title = clean(entry.findtext(f"{{{ATOM}}}title", ""))
    abstract = clean(entry.findtext(f"{{{ATOM}}}summary", ""))
    authors = [clean(node.findtext(f"{{{ATOM}}}name", "")) for node in entry.findall(f"{{{ATOM}}}author")]
    primary = entry.find(f"{{{ARXIV}}}primary_category")
    primary_category = primary.get("term", "") if primary is not None else ""
    categories = list(dict.fromkeys(node.get("term", "") for node in entry.findall(f"{{{ATOM}}}category") if node.get("term")))
    published = clean(entry.findtext(f"{{{ATOM}}}published", ""))
    updated = clean(entry.findtext(f"{{{ATOM}}}updated", ""))
    text = f"{title} {abstract}"
    keyword_hits = sorted({match.group(0).casefold() for match in DOMAIN_TERMS.finditer(text)})
    category_hits = sorted(ALLOWED_CATEGORIES.intersection(categories))
    score = min(1.0, (0.6 if primary_category in ALLOWED_CATEGORIES else 0.35 if category_hits else 0) + min(0.4, len(keyword_hits) * 0.1))
    reasons = []
    if category_hits:
        reasons.append("相关计算机分类:" + ",".join(category_hits))
    if keyword_hits:
        reasons.append("标题/摘要领域词:" + ",".join(keyword_hits[:8]))
    skills, evidence = skill_evidence(title, abstract)
    relationship_skills = [item["skill"] for item in evidence if item["source_field"] == "abstract"]
    return {
        "arxiv_id": arxiv_id, "version": int(version_match.group(1)) if version_match else 1,
        "title": title, "abstract": abstract, "authors": authors,
        "primary_category": primary_category, "categories": categories,
        "published_at": published, "updated_at": updated,
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}", "abs_url": f"https://arxiv.org/abs/{identity}",
        "query_keyword": query_keyword, "observed_at": observed_at,
        "relevance_score": round(score, 3), "relevance_reason": "; ".join(reasons),
        "inferred_skills": skills, "relationship_skills": relationship_skills, "skill_evidence": evidence,
    }


def fetch(params: dict, raw_path: Path, session: requests.Session) -> list[ET.Element]:
    response = session.get(API, params=params, timeout=60)
    response.raise_for_status()
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(response.content)
    root = ET.fromstring(response.content)
    return root.findall(f"{{{ATOM}}}entry")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=400)
    parser.add_argument("--per-category", type=int, default=30)
    parser.add_argument("--refresh-only", action="store_true")
    args = parser.parse_args()
    observed_at = now_iso()
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = RAW_ROOT / batch_id
    session = requests.Session()
    session.headers["User-Agent"] = "TalentGraph-Evolution-Research contact: research@example.invalid"
    records: dict[str, dict] = {}

    ids = legacy_ids()
    for index in range(0, len(ids), 50):
        chunk = ids[index:index + 50]
        try:
            entries = fetch({"id_list": ",".join(chunk), "max_results": len(chunk)}, raw_dir / f"legacy_{index//50+1:02d}.xml", session)
            for entry in entries:
                row = parse_entry(entry, "legacy_id_refresh", observed_at)
                current = records.get(row["arxiv_id"])
                if current is None or row["version"] > current["version"]:
                    records[row["arxiv_id"]] = row
            print(f"旧 ID 元数据 {min(index+50, len(ids))}/{len(ids)}")
        except requests.RequestException as exc:
            print(f"旧 ID 批次失败: {exc}")
        time.sleep(3)

    if not args.refresh_only:
        for category, terms in QUERY_TERMS.items():
            query = f"cat:{category} AND ({' OR '.join('all:'+part.strip() for part in terms.split(' OR '))})"
            try:
                entries = fetch({"search_query": query, "start": 0, "max_results": args.per_category,
                                 "sortBy": "submittedDate", "sortOrder": "descending"},
                                raw_dir / f"search_{category.replace('.', '_')}.xml", session)
                for entry in entries:
                    row = parse_entry(entry, f"{category}:{terms}", observed_at)
                    current = records.get(row["arxiv_id"])
                    if current is None or row["version"] > current["version"]:
                        records[row["arxiv_id"]] = row
                print(f"{category}: {len(entries)}，累计 {len(records)}")
            except requests.RequestException as exc:
                print(f"{category} 查询失败: {exc}")
            time.sleep(3)

    formal, isolated = [], []
    for row in records.values():
        relevant_category = row["primary_category"] in ALLOWED_CATEGORIES
        keyword_sufficient = bool(DOMAIN_TERMS.search(f"{row['title']} {row['abstract']}"))
        (formal if relevant_category and keyword_sufficient else isolated).append(row)
    formal.sort(key=lambda row: (row["published_at"], row["arxiv_id"]), reverse=True)
    isolated.sort(key=lambda row: row["arxiv_id"])
    write_jsonl(OUTPUT, formal)
    write_jsonl(QUARANTINE, isolated)
    manifest = {
        "batch_id": batch_id, "observed_at": observed_at, "legacy_ids": len(ids),
        "api_records": len(records), "formal_records": len(formal), "isolated_records": len(isolated),
        "raw_sha256": hashlib.sha256("".join(sorted(records)).encode()).hexdigest(),
    }
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
