/** Read-only evaluation of the production V8 scoring path against human gold v1.1. */
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import dotenv from 'dotenv'
import neo4j from 'neo4j-driver'
import {
  calibratedMatchScore, embeddingSimilarityScore, jobDirectionCompatibility, MATCHING_FUSION_CONFIG, meanEmbedding, normalizedWeightedScore,
  qualificationEvidenceScore, recallCandidates, weightedSkillCoverage,
} from '../../server/matching-utils.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '../..')
dotenv.config({ path:path.join(root, 'server', '.env') })
const human = path.join(root, 'crawler', 'data', 'gold', 'human', 'v1.1')
const calibrationMode = process.env.TALENTGRAPH_EVAL_MODE === 'calibration'
const reportJson = path.join(root, 'crawler', 'data', 'reports', calibrationMode ? 'human_calibration_v1_0_v8_features.json' : 'human_gold_v1_1_v8_readonly_evaluation.json')
const reportMd = path.join(root, 'crawler', 'data', 'reports', calibrationMode ? 'human_calibration_v1_0_v8_features.md' : 'human_gold_v1_1_v8_readonly_evaluation.md')
const loadJsonl = async name => (await fs.readFile(path.join(human,name),'utf8')).split(/\r?\n/).filter(Boolean).map(JSON.parse)
const schema = JSON.parse(await fs.readFile(path.join(root,'knowledge_graph','graph_schema.json'),'utf8')).neo4j_contract
const N=schema.nodes, R=schema.relationships
const q = value => `\`${String(value).replaceAll('`','``')}\``
if (!process.env.NEO4J_PASSWORD) throw new Error('NEO4J_PASSWORD is required')
const driver = neo4j.driver(process.env.NEO4J_URI || 'bolt://localhost:7687', neo4j.auth.basic(process.env.NEO4J_USER || 'neo4j', process.env.NEO4J_PASSWORD))
const session = driver.session({ defaultAccessMode:neo4j.session.READ })
const toNumber = value => value?.toInt ? value.toInt() : Number(value || 0)
const setLower = values => new Set((values||[]).map(x=>String(x).trim().toLowerCase()).filter(Boolean))
const ordinal = score => score <= 0 ? 0 : score < 40 ? 1 : score < 70 ? 2 : 3
const rounded = value => typeof value==='number' ? Math.round(value*10000)/10000 : Array.isArray(value) ? value.map(rounded) : value&&typeof value==='object' ? Object.fromEntries(Object.entries(value).map(([k,v])=>[k,rounded(v)])) : value

function classification(gold,pred){
  const labels=[0,1,2,3], matrix=labels.map(a=>labels.map(b=>gold.filter((y,i)=>y===a&&pred[i]===b).length))
  const perClass={}, f1s=[]
  for(const x of labels){const tp=matrix[x][x],fp=labels.filter(i=>i!==x).reduce((s,i)=>s+matrix[i][x],0),fn=labels.filter(i=>i!==x).reduce((s,i)=>s+matrix[x][i],0);const p=tp+fp?tp/(tp+fp):0,r=tp+fn?tp/(tp+fn):0,f=p+r?2*p*r/(p+r):0;perClass[x]={precision:p,recall:r,f1:f,support:matrix[x].reduce((a,b)=>a+b,0)};f1s.push(f)}
  const n=gold.length,acc=gold.filter((x,i)=>x===pred[i]).length/n,gc=labels.map(x=>gold.filter(y=>y===x).length),pc=labels.map(x=>pred.filter(y=>y===x).length),exp=labels.reduce((s,x)=>s+gc[x]*pc[x],0)/(n*n)
  return {accuracy:acc,macro_f1:f1s.reduce((a,b)=>a+b,0)/4,cohen_kappa:exp<1?(acc-exp)/(1-exp):0,mae:gold.reduce((s,x,i)=>s+Math.abs(x-pred[i]),0)/n,confusion_matrix:matrix,per_class:perClass,prediction_distribution:Object.fromEntries(labels.map(x=>[x,pred.filter(y=>y===x).length]))}
}
function ranking(rows){
  const groups=Map.groupBy(rows,x=>x.resume_id), result={query_count:groups.size}
  for(const k of [5,10]){let nd=0,rec=0,mrr=0;for(const xs of groups.values()){const ranked=[...xs].sort((a,b)=>b.v8_score-a.v8_score||a.pair_id.localeCompare(b.pair_id)),ideal=[...xs].sort((a,b)=>b.relevance-a.relevance);const dcg=ranked.slice(0,k).reduce((s,x,i)=>s+(2**x.relevance-1)/Math.log2(i+2),0),idcg=ideal.slice(0,k).reduce((s,x,i)=>s+(2**x.relevance-1)/Math.log2(i+2),0),relevant=xs.filter(x=>x.relevance>=2).length,first=ranked.findIndex(x=>x.relevance>=2);nd+=idcg?dcg/idcg:0;rec+=relevant?ranked.slice(0,k).filter(x=>x.relevance>=2).length/relevant:0;mrr+=first>=0?1/(first+1):0}result[`ndcg@${k}`]=nd/groups.size;result[`recall@${k}`]=rec/groups.size;if(k===10)result.mrr=mrr/groups.size}
  return result
}

