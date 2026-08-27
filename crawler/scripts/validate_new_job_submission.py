from __future__ import annotations
import hashlib, json
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
NJ=BASE/'data/gold/new_jobs'

def main():
    candidates=json.loads((NJ/'new_job_candidates.json').read_text(encoding='utf-8'))
    ledger=json.loads((NJ/'human_review_ledger_v1.0.json').read_text(encoding='utf-8'))
    published=json.loads((NJ/'published_job_definitions_v1.0.json').read_text(encoding='utf-8'))
    versions=[json.loads(x) for x in (NJ/'definition_version_history.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    by_candidate={x['candidate_id']:x for x in candidates['candidates']}
    review_by={x['candidate_id']:x for x in ledger['reviews']}
    required_fields=['name','responsibilities','required_skills','preferred_skills','typical_industry_scenarios']
    definitions=published['definitions']
    checks={
      'all_five_candidates_reviewed':set(by_candidate)==set(review_by),
      'at_least_one_submission_definition':len(definitions)>=1,
      'five_fields_complete':all(all(d.get(k) for k in required_fields) for d in definitions),
      'algorithm_type_not_overwritten':all(d['algorithm_candidate_type']==by_candidate[d['candidate_id']]['candidate_type'] for d in definitions),
      'submission_has_review_record':all(review_by.get(d['candidate_id'],{}).get('review_status')=='approved_for_submission_v1' for d in definitions),
      'evidence_counts_reconcile':all(d['evidence_summary']['unique_jd_count']==by_candidate[d['candidate_id']]['unique_jd_count'] and d['evidence_summary']['source_count']==by_candidate[d['candidate_id']]['source_count'] for d in definitions),
      'version_history_complete':all(any(v['definition_id']==d['definition_id'] and v['version']==d['version'] for v in versions) for d in definitions),
      'limitations_disclosed':all(d.get('limitations') for d in definitions),
    }
    payload=json.dumps(published,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    result={'schema_version':'1.0.0','passed':all(checks.values()),'checks':checks,'counts':{'algorithm_candidates':len(by_candidate),'reviewed_candidates':len(review_by),'published_submission_definitions':len(definitions)},'published_sha256':hashlib.sha256(payload).hexdigest()}
    out=BASE/'data/reports/new_job_submission_acceptance.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
