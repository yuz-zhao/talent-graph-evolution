from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
FLOW=ROOT/'data/gold/new_jobs/definition_workflow_v1.0.json'
OUT=ROOT/'data/reports/new_job_workflow_acceptance.json'
data=json.loads(FLOW.read_text(encoding='utf-8'))
definitions=data.get('definitions',[])
checks={
  'workflow_artifact_exists':FLOW.exists(),
  'published_version_pointer_valid':all(any(v['version']==d.get('current_published_version') and v['status']=='published' for v in d.get('versions',[])) for d in definitions),
  'five_fields_complete_in_every_version':all(all(v.get(k) for k in ('name','responsibilities','required_skills','preferred_skills','typical_industry_scenarios')) for d in definitions for v in d.get('versions',[])),
  'algorithm_type_preserved':all(d.get('algorithm_candidate_type') and all(v.get('algorithm_candidate_type')==d.get('algorithm_candidate_type') for v in d.get('versions',[])) for d in definitions),
  'immutable_version_numbers_unique':all(len({v['version'] for v in d.get('versions',[])})==len(d.get('versions',[])) for d in definitions),
  'supported_state_machine_only':all(v.get('status') in {'draft','pending_review','approved','rejected','published'} for d in definitions for v in d.get('versions',[])),
}
result={'schema_version':'1.0.0','passed':all(checks.values()),'checks':checks,'definitions':len(definitions),'versions':sum(len(d.get('versions',[])) for d in definitions),'current_published_versions':{d['definition_id']:d.get('current_published_version') for d in definitions}}
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
raise SystemExit(0 if result['passed'] else 1)
