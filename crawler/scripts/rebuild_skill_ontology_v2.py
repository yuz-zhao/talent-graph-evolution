"""Rebuild a versioned skill ontology using only observed, non-synthetic evidence."""
from __future__ import annotations
import csv, hashlib, json, re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
ONTO=BASE/"data/gold/reference/skill_ontology.json"
CANDIDATES=BASE/"data/gold/reference/skill_candidates.json"
DEPRECATED=BASE/"data/gold/reference/skill_deprecated.json"
VERSION=BASE/"data/gold/reference/skill_ontology.version.json"
CHANGELOG=BASE/"data/gold/reference/skill_ontology.changelog.jsonl"
RISKY={"es","to","bi","sc"}
CONTEXT_SHORT={"ai","go","r","cv","nlp","llm","rag","ocr","aws","git","plc","ios"}

def repair(value):
    if not isinstance(value,str): return value
    for enc in ("gbk","utf-8"):
        try:
            candidate=value.encode("latin1").decode(enc)
            if sum('\u4e00'<=c<='\u9fff' for c in candidate)>sum('\u4e00'<=c<='\u9fff' for c in value): return candidate
        except (UnicodeEncodeError,UnicodeDecodeError): pass
    return value

def parse_list(value):
    if isinstance(value,list): return value
    text=str(value or '').strip()
    if not text: return []
    try:
        parsed=json.loads(text)
        if isinstance(parsed,list): return parsed
    except json.JSONDecodeError: pass
    return [x.strip() for x in re.split(r'[;,|]',text) if x.strip()]

def load_jsonl(path):
    if not path.exists(): return []
    rows=[]
    with path.open(encoding='utf-8') as f:
        for line in f:
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: continue
    return rows

def evidence_counts():
    counts=defaultdict(Counter)
    with (BASE/'data/silver/jobs/jd_clean.csv').open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            if str(row.get('is_synthetic','')).lower() in {'1','true','yes'}: continue
            for skill in parse_list(row.get('skill_standard')): counts[repair(skill)]['jobs']+=1
    for row in load_jsonl(BASE/'data/bronze/github_trend.jsonl'):
        for skill in [row.get('primary_language'),*parse_list(row.get('inferred_skills')), *parse_list(row.get('topics'))]:
            if skill: counts[repair(skill)]['github']+=1
    for filename,channel in [('arxiv_trend.jsonl','papers'),('blog_trend.jsonl','industry')]:
        for row in load_jsonl(BASE/'data/bronze'/filename):
            for skill in parse_list(row.get('relationship_skills') or row.get('inferred_skills')):
                if skill: counts[repair(skill)][channel]+=1
    return counts

def skill_type(name,category):
    frameworks={'React','Vue.js','Angular','Spring Boot','Spring Cloud','Django','Flask','FastAPI','PyTorch','TensorFlow','Keras','Scikit-learn','LangChain','LlamaIndex'}
    platforms={'AWS','Azure','GCP','阿里云','腾讯云','华为云','GitHub','GitLab','Linux','Android','iOS'}
    tools={'Git','Docker','Kubernetes','Jenkins','Terraform','Ansible','Nginx','Prometheus','Grafana','Kafka','Redis','MySQL','PostgreSQL','MongoDB','Hive','Spark','Flink'}
    capabilities={'产品管理','需求分析','解决方案设计','技术咨询','技术支持','技术研究','标准研究','科研项目管理','项目管理','系统运维'}
    domains={'人工智能','云计算','物联网','工业互联网','智能制造','网络安全','信息安全','大数据','数据通信'}
    if name in capabilities:return 'job_capability'
    if name in frameworks:return 'framework'
    if name in platforms:return 'platform'
    if name in tools:return 'tool'
    if name in domains:return 'domain'
    if re.search(r'学习|分析|设计|测试|建模|治理|识别|检测|计算$',name):return 'method'
    if category in {'AI','Cloud','IoT','Security','Data'} and len(name)>4:return 'standard_skill'
    return 'technology'

def stage(counter):
    jobs=counter['jobs']; external=counter['github']+counter['papers']+counter['industry']; sources=sum(counter[k]>0 for k in ('jobs','github','papers','industry'))
    if jobs>=30 and sources>=1:return 'mature'
    if jobs>=5 and sources>=2:return 'growth'
    if external>=3 and sources>=2:return 'emerging'
    if jobs>=3:return 'observed'
    if sources>=2:return 'observed'
    return 'insufficient_evidence'

def break_cycles(ontology):
    removed=[]
    for name in ontology:
        seen=[]; current=name
        while current and current in ontology:
            if current in seen:
                ontology[name]['parent_skill']=''; removed.append({'skill':name,'reason':'parent_cycle'}); break
            seen.append(current); current=ontology[current].get('parent_skill','')
    return removed

