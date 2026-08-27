import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const input=process.argv[2]?path.resolve(root,process.argv[2]):path.join(root,'crawler/data/evaluation/match_training_annotation_queue_v1.jsonl')
const rows=fs.readFileSync(input,'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse)
const errors=[],ids=new Set(),testResumeIds=new Set()
const goldResumes=fs.readFileSync(path.join(root,'crawler/data/gold/human/v1.1/gold_resume_v1.1.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse)
goldResumes.filter(row=>row.split==='test').forEach(row=>testResumeIds.add(row.resume_id))
let complete=0,agreed=0,needsAdjudication=0,finalized=0
for(const [index,row] of rows.entries()){
  if(ids.has(row.annotation_id))errors.push(`duplicate annotation_id: ${row.annotation_id}`);ids.add(row.annotation_id)
  if(testResumeIds.has(row.resume_id))errors.push(`frozen test resume leaked at row ${index+1}: ${row.resume_id}`)
  const a=row.review_a||{},b=row.review_b||{},aDone=[a.annotator,a.relevance,a.reason].every(value=>value!==null&&value!==''),bDone=[b.annotator,b.relevance,b.reason].every(value=>value!==null&&value!=='')
  if(aDone&&bDone){complete++;if(a.annotator===b.annotator)errors.push(`independent reviewers required: ${row.annotation_id}`);if(a.relevance===b.relevance)agreed++;else{needsAdjudication++;if(row.adjudication?.final_relevance!==null&&row.adjudication?.adjudicator&&row.adjudication?.final_reason)finalized++}}
  for(const [name,review] of [['review_a',a],['review_b',b]])if(review.relevance!==null&&![0,1,2,3].includes(Number(review.relevance)))errors.push(`${row.annotation_id} ${name} relevance must be 0..3`)
}
console.log(JSON.stringify({input,rows:rows.length,double_review_complete:complete,direct_agreement:agreed,needs_adjudication:needsAdjudication,adjudicated:finalized,ready_for_training:agreed+finalized,errors:errors.slice(0,100),passed:errors.length===0},null,2))
if(errors.length)process.exitCode=1
