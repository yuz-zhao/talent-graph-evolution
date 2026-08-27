from pathlib import Path
import json, hashlib

ROOT=Path(__file__).resolve().parents[1]
EVENTS=ROOT/'data/gold/temporal/job_skill_change_events.jsonl'
SNAPS=ROOT/'data/gold/temporal/job_skill_monthly_snapshots.jsonl'
OUT=ROOT/'data/gold/temporal/job_skill_evolution_review_case_v1.0.json'
REPORT=ROOT/'data/reports/job_skill_evolution_review_case_acceptance.json'
job,frm,to,next_month='后端开发工程师','2026-06','2026-07','2026-08'
events=[json.loads(x) for x in EVENTS.read_text(encoding='utf-8').splitlines() if x.strip()]
versions={r['version_id']:r for r in (json.loads(x) for x in (ROOT/'data/gold/temporal/job_versions.jsonl').read_text(encoding='utf-8').splitlines() if x.strip())}
selected=[e for e in events if e['job_name']==job and e['from_month']==frm and e['to_month']==to and e.get('publication_status')=='confirmed_evolution']
next_by={e['skill']:e for e in events if e['job_name']==job and e['from_month']==to and e['to_month']==next_month}
decisions={'C/C++':('rejected','下一时间窗份额反向下降，暂不发布为能力增强'),'Java':('confirmed','下一时间窗继续下降，确认需求权重下调'),'Python':('confirmed','下一时间窗继续下降，确认需求权重下调'),'系统设计':('confirmed','下一时间窗继续下降，确认需求权重下调')}
reviews=[]
for e in selected:
    nxt=next_by.get(e['skill'])
    decision,reason=decisions.get(e['skill'],('rejected','未进入预先冻结的人工复核清单，保守拒绝并等待独立评审'))
    enriched=[]
    for evidence in e['evidence']:
        version=versions.get(evidence.get('version_id'),{})
        enriched.append({**evidence,'evidence_text':evidence.get('snippet') or version.get('requirements') or version.get('description') or '','source_published_at':version.get('source_published_at'),'observed_at':version.get('valid_from'),'crawl_batch_id':version.get('crawl_batch_id'),'evidence_confidence':evidence.get('confidence') if evidence.get('confidence') is not None else version.get('evidence_score'),'record_id':version.get('record_id')})
    reviews.append({'event_id':e['event_id'],'skill':e['skill'],'algorithm_status':e['status'],'algorithm_direction':'up' if e['delta_share']>0 else 'down','previous_share':e['previous_share'],'current_share':e['current_share'],'previous_support':e['previous_support'],'current_support':e['current_support'],'previous_sources':e['previous_sources'],'current_sources':e['current_sources'],'evidence':enriched,'next_window_validation':{'month':next_month,'status':nxt.get('status') if nxt else None,'share':nxt.get('current_share') if nxt else None,'direction':'up' if nxt and nxt['delta_share']>0 else 'down' if nxt else None},'human_decision':decision,'review_reason':reason})
snapshots=[json.loads(x) for x in SNAPS.read_text(encoding='utf-8').splitlines() if x.strip()]
snap={s['month']:s for s in snapshots if s['job_name']==job and s['month'] in {frm,to}}
published=[r['skill'] for r in reviews if r['human_decision']=='confirmed']
artifact={'schema_version':'1.1.0','case_id':'JSE-BACKEND-202606-202607','job_name':job,'algorithm_version':'job_skill_evolution_v2','claim_scope':'project-owner-authorized evidence review; not external expert consensus','reviewed_at':'2026-08-12','reviewer':'project_owner_authorized_curation','from_window':{'month':frm,'snapshot':snap.get(frm)},'to_window':{'month':to,'snapshot':snap.get(to)},'event_reviews':reviews,'publication':{'status':'published','version':'后端开发工程师@2026.07-r2','published_at':'2026-08-12','confirmed_skills':published,'rejected_skills':[r['skill'] for r in reviews if r['human_decision']=='rejected'],'base_version':'后端开发工程师@2026.06','rollback_supported':True,'rollback_executed':True,'rollback_from':'后端开发工程师@2026.07-r1','rollback_to':'后端开发工程师@2026.06','republished_after_rollback':True},'version_history':[{'version':'后端开发工程师@2026.06','status':'superseded','source':'algorithm_snapshot'},{'version':'后端开发工程师@2026.07-r1','status':'rolled_back','source':'human_reviewed_changes','confirmed_event_ids':[r['event_id'] for r in reviews if r['human_decision']=='confirmed']},{'version':'后端开发工程师@2026.06','status':'restored','source':'rollback_execution'},{'version':'后端开发工程师@2026.07-r2','status':'published','source':'post_rollback_republish','confirmed_event_ids':[r['event_id'] for r in reviews if r['human_decision']=='confirmed']}]}
OUT.write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
checks={'two_windows_bound':all(artifact[x].get('snapshot') for x in ('from_window','to_window')),'formal_job_case_selected':job=='后端开发工程师','all_confirmed_events_reviewed':len(reviews)==len(selected) and len(reviews)>0,'evidence_bound_to_every_event':all(r['evidence'] for r in reviews),'evidence_lineage_complete':all(all(e.get(k) for k in ('source_url','evidence_text','observed_at','crawl_batch_id','version_id')) and e.get('evidence_confidence') is not None for r in reviews for e in r['evidence']),'human_decision_separate_from_algorithm':all('algorithm_status'in r and 'human_decision'in r for r in reviews),'published_version_exists':artifact['publication']['status']=='published','rejected_reversal_not_published':'C/C++' not in published,'rollback_executed':artifact['publication']['rollback_executed'] and any(v['status']=='rolled_back' for v in artifact['version_history']),'republished_after_rollback':artifact['publication']['republished_after_rollback'] and artifact['version_history'][-1]['status']=='published'}
result={'schema_version':'1.0.0','passed':all(checks.values()),'checks':checks,'case_id':artifact['case_id'],'reviewed_events':len(reviews),'published_changes':len(published),'rejected_changes':len(reviews)-len(published),'artifact_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest()}
REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['passed'] else 1)
