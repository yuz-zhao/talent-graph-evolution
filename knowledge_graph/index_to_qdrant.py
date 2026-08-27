"""Build a real multilingual embedding index from formal evidence records."""
from __future__ import annotations
import argparse, hashlib, json, os, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "crawler/data/gold/evidence/skill_evidence.jsonl"
REPORT = ROOT / "crawler/data/reports/qdrant_index_report.json"
COLLECTION = os.getenv("QDRANT_COLLECTION", "talentgraph_evidence_v2")
QDRANT = os.getenv("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
VERSION = "qdrant_evidence_index_v2"

def request(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(QDRANT + path, data=data, method=method, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=120) as response: return json.loads(response.read().decode())

def load_records(limit=0):
    rows=[]
    for line in EVIDENCE.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        row=json.loads(line)
        if row.get("is_independent_representative") and row.get("evidence_text") and str(row.get("source_url","")).startswith(("http://","https://")):
            rows.append(row)
            if limit and len(rows)>=limit: break
    return rows

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--limit",type=int,default=0); parser.add_argument("--batch-size",type=int,default=64); args=parser.parse_args()
    try: from fastembed import TextEmbedding
    except ImportError: raise SystemExit("fastembed is required: pip install fastembed")
    rows=load_records(args.limit); model=TextEmbedding(model_name=MODEL)
    first=list(model.embed([rows[0]["skill_name"]+": "+rows[0]["evidence_text"]]))[0]; dimension=len(first)
    try: request("DELETE", f"/collections/{COLLECTION}")
    except Exception: pass
    request("PUT", f"/collections/{COLLECTION}", {"vectors":{"size":dimension,"distance":"Cosine"}})
    indexed=0
    for start in range(0,len(rows),args.batch_size):
        batch=rows[start:start+args.batch_size]
        texts=[x["skill_name"]+": "+x["evidence_text"] for x in batch]
        vectors=list(model.embed(texts))
        points=[]
        for row,vector,text in zip(batch,vectors,texts):
            numeric_id=int(hashlib.sha256(row["evidence_id"].encode()).hexdigest()[:15],16)
            payload={k:row.get(k) for k in ("evidence_id","skill_id","skill_name","source_group","source_type","source_platform","source_url","evidence_text","evidence_score","observed_at")}
            payload.update({"embedding_model":MODEL,"index_version":VERSION,"text_hash":hashlib.sha256(text.encode()).hexdigest()})
            points.append({"id":numeric_id,"vector":[float(v) for v in vector],"payload":payload})
        request("PUT",f"/collections/{COLLECTION}/points?wait=true",{"points":points}); indexed+=len(points); print(f"indexed {indexed}/{len(rows)}")
    info=request("GET",f"/collections/{COLLECTION}").get("result",{})
    report={"algorithm_version":VERSION,"collection":COLLECTION,"embedding_model":MODEL,"vector_dimension":dimension,"eligible_evidence":len(rows),"indexed_points":info.get("points_count",indexed),"status":info.get("status"),"fake_embedding":False,"passed":info.get("status") in {"green","yellow"} and int(info.get("points_count") or indexed)==len(rows)}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(report,ensure_ascii=False,indent=2)); return 0 if report["passed"] else 1
if __name__=="__main__": raise SystemExit(main())