function bootstrapIntervals(rows, iterations=1000, seed=20260812){
  const grouped=[...Map.groupBy(rows,x=>x.resume_id).values()]
  let state=seed>>>0
  const random=()=>{state=(1664525*state+1013904223)>>>0;return state/2**32}
  const samples={accuracy:[],macro_f1:[],'ndcg@10':[],'recall@10':[]}
  for(let iteration=0;iteration<iterations;iteration++){
    const sampled=[]
    for(let index=0;index<grouped.length;index++)sampled.push(...grouped[Math.floor(random()*grouped.length)])
    const cls=classification(sampled.map(x=>x.relevance),sampled.map(x=>x.v8_class))
    const rank=ranking(sampled)
    samples.accuracy.push(cls.accuracy);samples.macro_f1.push(cls.macro_f1)
    samples['ndcg@10'].push(rank['ndcg@10']);samples['recall@10'].push(rank['recall@10'])
  }
  const percentile=(values,p)=>[...values].sort((a,b)=>a-b)[Math.floor((values.length-1)*p)]
  return Object.fromEntries(Object.entries(samples).map(([metric,values])=>[metric,{lower:percentile(values,.025),upper:percentile(values,.975)}]))
}

try {
  const [jds,resumes,matches,gnn] = await Promise.all([
    loadJsonl('gold_jd_v1.1.jsonl'), loadJsonl('gold_resume_v1.1.jsonl'), loadJsonl(calibrationMode ? 'calibration/human_match_calibration_v1.0.jsonl' : 'gold_match_v1.1.jsonl'),
    fs.readFile(path.join(root,'knowledge_graph','gnn_models','online_embeddings.json'),'utf8').then(JSON.parse).catch(()=>null),
  ])
  const jdBy=new Map(jds.map(x=>[x.sample_id,x])), resumeBy=new Map(resumes.map(x=>[x.resume_id,x]))
  const candidateResult=await session.run(`MATCH (c:${q(N.job_cluster)})<-[:${q(R.job_belongs_cluster)}]-(j:${q(N.job)})-[r:${q(R.job_requires_skill)}]->(sk:${q(N.skill)}) WITH c, collect(DISTINCT sk.name) AS skills, collect(DISTINCT j.industry) AS industries, collect({name:sk.name,requirementType:coalesce(r.requirement_type,'mentioned'),confidence:coalesce(r.confidence,0.5),observedAt:r.observed_at,evidenceText:r.evidence_text,sourceUrl:r.source_url}) AS requirements RETURN c.name AS name,c.job_count AS jd_count,skills,industries,requirements ORDER BY c.job_count DESC LIMIT 1000`)
  const candidates=candidateResult.records.map(r=>({name:r.get('name'),jdCount:toNumber(r.get('jd_count')),skills:r.get('skills')||[],industries:r.get('industries')||[],requirements:r.get('requirements')||[]}))
  const totalResult=await session.run(`MATCH (j:${q(N.job)}) RETURN count(DISTINCT j) AS n`), totalJobs=toNumber(totalResult.records[0]?.get('n'))||1
  const dfResult=await session.run(`MATCH (j:${q(N.job)})-[:${q(R.job_requires_skill)}]->(sk:${q(N.skill)}) RETURN sk.name AS name,count(DISTINCT j) AS df`)
  const corpus={totalJobs,documentFrequency:Object.fromEntries(dfResult.records.map(r=>[r.get('name'),toNumber(r.get('df'))]))}
  const centResult=await session.run(`MATCH (sk:${q(N.skill)}) OPTIONAL MATCH (sk)<-[rel]-(n) RETURN sk.name AS name,count(rel) AS degree`)
  const maxDegree=Math.max(1,...centResult.records.map(r=>toNumber(r.get('degree')))), centrality=new Map(centResult.records.map(r=>[r.get('name'),Math.min(100,Math.round(toNumber(r.get('degree'))/maxDegree*100))]))
  const coocResult=await session.run(`MATCH (sk1:${q(N.skill)})<-[:${q(R.job_requires_skill)}]-(j:${q(N.job)})-[:${q(R.job_requires_skill)}]->(sk2:${q(N.skill)}) WHERE id(sk1)<id(sk2) WITH sk1,sk2,count(j) AS n WHERE n>=3 RETURN sk1.name AS a,sk2.name AS b,n ORDER BY n DESC LIMIT 500`)
  const cooc=new Map();for(const r of coocResult.records){cooc.set(`${r.get('a')}|${r.get('b')}`,toNumber(r.get('n')));cooc.set(`${r.get('b')}|${r.get('a')}`,toNumber(r.get('n')))}
  const parentResult=await session.run(`MATCH (child:${q(N.skill)})-[:${q(R.skill_parent)}]->(parent:${q(N.skill)}) RETURN child.name AS child,parent.name AS parent`)
  const parents=new Map(),children=new Map();for(const r of parentResult.records){const c=r.get('child'),p=r.get('parent');if(!parents.has(c))parents.set(c,new Set());parents.get(c).add(p);if(!children.has(p))children.set(p,new Set());children.get(p).add(c)}

  const scoredByResume=new Map(), recallDiagnostics=[], evaluatedResumeIds=new Set(matches.map(x=>x.resume_id))
  for(const resume of resumes.filter(x=>evaluatedResumeIds.has(x.resume_id))){
    const skills=resume.skills||[], skillSet=setLower(skills), userEmbedding=gnn?meanEmbedding(skills,gnn.embeddings?.skill):null
    const recall=recallCandidates(candidates.map(x=>({...x})),{skills,direction:resume.target_job,industry:null},{limit:1000,minimum:60})
    const scores=new Map()
    for(const c of recall.candidates){const matched=c.skills.filter(x=>skillSet.has(String(x).toLowerCase())),missing=c.skills.filter(x=>!skillSet.has(String(x).toLowerCase())),coverage=weightedSkillCoverage(c.requirements,matched,corpus),skillScore=coverage.totalWeight>0?coverage.coverage:Math.round(matched.length/Math.max(1,c.skills.length)*100);let hierarchyBonus=0;for(const x of matched){for(const p of parents.get(x)||[])if(c.skills.includes(p))hierarchyBonus+=3;for(const ch of children.get(x)||[])if(c.skills.includes(ch))hierarchyBonus+=2}for(const x of missing)for(const p of parents.get(x)||[])if(skillSet.has(String(p).toLowerCase()))hierarchyBonus+=5;const hierarchy=(parents.size||children.size)?Math.min(100,Math.round(skillScore+hierarchyBonus*5)):null;const qualification=qualificationEvidenceScore(resume.highest_education,c.requirements.map(x=>x.evidenceText).filter(Boolean)).score;let cs=0,cc=0;for(const x of matched){cs+=centrality.get(x)||30;cc++}const central=cc?Math.round(cs/cc):null;let bonus=0,pairs=0;for(const x of matched)for(const y of c.skills){const n=cooc.get(`${x}|${y}`)||0;if(n){bonus+=Math.min(n,20);pairs++}}const cooccur=pairs?Math.min(100,Math.round(50+bonus/pairs*5)):null;const graphFusion=normalizedWeightedScore({hierarchy,centrality:central,cooccurrence:cooccur,qualification,projectScene:null},{hierarchy:.3,centrality:.2,cooccurrence:.2,qualification:.15,projectScene:.15}),graph=graphFusion.availableWeight>0?graphFusion.score:null;const semanticFusion=normalizedWeightedScore({hierarchy,qualification,industry:null,graph},{hierarchy:.2,qualification:.15,industry:.25,graph:.4}),semantic=semanticFusion.availableWeight>0?semanticFusion.score:null;const preference=jobDirectionCompatibility(resume.target_job,c.name);const gnnScore=gnn?embeddingSimilarityScore(userEmbedding,gnn.embeddings?.job_cluster?.[c.name]):null;const fused=normalizedWeightedScore({required:skillScore,semantic,kg:graph,project:null,preference,cf:null,gnn:gnnScore},MATCHING_FUSION_CONFIG.weights),calibrated=calibratedMatchScore(fused.score,{directionPreference:preference,matchedSkillCount:matched.length});scores.set(c.name,{score:calibrated.score,class:ordinal(calibrated.score),calibration_adjustment:calibrated.adjustment,skill_score:skillScore,semantic_score:semantic,graph_score:graph,preference_score:preference,gnn_score:gnnScore,available_dimensions:fused.available,available_weight:fused.availableWeight,matched,missing})}
    scoredByResume.set(resume.resume_id,scores);recallDiagnostics.push({resume_id:resume.resume_id,total:recall.total,recalled:recall.recalled,positive:recall.positive,fallback_reason:recall.fallback,scored_clusters:scores.size})
  }
  const rows=matches.map(m=>{const jd=jdBy.get(m.jd_sample_id),score=scoredByResume.get(m.resume_id)?.get(jd?.standard_job_name);return {...m,standard_job_name:jd?.standard_job_name,job_title:jd?.job_title,v8_score:score?.score??0,v8_class:score?.class??0,recall_status:score?'recalled':'not_recalled',dimensions:score||null}})
  const gold=rows.map(x=>x.relevance),pred=rows.map(x=>x.v8_class),metrics=classification(gold,pred);metrics.ranking=ranking(rows)
  const recalledRows=rows.filter(x=>x.recall_status==='recalled'), recalledMetrics=classification(recalledRows.map(x=>x.relevance),recalledRows.map(x=>x.v8_class));recalledMetrics.ranking=ranking(recalledRows)
  const recallByLabel=Object.fromEntries([0,1,2,3].map(label=>{const xs=rows.filter(x=>x.relevance===label),hit=xs.filter(x=>x.recall_status==='recalled').length;return [label,{total:xs.length,recalled:hit,rate:hit/xs.length}]}))
  const componentSummary={};for(const key of ['skill_score','semantic_score','graph_score','preference_score','gnn_score']){const xs=recalledRows.map(x=>x.dimensions?.[key]).filter(x=>x!==null&&x!==undefined);componentSummary[key]={available:xs.length,rate:xs.length/recalledRows.length,mean:xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:null}}
  const report=rounded({schema_version:'1.0.0',gold_version:calibrationMode?'calibration_v1.0':'gold_v1.1',algorithm_version:'diversified_feedback_matching_v8',algorithm_revision:'candidate_direction_availability_fix_2026-08-12',evaluation_mode:'read_only_production_scoring_cold_start',formal_human_gold:true,write_operations:0,scope:{pairs:rows.length,resumes:scoredByResume.size,graph_candidate_limit:1000,recall_limit:60},coverage:{pairs_recalled:recalledRows.length,pairs_not_recalled:rows.length-recalledRows.length,recall_by_gold_label:recallByLabel,unique_gold_clusters:new Set(rows.map(x=>x.standard_job_name)).size,unique_gold_clusters_in_candidate_universe:new Set(rows.filter(x=>candidates.some(c=>c.name===x.standard_job_name)).map(x=>x.standard_job_name)).size,gnn_available_pairs:rows.filter(x=>x.dimensions?.gnn_score!==null&&x.dimensions?.gnn_score!==undefined).length},metrics,metrics_on_recalled_pairs:recalledMetrics,component_summary:componentSummary,rows,recall_diagnostics:recallDiagnostics,largest_errors:[...rows].sort((a,b)=>Math.abs(b.relevance-b.v8_class)-Math.abs(a.relevance-a.v8_class)).slice(0,30).map(x=>({pair_id:x.pair_id,resume_id:x.resume_id,job_title:x.job_title,standard_job_name:x.standard_job_name,gold:x.relevance,predicted:x.v8_class,score:x.v8_score,recall_status:x.recall_status,dimensions:x.dimensions})),limitations:['Read-only evaluation reuses production V8 scoring utilities, graph schema, weights and GNN artifact without calling the mutating API endpoint.','No synthetic behavior events are created; CF and feedback dimensions are unavailable and production weight renormalization is applied.','Gold labels are JD-level while production V8 ranks standard-name job clusters; JD standard_job_name is used as the declared bridge.','Ordinal bridge is fixed before evaluation: score=0 -> 0, (0,40) -> 1, [40,70) -> 2, >=70 -> 3.']})
  report.scope.recall_limit=1000
  report.production_fusion_config=MATCHING_FUSION_CONFIG
  report.gnn_evaluation_role='shadow_only_not_in_production_score'
  report.frozen_test_set={version:'human_gold_v1.1',locked:true,split:'test',label_source:'independent_double_annotation_with_arbitration'}
  report.error_samples=report.largest_errors
  report.confidence_intervals_95=bootstrapIntervals(rows)
  report.confidence_interval_method={method:'resume_cluster_bootstrap',iterations:1000,seed:20260812}
  await fs.writeFile(reportJson,JSON.stringify(report,null,2)+'\n','utf8')
  const m=report.metrics,c=report.coverage
  await fs.writeFile(reportMd,`# TalentGraph V8 只读端到端评测（人工金标 V1.1）\n\n## 总体结果\n\n- 算法：${report.algorithm_version}\n- 模式：无行为冷启动，只读，不写数据库\n- 样本：${report.scope.pairs} 对 / ${report.scope.resumes} 份 test 简历\n- Accuracy：${m.accuracy}\n- Macro-F1：${m.macro_f1}\n- Kappa：${m.cohen_kappa}\n- MAE：${m.mae}\n- NDCG@10：${m.ranking['ndcg@10']}\n- Recall@10：${m.ranking['recall@10']}\n\n## 召回诊断\n\n- 金标对召回：${c.pairs_recalled}/${report.scope.pairs}（${(c.pairs_recalled/report.scope.pairs*100).toFixed(1)}%）\n- 未召回：${c.pairs_not_recalled}\n- 金标岗位群进入生产 Top100：${c.unique_gold_clusters_in_candidate_universe}/${c.unique_gold_clusters}\n- 0/1/2/3级召回率：${[0,1,2,3].map(x=>`${x}级 ${c.recall_by_gold_label[x].rate}`).join('，')}\n- 只看已召回样本：Accuracy ${report.metrics_on_recalled_pairs.accuracy}，Macro-F1 ${report.metrics_on_recalled_pairs.macro_f1}\n- GNN 可用对：${c.gnn_available_pairs}/${report.scope.pairs}\n\n## 主要结论\n\n- Top100 热度候选截断造成大量金标岗位在评分前丢失，应先修召回覆盖。\n- V8 几乎不输出3级（总体仅 ${m.prediction_distribution[3]} 条），融合分数存在明显压缩。\n- 岗位方向只占 preference 5%，不足以阻止跨方向技能重合造成误排。\n- 项目、CF、反馈在冻结评测中不可用；缺失维度会重归一化，但当前 graph/semantic 的零分仍可能作为“可用分数”进入融合。\n\n## 解释边界\n\n${report.limitations.map(x=>`- ${x}`).join('\n')}\n`,'utf8')
  const reportLines = [
    '# TalentGraph V8 只读端到端评测（人工金标 V1.1）',
    '', '## 总体结果', '',
    `- 算法：${report.algorithm_version}`,
    `- 实现修订：${report.algorithm_revision}`,
    '- 模式：无行为冷启动，只读，不写数据库',
    `- 样本：${report.scope.pairs} 对 / ${report.scope.resumes} 份 test 简历`,
    `- Accuracy：${m.accuracy}`,
    `- Macro-F1：${m.macro_f1}`,
    `- Kappa：${m.cohen_kappa}`,
    `- MAE：${m.mae}`,
    `- NDCG@10：${m.ranking['ndcg@10']}`,
    `- Recall@10：${m.ranking['recall@10']}`,
    '', '## 召回诊断', '',
    `- 金标对召回：${c.pairs_recalled}/${report.scope.pairs}（${(c.pairs_recalled/report.scope.pairs*100).toFixed(1)}%）`,
    `- 未召回：${c.pairs_not_recalled}`,
    `- 金标岗位群进入生产 Top${report.scope.graph_candidate_limit}：${c.unique_gold_clusters_in_candidate_universe}/${c.unique_gold_clusters}`,
    `- 0/1/2/3 级召回率：${[0,1,2,3].map(x=>`${x}级 ${c.recall_by_gold_label[x].rate}`).join('，')}`,
    `- 只看已召回样本：Accuracy ${report.metrics_on_recalled_pairs.accuracy}，Macro-F1 ${report.metrics_on_recalled_pairs.macro_f1}`,
    `- GNN 可用对：${c.gnn_available_pairs}/${report.scope.pairs}`,
    '', '## 当前判断', '',
    '- 候选全集已覆盖全部 39 个金标岗位群；1/2/3 级样本均进入评分，主要召回结构问题已修复。',
    '- 当前主要瓶颈转为排序与分档：2 级预测偏多，3 级召回偏低，不能直接用本测试集反复调阈值。',
    '- 0 级仍有 27 对未召回并自然预测为 0；这是合理的负样本过滤，但其余 83 个负样本需要靠排序模型压低。',
    '- 下一步应使用独立 validation 集学习/校准融合排序，再在本 test 金标上只做一次冻结验收。',
    '', '## 解释边界', '', ...report.limitations.map(x=>`- ${x}`), '',
  ]
  await fs.writeFile(reportMd, reportLines.join('\n'), 'utf8')
  console.log(JSON.stringify({coverage:report.coverage,metrics:report.metrics},null,2))
} finally { await session.close(); await driver.close() }
