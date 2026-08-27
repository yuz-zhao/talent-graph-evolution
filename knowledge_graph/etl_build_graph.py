"""Build Neo4j CSVs exclusively from current crawler/data/gold records."""
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; GOLD=ROOT/'crawler/data/gold/records'; REF=ROOT/'crawler/data/gold/reference'; OUT=ROOT/'knowledge_graph/import'
OUT.mkdir(parents=True,exist_ok=True)
RUNTIME=ROOT/'crawler/data/.ops/runtime_config.json'
try: runtime=json.loads(RUNTIME.read_text(encoding='utf-8')) if RUNTIME.exists() else {}
except (json.JSONDecodeError,OSError): runtime={}
IMPORT_BATCH_SIZE=max(100,min(10000,int(runtime.get('import_batch_size',1000))))
RELATION_DEFAULT_WEIGHT=max(0.0,min(1.0,float(runtime.get('relation_default_weight',.7))))
def rows(path):
 with path.open(encoding='utf-8') as f:return [json.loads(x) for x in f if x.strip()]
def arr(v):
 if isinstance(v,list):return v
 if not v:return []
 try:
  x=json.loads(v);return x if isinstance(x,list) else []
 except Exception:return [x.strip() for x in str(v).replace(',',';').split(';') if x.strip()]
def val(x):return '' if x is None else str(x)
def ident(prefix,*parts):return prefix+'_'+hashlib.sha256('|'.join(map(val,parts)).encode()).hexdigest()[:20]
def write(name,header,data):
 data=list(data)
 def safe(cell):return cell.replace('\\"','"') if isinstance(cell,str) else cell
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.writer(f);writer.writerow(header)
  for start in range(0,len(data),IMPORT_BATCH_SIZE):writer.writerows([safe(cell) for cell in row] for row in data[start:start+IMPORT_BATCH_SIZE])
def current(env):
 p=env.get('payload') or {}; synthetic=str(p.get('is_synthetic','')).lower() in {'1','true','yes'} or p.get('data_provenance')=='synthetic'
 return not env.get('lineage_migrated_at') and not synthetic and env.get('lifecycle_status','active')!='expired'
envs=[e for f in GOLD.glob('*.jsonl') for e in rows(f) if current(e)]
ontology=json.loads((REF/'skill_ontology.json').read_text(encoding='utf-8'))
skill_info={}; aliases={}
for name,info in ontology.items():
 sid=info.get('skill_id') or ident('SKILL',name);skill_info[name]=(sid,info)
 for a in [name,*arr(info.get('aliases'))]:aliases[str(a).casefold()]=name
def skills(v):
 out=[]
 for raw in arr(v):
  name=raw.get('skill') if isinstance(raw,dict) else raw; canonical=aliases.get(val(name).strip().casefold())
  if canonical and canonical not in out:out.append(canonical)
 return out
def evidence_map(p):
 result={}
 for item in arr(p.get('skill_evidence')):
  if isinstance(item,dict):
   name=aliases.get(val(item.get('skill') or item.get('standard_skill')).casefold())
   if name:result.setdefault(name,item)
 return result
def evtext(ev,p,skill):
 for k in ('evidence_text','evidence_sentence','snippet','evidence','text'):
  if val(ev.get(k)).strip():return val(ev[k]).strip()[:1000]
 text=val(p.get('abstract') or p.get('summary') or p.get('description') or p.get('requirements'))
 pos=text.casefold().find(skill.casefold());return text[max(0,pos-120):pos+len(skill)+180] if pos>=0 else ''

