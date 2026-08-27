"""Validate ontology identity, hierarchy, aliases, lifecycle provenance and extraction rules."""
from __future__ import annotations
import json,sys
from pathlib import Path
from collections import Counter
BASE=Path(__file__).resolve().parents[1]; ONTO=BASE/'data/gold/reference/skill_ontology.json'; REPORT=BASE/'data/reports/skill_ontology_v2_quality_report.json'
sys.path.insert(0,str(BASE)); from utils.skill_mapping import extract_skill_matches

def has_cycle(data):
    for start in data:
        seen=set(); current=start
        while current and current in data:
            if current in seen:return True
            seen.add(current); current=data[current].get('parent_skill','')
    return False

def validate():
    data=json.loads(ONTO.read_text(encoding='utf-8')); ids=[x.get('skill_id') for x in data.values()]; risky={'es','to','bi','sc'}
    aliases=[a.casefold() for x in data.values() for a in x.get('aliases',[])]
    lifecycle_ok=all(x.get('lifecycle_evidence',{}).get('algorithm_version')=='lifecycle_evidence_v1' and x['lifecycle_evidence'].get('window_start') and x['lifecycle_evidence'].get('window_end') and len(x['lifecycle_evidence'].get('source_files',[]))==4 for x in data.values())
    adversarial={
      'ES TO SC are ordinary uppercase tokens':set(m.standard for m in extract_skill_matches('ES TO SC are ordinary uppercase tokens')),
      'business intelligence analyst':set(m.standard for m in extract_skill_matches('business intelligence analyst')),
      '机器学习工程师使用 Python':set(m.standard for m in extract_skill_matches('机器学习工程师使用 Python')),
    }
    rule_precision=(not adversarial['ES TO SC are ordinary uppercase tokens'] and '商业智能' in adversarial['business intelligence analyst'])
    rule_recall={'机器学习','Python'}.issubset(adversarial['机器学习工程师使用 Python'])
    checks={'skill_ids_unique_and_present':len(ids)==len(set(ids)) and all(ids),'parent_relations_acyclic':not has_cycle(data),'parents_exist':all(not x.get('parent_skill') or x['parent_skill'] in data for x in data.values()),'unsafe_short_aliases_removed':not risky.intersection(aliases),'lifecycle_has_window_algorithm_and_sources':lifecycle_ok,'no_manual_default_emerging':all(x.get('lifecycle_evidence',{}).get('counts') is not None for x in data.values()),'valid_skill_types':all(x.get('skill_type') in {'standard_skill','tool','framework','platform','method','domain','job_capability','technology'} for x in data.values()),'adversarial_precision_rules_pass':rule_precision,'adversarial_recall_rules_pass':rule_recall}
    candidates=json.loads((BASE/'data/gold/reference/skill_candidates.json').read_text(encoding='utf-8')); deprecated=json.loads((BASE/'data/gold/reference/skill_deprecated.json').read_text(encoding='utf-8'))
    checks['formal_core_size_150_to_220']=150<=len(data)<=220
    checks['formal_insufficient_evidence_below_20_percent']=sum(x.get('lifecycle_stage')=='insufficient_evidence' for x in data.values())/max(1,len(data))<.2
    checks['candidate_and_deprecated_separated']=all(x.get('ontology_status')=='candidate' for x in candidates.values()) and all(x.get('ontology_status')=='deprecated' for x in deprecated.values())
    report={'ontology_version':'2.1.0','skills':len(data),'candidate_skills':len(candidates),'deprecated_skills':len(deprecated),'lifecycle_distribution':Counter(x.get('lifecycle_stage') for x in data.values()),'checks':checks,'passed':all(checks.values()),'extraction_evaluation':{'formal_precision_recall_f1_status':'blocked_no_real_anonymized_gold_set','reason':'现有gold_resume_set_reviewed.json明确标记为synthetic，按数据治理规则不得用于正式准确率；resumes_anonymized_evaluation.jsonl当前也不是有效简历金标。','adversarial_rule_tests':{k:sorted(v) for k,v in adversarial.items()},'development_rule_checks_passed':rule_precision and rule_recall}}
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=dict),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2,default=dict));return report
if __name__=='__main__':raise SystemExit(0 if validate()['passed'] else 1)
