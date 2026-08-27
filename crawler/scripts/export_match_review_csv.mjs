import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const input=path.join(root,'crawler/data/evaluation/match_training_annotation_queue_v1.jsonl')
const rows=fs.readFileSync(input,'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse)
const quote=value=>`"${String(value??'').replaceAll('"','""').replaceAll('\r',' ').replaceAll('\n',' \\n ')}"`
const headers=['annotation_id','resume_id','jd_sample_id','target_job','resume_work_years','resume_skills','resume_projects','job_title','standard_job_name','required_skills','bonus_skills','jd_text','relevance_0_3','direction_match_yes_no_unknown','level_match_yes_no_unknown','experience_match_yes_no_unknown','matched_skills_semicolon','missing_skills_semicolon','hard_constraint_failures_semicolon','reason','annotator','reviewed_at_iso']
for(const reviewer of ['a','b']){
  const output=path.join(root,`crawler/data/evaluation/match_training_review_${reviewer}_v1.csv`)
  const lines=[headers.map(quote).join(',')]
  for(const row of rows)lines.push([
    row.annotation_id,row.resume_id,row.jd_sample_id,row.resume_view.target_job,row.resume_view.work_years,
    (row.resume_view.skills||[]).join(';'),row.resume_view.projects_text,row.jd_view.job_title,row.jd_view.standard_job_name,
    (row.jd_view.required_skills||[]).join(';'),(row.jd_view.bonus_skills||[]).join(';'),row.jd_view.original_text,
    '','','','','','','','','','',
  ].map(quote).join(','))
  fs.writeFileSync(output,'\uFEFF'+lines.join('\r\n')+'\r\n','utf8')
  console.log(JSON.stringify({reviewer,output,rows:rows.length}))
}
