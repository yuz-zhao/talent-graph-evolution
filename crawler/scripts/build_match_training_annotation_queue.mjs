import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { assessJdRelevance } from '../../server/matching-utils.js'

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..')
const human=path.join(root,'crawler/data/gold/human/v1.1')
const output=path.join(root,'crawler/data/evaluation/match_training_annotation_queue_v1.jsonl')
const read=name=>fs.readFileSync(path.join(human,name),'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse)
const resumes=read('gold_resume_v1.1.jsonl').filter(row=>['development','validation'].includes(row.split))
const jds=read('gold_jd_v1.1.jsonl')
const calibration=new Set(read('calibration/human_match_calibration_v1.0.jsonl').map(row=>`${row.resume_id}|${row.jd_sample_id}`))
const stateStrength={demonstrated:4,claimed:3,mentioned:2,learning:1,target_only:0}

const queue=[]
for(const resume of resumes){
  for(const jd of jds){
    const key=`${resume.resume_id}|${jd.sample_id}`
    if(calibration.has(key))continue
    const skills=(resume.skills||[]).map(name=>({name,state:resume.skill_states?.[name]||'mentioned'}))
    const assessment=assessJdRelevance(skills,{...jd,jobDirection:jd.standard_job_name||jd.job_title},{candidate:{work_years:resume.work_years,target_direction:resume.target_job},targetDirection:resume.target_job})
    const evidenceStrength=assessment.decisions.filter(item=>item.evidence_matched).reduce((sum,item)=>sum+(stateStrength[resume.skill_states?.[item.name]]||2),0)
    const boundaryDistance=Math.min(Math.abs((assessment.effective_required_coverage??0)-40),Math.abs((assessment.effective_required_coverage??0)-75))
    const difficulty=assessment.direction_compatibility===0&&assessment.matched_skills.length?'cross_direction_transfer'
      : boundaryDistance<=15?'classification_boundary'
        : assessment.matched_skills.length&&assessment.missing_skills.length?'partial_skill_overlap'
          : assessment.matched_skills.length?'strong_overlap':'hard_negative'
    queue.push({
      schema_version:'1.0.0',task:'resume_job_matching_four_class',annotation_id:`TRAIN_${resume.resume_id}_${jd.sample_id}`,
      resume_id:resume.resume_id,jd_sample_id:jd.sample_id,resume_split:resume.split,training_split:resume.split,
      leakage_guard:{frozen_test_resume:false,existing_calibration_pair:false,formal_gold_label_in_payload:false},
      resume_view:{target_job:resume.target_job,highest_education:resume.highest_education,work_years:resume.work_years,skills:resume.skills,skill_states:resume.skill_states,projects_text:resume.projects_text},
      jd_view:{job_title:jd.job_title,standard_job_name:jd.standard_job_name,required_skills:jd.required_skills,bonus_skills:jd.bonus_skills,original_text:jd.original_text,source_url:jd.source_url},
      preannotation:{suggested_relevance:assessment.relevance,score:assessment.score,matched_skills:assessment.matched_skills,missing_skills:assessment.missing_skills,required_coverage:assessment.required_coverage,effective_required_coverage:assessment.effective_required_coverage,direction_compatibility:assessment.direction_compatibility,evidence_strength:evidenceStrength,difficulty},
      review_a:{annotator:null,relevance:null,direction_match:null,level_match:null,experience_match:null,matched_skills:null,missing_skills:null,hard_constraint_failures:null,reason:null,reviewed_at:null},
      review_b:{annotator:null,relevance:null,direction_match:null,level_match:null,experience_match:null,matched_skills:null,missing_skills:null,hard_constraint_failures:null,reason:null,reviewed_at:null},
      adjudication:{required:null,adjudicator:null,final_relevance:null,final_reason:null,adjudicated_at:null},
      label_status:'pending_independent_double_review',formal_gold:false,
    })
  }
}
queue.sort((a,b)=>a.preannotation.difficulty.localeCompare(b.preannotation.difficulty)||a.resume_id.localeCompare(b.resume_id)||a.jd_sample_id.localeCompare(b.jd_sample_id))
fs.writeFileSync(output,queue.map(row=>JSON.stringify(row)).join('\n')+'\n','utf8')
console.log(JSON.stringify({output,pairs:queue.length,resumes:new Set(queue.map(x=>x.resume_id)).size,jds:new Set(queue.map(x=>x.jd_sample_id)).size,difficulty:Object.fromEntries(Object.entries(Object.groupBy(queue,x=>x.preannotation.difficulty)).map(([key,rows])=>[key,rows.length])),frozen_test_resumes:queue.filter(x=>x.leakage_guard.frozen_test_resume).length},null,2))
