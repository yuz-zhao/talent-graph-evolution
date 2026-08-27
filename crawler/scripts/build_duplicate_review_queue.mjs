import fs from'fs';import path from'path';import{fileURLToPath}from'url'
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..'),report=JSON.parse(fs.readFileSync(path.join(root,'crawler/data/reports/multisource_audit_report.json'),'utf8'))
const pairs=report.duplicate_pairs||[],bins=[[.95,1],[.85,.95],[0,.85]],sample=[]
for(const [low,high] of bins)sample.push(...pairs.filter(x=>x.score>=low&&x.score<=high).slice(0,20))
const rows=sample.map((x,i)=>({...x,review_id:`DUP_${String(i+1).padStart(3,'0')}`,human_label:null,reviewer:'',review_note:''}))
fs.mkdirSync(path.join(root,'crawler/data/gold/review'),{recursive:true});fs.writeFileSync(path.join(root,'crawler/data/gold/review/duplicate_pair_review_queue.json'),JSON.stringify({schema_version:'1.0.0',frozen:true,label_definition:{duplicate:'同一岗位内容重复/转载',distinct:'不同岗位'},rows},null,2)+'\n','utf8')
console.log(JSON.stringify({sample_count:rows.length,labeled:0,metrics_available:false}))
