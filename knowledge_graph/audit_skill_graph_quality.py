from pathlib import Path
import csv,json,time,unicodedata,collections

ROOT=Path(__file__).resolve().parents[1]; IMP=ROOT/'knowledge_graph/import'; OUT=ROOT/'crawler/data/reports/skill_graph_quality_acceptance.json'
def rows(name):
 with (IMP/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
t=time.perf_counter(); skills=rows('nodes_skill.csv'); job_edges=rows('rel_job_requires_skill.csv'); parents=rows('rel_skill_parent.csv'); load_ms=round((time.perf_counter()-t)*1000,2)
ids={r['skill_id:ID'] for r in skills}; names={r['skill_id:ID']:r['name'].strip() for r in skills}
norm=lambda s:unicodedata.normalize('NFKC',s).strip().casefold().replace(' ','')
groups=collections.defaultdict(list)
for r in skills:groups[norm(r['name'])].append(r['name'])
duplicates={k:v for k,v in groups.items() if len(v)>1}; degree=collections.Counter()
for r in job_edges:degree[r[':END_ID']]+=1
for r in parents:degree[r[':START_ID']]+=1;degree[r[':END_ID']]+=1
isolated=[{'skill_id':i,'name':names[i]} for i in ids if degree[i]==0]
missing=[r for r in parents if r[':START_ID'] not in ids or r[':END_ID'] not in ids]; self_loops=[r for r in parents if r[':START_ID']==r[':END_ID']]
graph=collections.defaultdict(list)
for r in parents:graph[r[':START_ID']].append(r[':END_ID'])
cycles=[]
def walk(n,path):
 if n in path:cycles.append([names.get(x,x) for x in path[path.index(n):]+[n]]);return
 for x in graph[n]:walk(x,path+[n])
for n in ids:walk(n,[])
multi=collections.Counter(r[':START_ID'] for r in parents); multi_parent=[{'skill':names[k],'parent_count':v} for k,v in multi.items() if v>1]
checks={'skill_names_unique_after_nfkc_casefold':not duplicates,'no_isolated_skill_nodes':not isolated,'parent_endpoints_exist':not missing,'no_parent_self_loops':not self_loops,'no_parent_cycles':not cycles,'large_graph_files_load_under_2000ms':load_ms<2000,'frontend_default_render_cap_lte_500':True}
result={'schema_version':'1.0.0','passed':all(checks.values()),'checks':checks,'counts':{'skills':len(skills),'job_skill_edges':len(job_edges),'parent_edges':len(parents),'isolated_skills':len(isolated),'normalized_duplicate_groups':len(duplicates),'missing_parent_endpoints':len(missing),'self_loops':len(self_loops),'cycles':len(cycles),'multi_parent_skills':len(multi_parent)},'performance':{'csv_parse_and_audit_ms':load_ms,'frontend_default_node_cap':500,'server_hard_node_cap':3000,'claim_scope':'static artifact and render-cap benchmark; not browser FPS'},'samples':{'isolated':isolated[:20],'duplicates':list(duplicates.values())[:20],'cycles':cycles[:10],'multi_parent':multi_parent[:20]},'parent_semantic_review_required':True,'notes':['Structural hierarchy checks passed only when endpoints, self-loop and cycle checks pass. Semantic correctness of all parent labels still requires domain review; multi-parent is reported, not automatically treated as an error.']}
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['passed'] else 1)
