import { createHash } from 'crypto'
import { existsSync, readFileSync, writeFileSync } from 'fs'
import { dirname, join, resolve } from 'path'
import { fileURLToPath } from 'url'
import { extractPdf } from '../../server/document-extractor.js'
import { parseResumeBlocks } from '../../server/resume-parser.js'

const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..')
const goldDir=join(root,'crawler/data/gold/human/v1.1')
const reportPath=join(root,'crawler/data/reports/resume_parser_frozen_test_evaluation.json')
const rows=readFileSync(join(goldDir,'gold_resume_v1.1.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse).filter(x=>x.split==='test')
const rawOntology=JSON.parse(readFileSync(join(root,'crawler/data/gold/reference/skill_ontology.json'),'utf8'))
const ontology=Object.entries(rawOntology).map(([name,value])=>({name,category:value.category,keywords:[name,...(value.aliases||[])]}))
const norm=x=>String(x||'').trim().toLowerCase()
const stripCandidatePrefix=x=>String(x||'').replace(/^待新增:/i,'').trim()
const ontologyNames=new Set(Object.keys(rawOntology).map(norm))
let tp=0,fp=0,fn=0
let candidateGoldCount=0,candidateMentionedCount=0
const samples=[]
for(const row of rows){
  const pdf=resolve(root,row.pdf_path)
  const extraction=await extractPdf(pdf)
  const parsed=parseResumeBlocks(extraction.blocks,ontology)
  const rawGold=(row.skills||[]).map(stripCandidatePrefix)
  const inScopeGold=rawGold.filter(x=>ontologyNames.has(norm(x)))
  const outOfScopeGold=rawGold.filter(x=>!ontologyNames.has(norm(x)))
  const gold=new Set(inScopeGold.map(norm)),pred=new Set(parsed.skills.map(x=>norm(x.standard_name)))
  const documentText=extraction.blocks.map(x=>String(x.text||'').toLowerCase()).join('\n')
  const mentionedCandidates=outOfScopeGold.filter(x=>documentText.includes(String(x).toLowerCase()))
  candidateGoldCount+=outOfScopeGold.length;candidateMentionedCount+=mentionedCandidates.length
  const hit=[...gold].filter(x=>pred.has(x)),falsePositive=[...pred].filter(x=>!gold.has(x)),missed=[...gold].filter(x=>!pred.has(x))
  tp+=hit.length;fp+=falsePositive.length;fn+=missed.length
  samples.push({resume_id:row.resume_id,pdf_sha256:createHash('sha256').update(readFileSync(pdf)).digest('hex'),extraction_method:extraction.extraction_method,standardized_gold_count:gold.size,out_of_ontology_candidate_count:outOfScopeGold.length,predicted_count:pred.size,tp:hit.length,fp:falsePositive.length,fn:missed.length,false_positive:falsePositive,missed,out_of_ontology_candidates:outOfScopeGold,candidate_surface_mentions:mentionedCandidates})
}
const precision=tp/(tp+fp||1),recall=tp/(tp+fn||1),f1=2*precision*recall/(precision+recall||1)
const evidenceDir=join(goldDir,'evidence/annotators')
const evidenceFiles=['TalentGraph_邓佑杰_30简历_预填复核.xlsx','TalentGraph_郭炫宇_30简历_预填复核.xlsx','TalentGraph_胡苗苗_30简历_预填复核.xlsx','TalentGraph_徐赠贺_30简历_预填复核.xlsx','TalentGraph_余昭_30简历仲裁_400组匹配.xlsx']
const evidencePresent=evidenceFiles.every(name=>existsSync(join(evidenceDir,name)))
const report={schema_version:'1.1.0',evaluation_target:'resume_parser_v2',evaluation_scope:'standardized_skill_extraction',scope_policy:'Gold skills present in the frozen production ontology are scored. Gold items marked 待新增 or otherwise absent from that ontology are reported separately as candidate discovery coverage and never counted as parser false negatives.',gold_version:'gold_v1.1',split:'test',frozen_manifest:true,sample_count:rows.length,actual_pdf_parser_run:true,ai_reference_self_consistency:false,human_evidence:{four_independent_review_workbooks:true,adjudication_workbook:true,evidence_files_present:evidencePresent},metrics:{precision,recall,f1,tp,fp,fn,threshold:0.9,passed:f1>=0.9},candidate_discovery_diagnostic:{gold_count:candidateGoldCount,surface_mentioned_count:candidateMentionedCount,surface_mention_recall:candidateGoldCount?candidateMentionedCount/candidateGoldCount:1,claim_eligible:false},claim_eligible:evidencePresent&&f1>=0.9,samples}
writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n','utf8')
console.log(JSON.stringify(report,null,2))