def main():
    old=json.loads(ONTO.read_text(encoding='utf-8'))
    for extra in (CANDIDATES,DEPRECATED):
        if extra.exists(): old.update(json.loads(extra.read_text(encoding='utf-8')))
    counts=evidence_counts(); merged={}; duplicate_merges=[]; removed_aliases=[]
    for old_name,raw in old.items():
        name=repair(raw.get('standard_name') or old_name).strip(); key=name.casefold()
        if not name: continue
        item=merged.setdefault(key,{'name':name,'raws':[]}); item['raws'].append(raw)
        if len(item['raws'])>1: duplicate_merges.append({'from':repair(old_name),'merged_into':name})
    ontology={}; computed=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
    for entry in sorted(merged.values(),key=lambda x:x['name'].casefold()):
        name=entry['name']; raw=entry['raws'][0]; aliases=[]
        for source in entry['raws']:
            for alias in source.get('aliases') or []:
                alias=repair(alias).strip(); low=alias.casefold()
                if low in RISKY or (alias.isascii() and len(alias)<=2 and low not in CONTEXT_SHORT): removed_aliases.append({'skill':name,'alias':alias,'reason':'unsafe_short_alias'}); continue
                if alias and low!=name.casefold() and low not in {x.casefold() for x in aliases}: aliases.append(alias)
        category=repair(raw.get('category','Other')); parent=repair(raw.get('parent_skill','')).strip(); c=counts.get(name,Counter())
        ontology[name]={
          'skill_id':'skill_'+hashlib.sha256(name.casefold().encode()).hexdigest()[:16], 'standard_name':name,'skill_type':skill_type(name,category),
          'aliases':aliases,'alias_rules':{a:{'boundary':'unicode_word','context_required':a.casefold() in CONTEXT_SHORT} for a in aliases},
          'category':category,'parent_skill':parent if parent!=name else '', 'lifecycle_stage':stage(c),
          'lifecycle_evidence':{'window_start':'2025-01-01','window_end':computed[:10],'algorithm_version':'lifecycle_evidence_v1','counts':{k:c[k] for k in ('jobs','github','papers','industry')},'source_files':['crawler/data/silver/jobs/jd_clean.csv','crawler/data/bronze/github_trend.jsonl','crawler/data/bronze/papers_trend.jsonl','crawler/data/bronze/blogs_trend.jsonl'],'computed_at':computed},
          'deprecated':False,'merged_into':'','replaced_by':'','ontology_version':'2.0.0'
        }
    # Missing/corrupt parents are removed rather than invented.
    invalid=[]
    for name,item in ontology.items():
        item['ontology_version']='2.1.0'
        if item['parent_skill'] and item['parent_skill'] not in ontology: invalid.append({'skill':name,'parent':item['parent_skill']}); item['parent_skill']=''
    cycles=break_cycles(ontology)
    deprecated_short={'ES':'Elasticsearch','BI':'商业智能','TO':'','SC':''}
    for short,replacement in deprecated_short.items():
        if short in ontology:
            ontology[short]['deprecated']=True; ontology[short]['merged_into']=replacement; ontology[short]['replaced_by']=replacement
            ontology[short]['lifecycle_stage']='deprecated'
    core={}; candidates={}; deprecated={}
    for name,item in ontology.items():
        c=item['lifecycle_evidence']['counts']; source_count=sum(c[x]>0 for x in ('jobs','github','papers','industry'))
        if item['deprecated']:
            item['ontology_status']='deprecated'; deprecated[name]=item
        elif c['jobs']>=3 or source_count>=2:
            item['ontology_status']='core'; core[name]=item
        else:
            item['ontology_status']='candidate'; item['candidate_reason']='fewer_than_3_job_observations_and_fewer_than_2_evidence_sources'; candidates[name]=item
    for item in core.values():
        if item.get('parent_skill') not in core:item['parent_skill']=''
    ONTO.write_text(json.dumps(core,ensure_ascii=False,indent=2),encoding='utf-8')
    CANDIDATES.write_text(json.dumps(candidates,ensure_ascii=False,indent=2),encoding='utf-8')
    DEPRECATED.write_text(json.dumps(deprecated,ensure_ascii=False,indent=2),encoding='utf-8')
    version={'version':'2.1.0','released_at':computed,'skill_count':len(core),'candidate_count':len(candidates),'deprecated_count':len(deprecated),'algorithm_version':'lifecycle_evidence_v1','promotion_rule':'jobs>=3 OR evidence_sources>=2','source_policy':'observed_non_synthetic_only','previous_version':'2.0.0'}
    VERSION.write_text(json.dumps(version,ensure_ascii=False,indent=2),encoding='utf-8')
    change={'version':'2.1.0','released_at':computed,'core_skills':len(core),'candidate_skills':len(candidates),'deprecated_skills':len(deprecated),'promotion_rule':'jobs>=3 OR evidence_sources>=2','removed_unsafe_aliases':removed_aliases,'duplicate_merges':duplicate_merges,'removed_invalid_parents':invalid,'removed_cycles':cycles}
    if not CHANGELOG.exists() or '"version":"2.1.0"' not in CHANGELOG.read_text(encoding='utf-8').replace(' ', ''):
        with CHANGELOG.open('a',encoding='utf-8') as handle: handle.write(json.dumps(change,ensure_ascii=False)+'\n')
    print(json.dumps({'core_skills':len(core),'candidate_skills':len(candidates),'deprecated_skills':len(deprecated),'removed_short_aliases':len(removed_aliases),'duplicate_merges':len(duplicate_merges),'invalid_parents':len(invalid),'cycles_removed':len(cycles),'core_lifecycle':Counter(x['lifecycle_stage'] for x in core.values())},ensure_ascii=False,default=dict)); return 0
if __name__=='__main__':raise SystemExit(main())
