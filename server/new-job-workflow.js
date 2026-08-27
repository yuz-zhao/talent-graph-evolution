import { existsSync, readFileSync, renameSync, writeFileSync } from 'fs'
import { dirname, join } from 'path'
import { mkdirSync } from 'fs'
import { randomUUID } from 'crypto'

export const FIVE_FIELDS = ['name', 'responsibilities', 'required_skills', 'preferred_skills', 'typical_industry_scenarios']
export const MATCHING_FIELDS = ['job_direction', 'seniority', 'minimum_work_years', 'skill_groups', 'skill_minimum_levels', 'skill_minimum_years', 'hard_constraints']
const EDITABLE_STATES = new Set(['draft', 'rejected'])

const clone = value => JSON.parse(JSON.stringify(value))
const now = () => new Date().toISOString()
const versionParts = value => String(value || '0.0.0').split('.').map(x => Number(x) || 0)
const nextPatch = versions => {
  const latest = versions.map(v => versionParts(v.version)).sort((a,b) => b[0]-a[0] || b[1]-a[1] || b[2]-a[2])[0] || [1,0,-1]
  return `${latest[0]}.${latest[1]}.${latest[2] + 1}`
}
const validateFields = fields => {
  const normalized = {}
  for (const key of FIVE_FIELDS) {
    const value = fields?.[key]
    normalized[key] = key === 'name' ? String(value || '').trim() : (Array.isArray(value) ? value.map(x => String(x).trim()).filter(Boolean) : [])
    if (!normalized[key] || (Array.isArray(normalized[key]) && !normalized[key].length)) throw Object.assign(new Error(`五字段不完整：${key}`), { statusCode:400 })
  }
  for (const key of MATCHING_FIELDS) {
    if (fields?.[key] === undefined) continue
    const value = fields[key]
    if (key === 'minimum_work_years') normalized[key] = value === null || value === '' ? null : Math.max(0, Number(value))
    else if (['skill_groups','hard_constraints'].includes(key)) normalized[key] = Array.isArray(value) ? clone(value) : []
    else if (['skill_minimum_levels','skill_minimum_years'].includes(key)) normalized[key] = value && typeof value === 'object' && !Array.isArray(value) ? clone(value) : {}
    else normalized[key] = String(value || '').trim()
  }
  return normalized
}