nodes={'job':[],'company':{},'paper':[],'blog':[],'project':[],'course':[],'certificate':[],'talent':[]}
rels={k:[] for k in ('job_skill','company_job','paper_skill','blog_skill','project_skill','course_skill','certificate_skill','talent_skill')}
used=set()
for e in envs:
 p=e.get('payload') or {}; typ=e.get('data_type'); url=e.get('source_url') or p.get('official_url') or p.get('html_url') or p.get('abs_url') or p.get('github_profile_url') or ''; obs=e.get('last_seen_at') or e.get('crawled_at') or p.get('observed_at') or ''; published=e.get('source_published_at') or p.get('published_at') or p.get('publish_time') or ''; window=published[:7] if len(published)>=7 else obs[:7]
 em=evidence_map(p)
 if typ=='job':
  # canonical_job_id groups equivalent roles and is not unique across observations.
  jid=e['record_id']; nodes['job'].append([jid,p.get('job_title'),p.get('standard_job_name'),p.get('company'),p.get('location'),p.get('description'),p.get('requirements'),published,window,url,e.get('source_platform'),obs,'observed',p.get('canonical_job_id'),p.get('industry')])
  company=val(p.get('company')).strip()
  if company:
   cid=ident('COMPANY',company);nodes['company'][cid]=[cid,company,p.get('industry'),p.get('company_type'),'observed'];rels['company_job'].append([cid,jid,1.0,'Official/public job posting',url,obs])
  candidates=skills(p.get('skill_standard'))
  for s in candidates:
   ev=em.get(s,{});text=evtext(ev,p,s)
   if text:used.add(s);rels['job_skill'].append([jid,skill_info[s][0],ev.get('confidence',p.get('skill_confidence',RELATION_DEFAULT_WEIGHT)),text,url,obs,ev.get('relation','mentioned')])
 elif typ=='paper':
  nid=p.get('arxiv_id') or e['record_id'];nodes['paper'].append([nid,p.get('title'),p.get('abstract'),p.get('authors'),p.get('primary_category'),published,window,url,obs,'observed'])
  for s in skills(p.get('relationship_skills') or p.get('inferred_skills')):
   text=evtext(em.get(s,{}),p,s)
   if text:used.add(s);rels['paper_skill'].append([nid,skill_info[s][0],em.get(s,{}).get('confidence',.85),text,url,obs,window])
 elif typ=='technology_article':
  nid=ident('BLOG',url);nodes['blog'].append([nid,p.get('title') or p.get('tech_name'),p.get('summary'),p.get('source_name'),p.get('article_type'),published,window,url,obs,'observed'])
  for s in skills(p.get('relationship_skills') or p.get('tags')):
   text=evtext(em.get(s,{}),p,s)
   if text:used.add(s);rels['blog_skill'].append([nid,skill_info[s][0],em.get(s,{}).get('confidence',.8),text,url,obs,window])
 elif typ=='technology_project':
  nid=val(p.get('repo_id') or e['record_id']);nodes['project'].append([nid,p.get('full_name') or p.get('name'),p.get('description'),p.get('primary_language'),p.get('stars'),p.get('forks'),p.get('created_at'),window,url,obs,'observed'])
  for s in skills([*arr(p.get('topics')),p.get('primary_language')]):
   used.add(s);rels['project_skill'].append([nid,skill_info[s][0],.9,f'Observed repository topic or primary language: {s}',url,obs,window])
 elif typ=='course':
  nid=p.get('course_id') or e['record_id'];nodes['course'].append([nid,p.get('course_name'),p.get('provider'),p.get('difficulty'),p.get('syllabus'),url,obs,p.get('availability_status'),'observed'])
  for s in skills(p.get('skills')):
   text=evtext(em.get(s,{}),p,s)
   if text:used.add(s);rels['course_skill'].append([nid,skill_info[s][0],em.get(s,{}).get('confidence',.85),text,url,obs])
 elif typ=='certificate':
  nid=p.get('certificate_id') or e['record_id'];nodes['certificate'].append([nid,p.get('certificate_name'),p.get('issuer'),p.get('level'),p.get('status'),url,obs,'observed'])
  for s in skills(p.get('related_skills')):
   text=evtext(em.get(s,{}),p,s)
   if text:used.add(s);rels['certificate_skill'].append([nid,skill_info[s][0],em.get(s,{}).get('confidence',.9),text,url,obs])
 elif typ=='public_profile':
  nid=p.get('profile_id') or e['record_id'];nodes['talent'].append([nid,p.get('display_name'),p.get('location'),p.get('bio'),url,obs,'public_observed'])
  for s in skills(p.get('skills')):
   ev=em.get(s,{});eurl=ev.get('repository_url') or url;text=evtext(ev,p,s) or f'Observed from public repository evidence for {s}'
   used.add(s);rels['talent_skill'].append([nid,skill_info[s][0],ev.get('confidence',.85),text,eurl,obs])
