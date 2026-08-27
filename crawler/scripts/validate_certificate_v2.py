"""Quality gate for issuer-verified certification data."""
from __future__ import annotations
import csv, json
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/"data/silver/learning/certificate_data.csv"
REPORT=BASE/"data/reports/certificate_v2_quality_report.json"

def validate():
    with DATA.open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
    relation_count=0; evidence_ok=True
    for row in rows:
        skills=json.loads(row.get("related_skills") or "[]"); evidence=json.loads(row.get("skill_evidence") or "[]")
        relation_count += len(skills)
        proven={item.get("skill") for item in evidence if item.get("evidence") and item.get("source")=="official_outline_or_capability_page"}
        evidence_ok &= set(skills).issubset(proven)
    total=len(rows); verified=sum(r.get("url_status")=="verified_200" for r in rows)
    checks={
      "no_example_com":all("example.com" not in r.get("official_url","") for r in rows),
      "official_url_rate_gte_95_percent":verified/max(1,total)>=.95,
      "issuer_domains_only":all(url_domain_ok(r) for r in rows),
      "all_skill_relations_have_official_evidence":evidence_ok,
      "stable_ids_present":all(r.get("certificate_id") for r in rows),
      "status_present":all(r.get("status") for r in rows),
      "retired_history_preserved":any(r.get("status")=="retired" for r in rows),
      "no_template_rows":all(r.get("source_type")!="template_generated" for r in rows),
    }
    report={"formal_certificates":total,"issuers":sorted({r.get('issuer') for r in rows}),"verified_url_rate":round(verified/max(1,total),4),"skill_relations":relation_count,"checks":checks,"passed":all(checks.values()),"blocked_but_not_fabricated":[{"issuer":"国家软考","reason":"官网主动关闭自动采集连接，未伪造入库"},{"issuer":"华为","reason":"官网HTTP 403禁止自动采集，未伪造入库"}]}
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2)); return report

def url_domain_ok(row):
    from urllib.parse import urlparse
    host=urlparse(row.get("official_url","")).netloc.casefold()
    allowed={"AWS":"amazon.com","Microsoft":"microsoft.com","阿里云":"aliyun.com","腾讯云":"tencent.com"}
    return allowed.get(row.get("issuer",""),"") in host

if __name__=="__main__": raise SystemExit(0 if validate()["passed"] else 1)