export function createWorkflowStore({ workflowPath, publishedPath, historyPath }) {
  const atomicWrite = (path, value) => {
    mkdirSync(dirname(path), { recursive:true })
    const temp = join(dirname(path), `.${randomUUID()}.tmp`)
    writeFileSync(temp, JSON.stringify(value, null, 2), 'utf8')
    renameSync(temp, path)
  }
  const appendHistory = event => writeFileSync(historyPath, `${JSON.stringify(event)}\n`, { encoding:'utf8', flag:'a' })
  const initialState = () => {
    const source = JSON.parse(readFileSync(publishedPath, 'utf8'))
    const definitions = (source.definitions || []).map(item => ({
      definition_id:item.definition_id, candidate_id:item.candidate_id, algorithm_candidate_type:item.algorithm_candidate_type,
      current_published_version:item.version,
      versions:[{ ...clone(item), status:'published', created_at:source.published_at, updated_at:source.published_at, created_by:'initial_publication', review:null }],
    }))
    return { schema_version:'1.0.0', workflow:'draft_pending_review_approved_published', definitions, audit_events:[] }
  }
  const load = () => {
    if (!existsSync(workflowPath)) atomicWrite(workflowPath, initialState())
    return JSON.parse(readFileSync(workflowPath, 'utf8'))
  }
  const save = state => atomicWrite(workflowPath, state)
  const locate = (state, definitionId, version) => {
    const definition = state.definitions.find(x => x.definition_id === definitionId)
    if (!definition) throw Object.assign(new Error('岗位定义不存在'), { statusCode:404 })
    const item = definition.versions.find(x => x.version === version)
    if (!item) throw Object.assign(new Error('岗位版本不存在'), { statusCode:404 })
    return { definition, item }
  }
  const audit = (state, payload) => {
    const event = { event_id:`NJE-${randomUUID()}`, occurred_at:now(), ...payload }
    state.audit_events.push(event); appendHistory(event); return event
  }
  const updatePublishedArtifact = state => {
    const definitions = state.definitions.flatMap(definition => {
      const item = definition.versions.find(x => x.version === definition.current_published_version)
      if (!item) return []
      const copy = clone(item); delete copy.status; delete copy.created_at; delete copy.updated_at; delete copy.created_by; delete copy.review
      copy.publication_status = 'curated_submission_candidate'
      return [copy]
    })
    atomicWrite(publishedPath, { schema_version:'1.1.0', publication_version:`new_job_definitions_${new Date().toISOString().slice(0,10)}_workflow`, published_at:now(), source_algorithm:'new_job_discovery_v3.0.0', definitions })
  }
  return {
    load,
    createDraft(definitionId, baseVersion, fields, actor='admin_ui', reason='人工优化') {
      const state=load(); const definition=state.definitions.find(x=>x.definition_id===definitionId)
      if(!definition) throw Object.assign(new Error('岗位定义不存在'),{statusCode:404})
      const base=definition.versions.find(x=>x.version===(baseVersion||definition.current_published_version))
      if(!base) throw Object.assign(new Error('基础版本不存在'),{statusCode:404})
      const version=nextPatch(definition.versions); const values=validateFields(fields || base)
      const item={...clone(base),...values,version,status:'draft',created_at:now(),updated_at:now(),created_by:actor,base_version:base.version,change_reason:reason,review:null}
      definition.versions.push(item); audit(state,{definition_id:definitionId,version,event:'draft_created',actor,reason,from_version:base.version}); save(state); return clone(item)
    },
    edit(definitionId, version, fields, actor='admin_ui', reason='编辑草稿') {
      const state=load(); const {item}=locate(state,definitionId,version)
      if(!EDITABLE_STATES.has(item.status)) throw Object.assign(new Error('只有草稿或已驳回版本可以编辑'),{statusCode:409})
      Object.assign(item,validateFields(fields),{status:'draft',updated_at:now(),change_reason:reason,review:null})
      audit(state,{definition_id:definitionId,version,event:'draft_edited',actor,reason}); save(state); return clone(item)
    },
    transition(definitionId, version, action, actor='admin_ui', reason='') {
      const state=load(); const {definition,item}=locate(state,definitionId,version)
      const allowed={submit:['draft','pending_review'],approve:['pending_review','approved'],reject:['pending_review','rejected'],publish:['approved','published']}
      if(!allowed[action]?.includes(item.status)) throw Object.assign(new Error(`状态 ${item.status} 不允许执行 ${action}`),{statusCode:409})
      const target={submit:'pending_review',approve:'approved',reject:'rejected',publish:'published'}[action]
      if(['approve','reject','publish'].includes(action) && !reason.trim()) throw Object.assign(new Error('审核、驳回或发布必须填写原因'),{statusCode:400})
      item.status=target; item.updated_at=now(); item.review={action,actor,reason,reviewed_at:now()}
      if(action==='publish') { definition.current_published_version=version; updatePublishedArtifact(state) }
      audit(state,{definition_id:definitionId,version,event:action,actor,reason,status_after:target}); save(state); return clone(item)
    },
    rollback(definitionId, targetVersion, actor='admin_ui', reason='') {
      if(!reason.trim()) throw Object.assign(new Error('回滚必须填写原因'),{statusCode:400})
      const state=load(); const {definition,item:target}=locate(state,definitionId,targetVersion); const from=definition.current_published_version
      const version=nextPatch(definition.versions); const copy={...clone(target),version,status:'published',created_at:now(),updated_at:now(),created_by:actor,base_version:from,rollback_from:from,rollback_target:targetVersion,change_reason:reason,review:{action:'rollback',actor,reason,reviewed_at:now()}}
      definition.versions.push(copy); definition.current_published_version=version
      audit(state,{definition_id:definitionId,version,event:'rollback_published',actor,reason,from_version:from,target_version:targetVersion}); updatePublishedArtifact(state); save(state); return clone(copy)
    },
  }
}
