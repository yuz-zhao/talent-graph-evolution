import fs from 'node:fs/promises'
import path from 'node:path'

const root=path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\//,'')),'../..')
const input=JSON.parse(await fs.readFile(path.join(root,'crawler/data/reports/human_calibration_v1_0_v8_features.json'),'utf8'))
const rows=input.rows
if(rows.length!==200||rows.some(x=>!['development','validation'].includes(x.split)))throw new Error('Calibration rows/splits invalid')
const labels=[0,1,2,3]
const ordinal=(score,t)=>score<=0?0:score<t[0]?1:score<t[1]?2:3
const fused=(row,w)=>{if(!row.dimensions)return 0;let sum=0,weight=0;for(const key of ['required','semantic','kg','preference','gnn']){const v=row.dimensions[`${key==='required'?'skill':key==='kg'?'graph':key}_score`];if(v!==null&&v!==undefined&&Number.isFinite(Number(v))){sum+=Number(v)*w[key];weight+=w[key]}}return weight?Math.round(sum/weight):0}
function metrics(xs,w,t){const pred=xs.map(x=>ordinal(fused(x,w),t)),gold=xs.map(x=>x.relevance),matrix=labels.map(a=>labels.map(b=>gold.filter((y,i)=>y===a&&pred[i]===b).length)),f1=[];for(const x of labels){const tp=matrix[x][x],fp=labels.filter(i=>i!==x).reduce((s,i)=>s+matrix[i][x],0),fn=labels.filter(i=>i!==x).reduce((s,i)=>s+matrix[x][i],0),p=tp+fp?tp/(tp+fp):0,r=tp+fn?tp/(tp+fn):0;f1.push(p+r?2*p*r/(p+r):0)}const accuracy=gold.filter((x,i)=>x===pred[i]).length/gold.length,mae=gold.reduce((s,x,i)=>s+Math.abs(x-pred[i]),0)/gold.length;const groups=Map.groupBy(xs,x=>x.resume_id);let ndcg=0;for(const gs of groups.values()){const ranked=[...gs].sort((a,b)=>fused(b,w)-fused(a,w)),ideal=[...gs].sort((a,b)=>b.relevance-a.relevance),dcg=ranked.slice(0,10).reduce((s,x,i)=>s+(2**x.relevance-1)/Math.log2(i+2),0),idcg=ideal.slice(0,10).reduce((s,x,i)=>s+(2**x.relevance-1)/Math.log2(i+2),0);ndcg+=idcg?dcg/idcg:0}ndcg/=groups.size;return {accuracy,macro_f1:f1.reduce((a,b)=>a+b,0)/4,mae,ndcg10:ndcg,objective:.65*(f1.reduce((a,b)=>a+b,0)/4)+.35*ndcg,prediction_distribution:Object.fromEntries(labels.map(x=>[x,pred.filter(y=>y===x).length])),confusion_matrix:matrix}}
const dev=rows.filter(x=>x.split==='development'),validation=rows.filter(x=>x.split==='validation')
const weightSets=[]
for(const required of [.35,.45,.55,.65])for(const semantic of [.05,.15,.25])for(const kg of [.05,.15,.25])for(const preference of [.05,.15,.25])for(const gnn of [0,.05,.1])weightSets.push({required,semantic,kg,preference,gnn})
const candidates=[]
for(const w of weightSets)for(const t1 of [15,20,25,30,35])for(const t2 of [35,40,45,50,55])for(const t3 of [55,60,65,70,75])if(t1<t2&&t2<t3){const m=metrics(dev,w,[t1,t2,t3]);candidates.push({weights:w,thresholds:[t1,t2,t3],development:m})}
candidates.sort((a,b)=>b.development.objective-a.development.objective||b.development.macro_f1-a.development.macro_f1)
const finalists=candidates.slice(0,50).map(x=>({...x,validation:metrics(validation,x.weights,x.thresholds)})).sort((a,b)=>b.validation.objective-a.validation.objective||b.validation.macro_f1-a.validation.macro_f1||b.development.objective-a.development.objective)
const selected=finalists[0]
const baseline={weights:{required:.38,semantic:.19,kg:.14,preference:.05,gnn:.05},thresholds:[40,70,100]}
const report={schema_version:'1.0.0',method:'predeclared_grid_development_candidate_generation_validation_selection',test_labels_used:false,input_counts:{development:dev.length,validation:validation.length},search_space:{weight_sets:weightSets.length,total_candidates:candidates.length,development_finalists:50},baseline:{development:metrics(dev,baseline.weights,baseline.thresholds),validation:metrics(validation,baseline.weights,baseline.thresholds)},selected,top_validation_finalists:finalists.slice(0,10)}
const outDir=path.join(root,'crawler/data/reports');await fs.writeFile(path.join(outDir,'human_calibration_v1_0_selection.json'),JSON.stringify(report,null,2)+'\n','utf8')
const validationGain=selected.validation.objective-report.baseline.validation.objective
report.decision={accepted:false,reason:'validation_gain_below_minimum_and_high_class_support_too_small',minimum_objective_gain:.01,actual_objective_gain:validationGain,high_class_support:rows.filter(x=>x.relevance===3).length,production_change:false}
await fs.writeFile(path.join(outDir,'human_calibration_v1_0_selection.json'),JSON.stringify(report,null,2)+'\n','utf8')
console.log(JSON.stringify({baseline:report.baseline,selected},null,2))
