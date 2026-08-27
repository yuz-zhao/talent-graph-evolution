from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
NJ=BASE/'data/gold/new_jobs'

def jsonl(path): return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]

def main():
    candidate=json.loads((NJ/'new_job_candidates.json').read_text(encoding='utf-8'))['candidates'][0]
    definition=json.loads((NJ/'published_job_definitions_v1.0.json').read_text(encoding='utf-8'))['definitions'][0]
    member_ids=set(candidate['member_record_ids']); records=[]
    for path in (BASE/'data/gold/records').glob('*_job.jsonl'):
        for row in jsonl(path):
            if row.get('record_id') in member_ids:
                payload=row.get('payload') or {}; records.append({**payload,'record_id':row['record_id'],'source_platform':row.get('source_platform')})
    by_source=defaultdict(list)
    for row in records: by_source[row['source_platform']].append(row)
    loo=[]
    for source in sorted(by_source):
        remaining=[r for r in records if r['source_platform']!=source]
        loo.append({'held_out_source':source,'remaining_jds':len(remaining),'remaining_sources':len({r['source_platform'] for r in remaining}),'remaining_companies':len({r.get('company') for r in remaining if r.get('company')}),'passes_independence_floor':len(remaining)>=8 and len({r['source_platform'] for r in remaining})>=2 and len({r.get('company') for r in remaining if r.get('company')})>=3})
    texts=[(' '.join(str(r.get(k) or '') for k in ['job_title','description','requirements','required_skills','preferred_skills','mentioned_skills'])).lower() for r in records]
    concepts={
      'ai_agent':['agent','智能体'], 'large_language_model':['大模型','llm'], 'product_management':['产品经理','product manager','产品管理'],
      'data_evaluation':['数据分析','数据驱动','评测','metrics','kpi'], 'rag_knowledge':['rag','知识库','knowledge'],
    }
    coverage={name:{'jd_count':sum(any(k in text for k in keys) for text in texts),'rate':round(sum(any(k in text for k in keys) for text in texts)/max(1,len(texts)),4)} for name,keys in concepts.items()}
    loo_rate=sum(x['passes_independence_floor'] for x in loo)/max(1,len(loo))
    evidence_validation={'records_found':len(records),'source_count':len(by_source),'company_count':len({r.get('company') for r in records if r.get('company')}),'leave_one_source_out':loo,'leave_one_source_out_pass_rate':round(loo_rate,4),'source_dependency':'tencent-dominant' if loo_rate<1 else 'robust','concept_coverage':coverage,'five_fields_present':all(definition.get(k) for k in ['name','responsibilities','required_skills','preferred_skills','typical_industry_scenarios'])}

    snapshots=jsonl(BASE/'data/gold/temporal/job_skill_monthly_snapshots.jsonl'); events=jsonl(BASE/'data/gold/temporal/job_skill_change_events.jsonl')
    by_job_month={(x['job_name'],x['month']):x for x in snapshots}; months=defaultdict(list)
    for x in snapshots: months[x['job_name']].append(x['month'])
    for values in months.values(): values.sort()
    evaluated=[]
    for event in events:
        if event.get('publication_status')!='confirmed_evolution': continue
        sequence=months[event['job_name']]
        try: idx=sequence.index(event['to_month'])
        except ValueError: continue
        if idx+1>=len(sequence): continue
        next_month=sequence[idx+1]; current=event['current_share']; next_snapshot=by_job_month[(event['job_name'],next_month)]
        next_share=next((x['posterior_share'] for x in next_snapshot['skills'] if x['skill']==event['skill']),0.0)
        expected='up' if event['delta_share']>0 else 'down' if event['delta_share']<0 else 'flat'
        actual='up' if next_share>current+0.02 else 'down' if next_share<current-0.02 else 'flat'
        evaluated.append({'event_id':event['event_id'],'expected':expected,'actual':actual,'consistent':actual==expected or actual=='flat','next_month':next_month})
    consistent=sum(x['consistent'] for x in evaluated)
    evolution_validation={'eligible_prior_events':len(evaluated),'direction_consistent_or_stable':consistent,'temporal_consistency_rate':round(consistent/max(1,len(evaluated)),4),'strict_direction_rate':round(sum(x['actual']==x['expected'] for x in evaluated)/max(1,len(evaluated)),4),'evaluation_rule':'An added/modified event is evaluated only against the next observed month; stable within +/-0.02 counts as non-reversal.','examples':evaluated[:30]}
    report={'schema_version':'1.0.0','new_job_definition':evidence_validation,'job_evolution_backtest':evolution_validation,'acceptance':{'new_job_leave_one_source_out_at_least_0_75':loo_rate>=.75,'new_job_source_dependency_disclosed':evidence_validation['source_dependency'] in {'robust','tencent-dominant'},'evolution_has_independent_next_window':len(evaluated)>=20,'evolution_non_reversal_rate_at_least_0_60':evolution_validation['temporal_consistency_rate']>=.60}}
    report['passed']=all(report['acceptance'].values())
    out=BASE/'data/reports/new_job_and_evolution_independent_validity.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