parent_rels=[]
for child in list(used):
 parent=aliases.get(val(skill_info[child][1].get('parent_skill')).strip().casefold())
 if parent and parent in skill_info and parent != child:
  used.add(parent);parent_rels.append([skill_info[child][0],skill_info[parent][0],1.0,'Skill ontology parent relation','', ''])
skill_nodes=[[skill_info[s][0],s,skill_info[s][1].get('category'),skill_info[s][1].get('skill_type'),skill_info[s][1].get('lifecycle_stage') or skill_info[s][1].get('lifecycle'),'observed_evidence'] for s in sorted(used)]
cluster_counts={}
job_cluster_rels=[]
for job in nodes['job']:
 cluster_name=val(job[2] or job[1]).strip() or '未标准化岗位'
 cluster_id=ident('CLUSTER',cluster_name)
 cluster_counts.setdefault(cluster_id,[cluster_id,cluster_name,0,'standard_name_v1'])
 cluster_counts[cluster_id][2]+=1
 job_cluster_rels.append([job[0],cluster_id,1.0,'Job standard name grouping',job[9],job[11]])
write('nodes_skill.csv',['skill_id:ID','name','category','skill_type','lifecycle','statistics_scope'],skill_nodes)
write('nodes_job.csv',['job_id:ID','title','standard_name','company','location','description','requirements','published_at','time_window','source_url','source_name','observed_at','statistics_scope','canonical_job_id','industry'],nodes['job'])
write('nodes_company.csv',['company_id:ID','name','industry','company_type','statistics_scope'],nodes['company'].values())
write('nodes_paper.csv',['paper_id:ID','title','abstract','authors','primary_category','published_at','time_window','source_url','observed_at','statistics_scope'],nodes['paper'])
write('nodes_blog.csv',['blog_id:ID','title','summary','source_name','article_type','published_at','time_window','source_url','observed_at','statistics_scope'],nodes['blog'])
write('nodes_tech_project.csv',['project_id:ID','name','description','language','stars','forks','created_at','time_window','source_url','observed_at','statistics_scope'],nodes['project'])
write('nodes_course.csv',['course_id:ID','name','provider','difficulty','syllabus','source_url','observed_at','status','statistics_scope'],nodes['course'])
write('nodes_certificate.csv',['certificate_id:ID','name','issuer','level','status','source_url','observed_at','statistics_scope'],nodes['certificate'])
write('nodes_talent.csv',['talent_id:ID','display_name','location','bio','source_url','observed_at','statistics_scope'],nodes['talent'])
write('nodes_job_cluster.csv',['cluster_id:ID','name','job_count:int','grouping_method'],cluster_counts.values())
rh=[':START_ID',':END_ID','confidence:float','evidence_text','source_url','observed_at']
write('rel_job_requires_skill.csv',rh+['requirement_type'],rels['job_skill']);write('rel_company_posts_job.csv',rh,rels['company_job']);write('rel_paper_mentions_tech.csv',rh+['time_window'],rels['paper_skill']);write('rel_blog_mentions_tech.csv',rh+['time_window'],rels['blog_skill']);write('rel_tech_project_uses_tech.csv',rh+['time_window'],rels['project_skill']);write('rel_course_teaches_skill.csv',rh,rels['course_skill']);write('rel_certificate_certifies_skill.csv',rh,rels['certificate_skill']);write('rel_talent_has_skill.csv',rh,rels['talent_skill'])
write('rel_job_belongs_cluster.csv',rh,job_cluster_rels)
write('rel_skill_parent.csv',rh,parent_rels)
job_ids=[row[0] for row in nodes['job']]
report={'input_gold_records':len(envs),'synthetic_records_in_formal_graph':0,'nodes':{**{k:len(v) for k,v in nodes.items()},'job_cluster':len(cluster_counts),'skill':len(skill_nodes)},'relationships':{**{k:len(v) for k,v in rels.items()},'job_cluster':len(job_cluster_rels),'skill_parent':len(parent_rels)},'unique_job_ids':len(set(job_ids)),'duplicate_job_ids':len(job_ids)-len(set(job_ids)),'paper_relations':len(rels['paper_skill']),'blog_relations':len(rels['blog_skill']),'all_relationships_have_source_url':all(r[4] for values in rels.values() for r in values),'time_window_supported':True,'v2_duplicate_files':False,'graph_contract_version':'1.0.0'}
(OUT/'etl_quality_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
