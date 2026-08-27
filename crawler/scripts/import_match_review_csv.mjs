import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const reviewer=String(process.argv[2]||'').toLowerCase()
if(!['a','b'].includes(reviewer))throw new Error('Usage: node crawler/scripts/import_match_review_csv.mjs <a|b> [csv-path]')
const csvPath=process.argv[3]?path.resolve(root,process.argv[3]):path.join(root,`crawler/data/evaluation/match_training_review_${reviewer}_v1.csv`)
const queuePath=path.join(root,'crawler/data/evaluation/match_training_annotation_queue_v1.jsonl')
function parseCsv(text){const rows=[];let row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const char=text[i];if(char==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++}else quoted=!quoted}else if(char===','&&!quoted){row.push(cell);cell=''}else if((char==='\n'||char==='\r')&&!quoted){if(char==='\r'&&text[i+1]==='\n')i++;row.push(cell);cell='';if(row.some(value=>value!==''))rows.push(row);row=[]}else cell+=char}if(cell||row.length){row.push(cell);rows.push(row)}return rows}
function parseList(value){return String(value||'').split(';').map(x=>x.trim()).filter(x=>x&&x!=='无'&&x.toLowerCase()!=='none')}
const parsed=parseCsv(fs.readFileSync(csvPath,'utf8').replace(/^\uFEFF/,'')),headers=parsed.shift(),records=parsed.map(values=>Object.fromEntries(headers.map((key,index)=>[key,values[index]??''])))
const queue=fs.readFileSync(queuePath,'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse),byId=new Map(queue.map(row=>[row.annotation_id,row]))
let imported=0
for(const record of records){if(record.relevance_0_3==='')continue;const relevance=Number(record.relevance_0_3);if(![0,1,2,3].includes(relevance))throw new Error(`${record.annotation_id}: relevance must be 0..3`);if(!record.annotator.trim()||!record.reason.trim())throw new Error(`${record.annotation_id}: annotator and reason are required`);const row=byId.get(record.annotation_id);if(!row)throw new Error(`Unknown annotation_id: ${record.annotation_id}`);row[`review_${reviewer}`]={annotator:record.annotator.trim(),relevance,direction_match:record.direction_match_yes_no_unknown||null,level_match:record.level_match_yes_no_unknown||null,experience_match:record.experience_match_yes_no_unknown||null,matched_skills:parseList(record.matched_skills_semicolon),missing_skills:parseList(record.missing_skills_semicolon),hard_constraint_failures:parseList(record.hard_constraint_failures_semicolon),reason:record.reason.trim(),reviewed_at:record.reviewed_at_iso||new Date().toISOString()};imported++}
for(const row of queue){const a=row.review_a,b=row.review_b;if(a?.relevance!==null&&b?.relevance!==null){if(a.annotator===b.annotator)throw new Error(`${row.annotation_id}: reviewers must be independent`);if(a.relevance===b.relevance){row.adjudication={required:false,adjudicator:null,final_relevance:a.relevance,final_reason:'independent_reviewer_agreement',adjudicated_at:new Date().toISOString()};row.label_status='double_review_agreed';row.formal_gold=true}else{row.adjudication={...row.adjudication,required:true};row.label_status='pending_adjudication';row.formal_gold=false}}}
fs.writeFileSync(queuePath,queue.map(row=>JSON.stringify(row)).join('\n')+'\n','utf8')
console.log(JSON.stringify({reviewer,csv:csvPath,imported,queue:queuePath},null,2))
