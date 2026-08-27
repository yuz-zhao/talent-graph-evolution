import fs from'fs';import path from'path';import{fileURLToPath}from'url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'),p=path.join(root,'crawler/data/gold/review/duplicate_pair_review_queue.json'),d=JSON.parse(fs.readFileSync(p,'utf8')),rows=d.rows.filter(x=>['duplicate','distinct'].includes(x.human_label))
let tp=0,fp=0,fn=0;for(const x of rows){const pred=x.score>=.85;if(pred&&x.human_label==='duplicate')tp++;if(pred&&x.human_label==='distinct')fp++;if(!pred&&x.human_label==='duplicate')fn++}const precision=tp/(tp+fp||1),recall=tp/(tp+fn||1)
const out={labeled:rows.length,total:d.rows.length,metrics_available:rows.length===d.rows.length,precision,recall,tp,fp,fn,claim_allowed:rows.length===d.rows.length}
fs.writeFileSync(path.join(root,'crawler/data/reports/duplicate_human_evaluation.json'),JSON.stringify(out,null,2)+'\n','utf8');console.log(JSON.stringify(out,null,2))
