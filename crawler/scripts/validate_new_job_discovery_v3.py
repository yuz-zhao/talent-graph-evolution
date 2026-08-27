from __future__ import annotations
import json
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
RESULT=BASE/'data/gold/new_jobs/new_job_candidates.json'


def main():
 data=json.loads(RESULT.read_text(encoding='utf-8')); candidates=data.get('candidates',[]); total=data.get('input_unique_jds',0)
 mature={'Java开发工程师','前端工程师','大数据开发工程师','嵌入式开发工程师','人工智能算法工程师'}
 checks={
  'input_is_jd_level':total>0,
  'unique_counts_reproducible':all(c['unique_jd_count']==len(set(c['member_record_ids'])) for c in candidates),
  'candidate_count_never_exceeds_total':all(c['unique_jd_count']<=total for c in candidates),
  'scores_are_normalized':all(0<=c['score']<=1 for c in candidates),
  'clusters_have_evaluation':bool(data.get('clustering_evaluations')) and all('silhouette' in x and 'davies_bouldin' in x for x in data['clustering_evaluations']),
  'results_are_versioned':all(c.get('algorithm_version') and c.get('data_batch_ids') for c in candidates),
  'no_mature_job_directly_relabelled_new':all(not(c['name'] in mature and c['candidate_type']=='formal_candidate') for c in candidates),
  'formal_candidates_meet_independence':all(c['source_count']>=2 and c['company_count']>=3 for c in candidates if c['candidate_type']=='formal_candidate'),
  'evidence_and_time_are_traceable':all('representative_evidence' in c and 'observation_windows' in c for c in candidates),
 }
 report={'checks':checks,'counts':{'input_unique_jds':total,'published_candidates':len(candidates),'formal_candidates':sum(c['candidate_type']=='formal_candidate' for c in candidates)},'passed':all(checks.values())}
 (BASE/'data/reports/new_job_discovery_acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
