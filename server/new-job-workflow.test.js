import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, writeFileSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { createWorkflowStore } from './new-job-workflow.js'

test('draft, review, publish and rollback keep immutable history', () => {
  const dir=mkdtempSync(join(tmpdir(),'new-job-flow-')); const published=join(dir,'published.json'); const history=join(dir,'history.jsonl')
  writeFileSync(published,JSON.stringify({published_at:'2026-08-12',definitions:[{definition_id:'NJD-1',candidate_id:'C1',version:'1.0.0',algorithm_candidate_type:'early_watch',name:'A',responsibilities:['r'],required_skills:['s'],preferred_skills:['p'],typical_industry_scenarios:['x']}]}))
  const store=createWorkflowStore({workflowPath:join(dir,'workflow.json'),publishedPath:published,historyPath:history})
  const draft=store.createDraft('NJD-1','1.0.0',{name:'B',responsibilities:['r2'],required_skills:['s2'],preferred_skills:['p2'],typical_industry_scenarios:['x2'],job_direction:'backend',seniority:'senior',minimum_work_years:3,skill_groups:[{operator:'OR',skills:['Java','Golang']}],skill_minimum_levels:{Java:4},hard_constraints:[{field:'certificate',operator:'required'}]},'editor','update')
  assert.equal(draft.version,'1.0.1'); assert.equal(draft.status,'draft')
  assert.equal(draft.minimum_work_years,3); assert.equal(draft.skill_groups[0].operator,'OR'); assert.equal(draft.skill_minimum_levels.Java,4)
  store.transition('NJD-1','1.0.1','submit','editor','ready'); store.transition('NJD-1','1.0.1','approve','reviewer','evidence checked'); store.transition('NJD-1','1.0.1','publish','publisher','release')
  const rolled=store.rollback('NJD-1','1.0.0','publisher','restore baseline')
  assert.equal(rolled.version,'1.0.2'); assert.equal(rolled.rollback_target,'1.0.0')
  const state=store.load(); assert.equal(state.definitions[0].versions.length,3); assert.equal(state.definitions[0].versions[0].name,'A'); assert.equal(state.definitions[0].current_published_version,'1.0.2')
  assert.equal(readFileSync(history,'utf8').trim().split('\n').length,5)
})
