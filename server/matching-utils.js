export function weightedJaccard(left, right, weights = {}) {
  const a = new Set((left || []).map(value => String(value).trim().toLowerCase()).filter(Boolean))
  const b = new Set((right || []).map(value => String(value).trim().toLowerCase()).filter(Boolean))
  const union = new Set([...a, ...b])
  if (!union.size) return 0

  let intersectionWeight = 0
  let unionWeight = 0
  for (const skill of union) {
    const weight = Number(weights[skill] || 1)
    unionWeight += weight
    if (a.has(skill) && b.has(skill)) intersectionWeight += weight
  }
  return unionWeight > 0 ? intersectionWeight / unionWeight : 0
}

export function fuseMatchScore({ skillScore, semanticScore, cfScore, feedbackAdjust = 0, weights }) {
  const raw = Number(skillScore || 0) * weights.skill
    + Number(semanticScore || 0) * weights.semantic
    + Number(cfScore || 0) * weights.cf
    + Number(feedbackAdjust || 0)
  return Math.min(100, Math.max(0, Math.round(raw)))
}

/**
 * 四档匹配等级。`concreteTier` 是 concrete-JD 四档判定（0-3），优先于连续分；
 * 没有 tier 时按分带划分，把「不匹配」与「弱匹配」拆开，而不是压成同一档。
 */
export function matchLevel(score, concreteTier) {
  if (Number.isInteger(concreteTier) && concreteTier >= 0 && concreteTier <= 3) {
    return ['none', 'low', 'medium', 'high'][concreteTier]
  }
  if (score >= 70) return 'high'
  if (score >= 40) return 'medium'
  if (score >= 10) return 'low'
  return 'none'
}

export const MATCHING_FUSION_CONFIG = Object.freeze({
  version: 'matching_fusion_v8.1.1',
  weights: Object.freeze({ required:.40, semantic:.20, kg:.15, project:.10, preference:.05, cf:.10, gnn:.00 }),
  thresholds: Object.freeze({ high:70, medium:40, low:10 }),
  calibration: Object.freeze({ status:'rule_gated_unvalidated', evidence:'direction_and_direct_skill_guards', frozen_test_required:true }),
})

export function calibratedMatchScore(rawScore, evidence = {}) {
  let score = Math.min(100, Math.max(0, Math.round(Number(rawScore || 0))))
  const direction = evidence.directionPreference
  const matchedSkillCount = Number(evidence.matchedSkillCount || 0)
  // A known cross-family role conflict is decisive evidence: generic skills
  // such as Python must not turn a marketing-vs-engineering pair into a match.
  if (direction === 0) return matchedSkillCount > 0
    ? { score:Math.min(score,39), adjustment:'direction_conflict_low_match_cap' }
    : { score:0, adjustment:'direction_conflict_no_evidence' }
  // With no directly matched skill, semantic/graph proximity can keep a pair
  // discoverable but cannot promote it beyond the low-match band.
  if (matchedSkillCount === 0 && score >= 40) return { score:39, adjustment:'no_direct_skill_cap' }
  const maximumScore = Number(evidence.maximumScore)
  if (Number.isFinite(maximumScore) && score > maximumScore) return { score:Math.max(0, Math.min(100, Math.round(maximumScore))), adjustment:evidence.maximumReason || 'evidence_constraint_cap' }
  return { score, adjustment:null }
}

export function normalizedWeightedScore(dimensions, weights) {
  let weighted = 0
  let availableWeight = 0
  const available = {}
  for (const [name, weight] of Object.entries(weights || {})) {
    const value = dimensions?.[name]
    const isAvailable = value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))
    available[name] = isAvailable
    if (!isAvailable || Number(weight) <= 0) continue
    weighted += Number(value) * Number(weight)
    availableWeight += Number(weight)
  }
  return {
    score: availableWeight > 0 ? Math.round(weighted / availableWeight) : 0,
    available,
    availableWeight: Math.round(availableWeight * 1000) / 1000,
  }
}

const JOB_DIRECTION_FAMILIES = {
  ai: ['人工智能', '机器学习', '深度学习', '算法工程师', '算法研究', '自然语言', '计算机视觉', '大模型', 'nlp', 'machine learning', 'deep learning'],
  backend: ['后端', '服务端', 'java开发', 'java工程师', 'golang', 'go开发', 'node.js开发'],
  frontend: ['前端', 'web前端', 'javascript开发', 'react开发', 'vue开发'],
  fullstack: ['全栈', 'full stack', 'fullstack'],
  data: ['数据工程', '数据开发', '数据仓库', '数据分析', '商业智能', '大数据', 'data engineer', 'data analyst', 'business intelligence'],
  devops: ['运维', 'devops', 'sre', '云原生', '云平台', '平台工程'],
  embedded: ['嵌入式', '物联网', '单片机', '硬件工程'],
  product: ['产品经理', '产品运营'],
  marketing: ['市场营销', '市场推广', '品牌营销'],
  sales: ['销售', '客户经理', '商务拓展'],
}

function directionFamilies(value) {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return new Set()
  return new Set(Object.entries(JOB_DIRECTION_FAMILIES)
    .filter(([, keywords]) => keywords.some(keyword => normalized.includes(keyword)))
    .map(([family]) => family))
}

export function jobDirectionCompatibility(targetDirection, jobName) {
  const target = String(targetDirection || '').trim().toLowerCase()
  const job = String(jobName || '').trim().toLowerCase()
  if (!target || !job) return null
  if (target.includes(job) || job.includes(target)) return 100
  const targetFamilies = directionFamilies(target)
  const jobFamilies = directionFamilies(job)
  if (!targetFamilies.size || !jobFamilies.size) return null
  if ([...targetFamilies].some(family => jobFamilies.has(family))) return 100
  const fullstackCompatible = (targetFamilies.has('fullstack') && [...jobFamilies].some(x => x === 'frontend' || x === 'backend'))
    || (jobFamilies.has('fullstack') && [...targetFamilies].some(x => x === 'frontend' || x === 'backend'))
  return fullstackCompatible ? 85 : 0
}

/**
 * 从岗位群聚合的 skill_requirements 中按 jobId 分组，找出与用户技能重叠
 * 最高的单个岗位的覆盖度。用于召回阶段的精准评估。
 */
export function bestPerJobCoverage(skillRequirements, userSkillSet) {
  if (!skillRequirements || !skillRequirements.length || !userSkillSet || !userSkillSet.size) return null
  const byJob = new Map()
  for (const req of skillRequirements) {
    const jid = req.jobId || req.jobName || '__unknown__'
    if (!byJob.has(jid)) byJob.set(jid, { skills: new Set(), total: 0 })
    const entry = byJob.get(jid)
    const name = String(req.skillName || req.name || '').toLowerCase().trim()
    if (name && !entry.skills.has(name)) {
      entry.skills.add(name)
      entry.total++
    }
  }
  let bestOverlap = 0, bestTotal = 1
  for (const entry of byJob.values()) {
    const overlap = [...entry.skills].filter(s => userSkillSet.has(s)).length
    if (entry.total > 0 && overlap / entry.total > bestOverlap / bestTotal) {
      bestOverlap = overlap
      bestTotal = entry.total
    }
  }
  return { overlap: bestOverlap, total: bestTotal, coverage: bestTotal > 0 ? bestOverlap / bestTotal : 0 }
}

export function normalizedSkillName(value) {
  return String(value || '').trim().toLowerCase()
}

const SENIORITY_RANK = { intern:0, internship:0, junior:1, entry:1, mid:2, intermediate:2, senior:3, lead:4, principal:4, expert:4, manager:4, director:5, '实习':0, '初级':1, '中级':2, '高级':3, '资深':4, '专家':4, '经理':4, '总监':5 }

export function parseExperienceYears(value) {
  if (value !== '' && value !== null && value !== undefined && Number.isFinite(Number(value))) return Math.max(0, Number(value))
  const text = String(value || '')
  const range = text.match(/(\d+(?:\.\d+)?)\s*(?:-|~|至|到)\s*(\d+(?:\.\d+)?)\s*(?:年|years?)/i)
  if (range) return Number(range[1])
  const match = text.match(/(\d+(?:\.\d+)?)\s*(?:年|years?)/i)
  return match ? Number(match[1]) : null
}

export function seniorityRank(value) {
  const text = String(value || '').trim().toLowerCase()
  if (!text) return null
  const hit = Object.entries(SENIORITY_RANK).find(([key]) => text.includes(key))
  return hit ? hit[1] : null
}

export function diagnoseJdSkillMatch(userSkills = [], jd = {}, options = {}) {
  const possessedStates = new Set(options.possessedStates || ['demonstrated', 'claimed', 'mentioned'])
  const aliases = options.aliases instanceof Map ? options.aliases : new Map()
  const possessed = new Set(), skillProfiles = new Map()
  for (const skill of userSkills || []) {
    const name = normalizedSkillName(typeof skill === 'string' ? skill : (skill.standard_name || skill.standardName || skill.name))
    const state = typeof skill === 'string' ? 'demonstrated' : String(skill.state || skill.skill_state || skill.status || 'demonstrated').toLowerCase()
    if (name && possessedStates.has(state)) {
      possessed.add(name)
      if (typeof skill !== 'string') skillProfiles.set(name, skill)
    }
  }
  const requirements = [
    ...(jd.required_skills || jd.requiredSkills || []).map(name => ({ name, type:'required' })),
    ...(jd.bonus_skills || jd.bonusSkills || jd.preferred_skills || jd.preferredSkills || []).map(name => ({ name, type:'bonus' })),
    ...(jd.skill_groups || jd.skillGroups || []).flatMap(group => (group.skills || []).map(name => ({ name, type:group.required === false ? 'bonus' : 'required' }))),
  ]
  const seen = new Set()
  const decisions = []
  for (const requirement of requirements) {
    const normalized = normalizedSkillName(requirement.name)
    if (!normalized || seen.has(normalized)) continue
    seen.add(normalized)
    const skillAliases = aliases.get(requirement.name) || aliases.get(normalized) || []
    const matchedName = possessed.has(normalized) ? normalized : [...skillAliases].map(normalizedSkillName).find(alias => possessed.has(alias))
    const profile = skillProfiles.get(matchedName)
    const minimumLevel = Number(jd.skill_minimum_levels?.[requirement.name] || jd.skillMinimumLevels?.[requirement.name] || 0)
    const minimumYears = Number(jd.skill_minimum_years?.[requirement.name] || jd.skillMinimumYears?.[requirement.name] || 0)
    const level = Number(profile?.proficiency_level || profile?.level || 0)
    const years = Number(profile?.years_experience || profile?.years || 0)
    const evidenceMatched = Boolean(matchedName)
    const matched = evidenceMatched && (!minimumLevel || level >= minimumLevel) && (!minimumYears || years >= minimumYears)
    decisions.push({ name:requirement.name, normalized_name:normalized, requirement_type:requirement.type, matched, evidence_matched:evidenceMatched, proficiency_level:level || null, minimum_level:minimumLevel || null, years_experience:years || null, minimum_years:minimumYears || null })
  }
  const group_decisions = (jd.skill_groups || jd.skillGroups || []).map((group,index) => {
    const members = (group.skills || []).map(normalizedSkillName).filter(Boolean)
    const matchedMembers = decisions.filter(item => members.includes(item.normalized_name) && item.matched).map(item => item.name)
    const operator = String(group.operator || 'OR').toUpperCase()
    const minimumMatch = operator === 'AND' ? members.length : Math.max(1, Number(group.minimum_match || group.minimumMatch || 1))
    return { group_id:group.id || `group_${index + 1}`, operator, skills:group.skills || [], minimum_match:minimumMatch, matched_skills:matchedMembers, satisfied:matchedMembers.length >= minimumMatch, required:group.required !== false }
  })
  const required = decisions.filter(item => item.requirement_type === 'required')
  const bonus = decisions.filter(item => item.requirement_type === 'bonus')
  const coverage = items => items.length ? Math.round(items.filter(item => item.matched).length / items.length * 100) : null
  const groupedSkills = new Set(group_decisions.flatMap(group => group.skills.map(normalizedSkillName)))
  const standaloneRequired = required.filter(item => !groupedSkills.has(item.normalized_name))
  const requiredUnits = [...standaloneRequired.map(item => item.matched), ...group_decisions.filter(group => group.required).map(group => group.satisfied)]
  return {
    decisions,
    matched_skills:decisions.filter(item => item.matched).map(item => item.name),
    missing_skills:decisions.filter(item => !item.matched).map(item => item.name),
    required_coverage:coverage(required),
    effective_required_coverage:requiredUnits.length ? Math.round(requiredUnits.filter(Boolean).length / requiredUnits.length * 100) : coverage(required),
    bonus_coverage:coverage(bonus),
    decision_count:decisions.length,
    group_decisions,
    required_groups_satisfied:group_decisions.filter(group => group.required).every(group => group.satisfied),
  }
}

export function evaluateJdConstraints(candidate = {}, jd = {}) {
  const candidateYears = parseExperienceYears(candidate.work_years ?? candidate.workYears)
  const minimumYears = parseExperienceYears(jd.minimum_work_years ?? jd.minimumWorkYears ?? jd.experience)
  const candidateSeniority = seniorityRank(candidate.seniority || candidate.current_seniority)
  const requiredSeniority = seniorityRank(jd.seniority || jd.required_seniority)
  const failures = []
  if (minimumYears !== null && candidateYears !== null && candidateYears < minimumYears) failures.push({type:'work_experience',required:minimumYears,actual:candidateYears})
  if (requiredSeniority !== null && candidateSeniority !== null && candidateSeniority < requiredSeniority - 1) failures.push({type:'seniority',required:requiredSeniority,actual:candidateSeniority})
  for (const constraint of jd.hard_constraints || jd.hardConstraints || []) {
    const actual = candidate[constraint.field]
    if (constraint.operator === 'required' && !actual) failures.push({type:constraint.field,required:constraint.value ?? true,actual:null})
    if (constraint.operator === 'equals' && normalizedSkillName(actual) !== normalizedSkillName(constraint.value)) failures.push({type:constraint.field,required:constraint.value,actual})
    if (constraint.operator === 'minimum' && Number(actual) < Number(constraint.value)) failures.push({type:constraint.field,required:constraint.value,actual})
  }
  return { passed:failures.length === 0, failures, candidate_years:candidateYears, minimum_years:minimumYears, candidate_seniority:candidateSeniority, required_seniority:requiredSeniority }
}

export function assessJdRelevance(userSkills = [], jd = {}, options = {}) {
  const diagnosis = diagnoseJdSkillMatch(userSkills, jd, options)
  const constraints = evaluateJdConstraints(options.candidate || {}, jd)
  const requiredCoverage = diagnosis.effective_required_coverage
  const matchedCount = diagnosis.matched_skills.length
  // Fixed semantic bands: substantial core coverage, partial core coverage,
  // isolated transferable evidence, and no direct evidence. They are declared
  // independently of the frozen test labels.
  let relevance = 0
  if (requiredCoverage !== null && requiredCoverage >= 75) relevance = 3
  else if (requiredCoverage !== null && requiredCoverage >= 40) relevance = 2
  else if (matchedCount > 0) relevance = 1
  const direction = jobDirectionCompatibility(options.targetDirection || options.candidate?.target_direction, jd.job_direction || jd.jobDirection || jd.job_title || jd.jobTitle)
  // Direction dictionaries are useful for ambiguous partial matches, but a
  // name-level family mismatch must not override substantial direct evidence.
  if (direction === 0 && relevance === 2) relevance = 1
  if (!diagnosis.required_groups_satisfied || !constraints.passed) relevance = Math.min(relevance, 1)
  const score = relevance === 3
    ? Math.round(70 + (requiredCoverage - 75) * 1.2)
    : relevance === 2
      ? Math.round(40 + (requiredCoverage - 40) / 35 * 29)
      : relevance === 1 ? Math.min(39, 15 + matchedCount * 8) : 0
  return { ...diagnosis, constraints, direction_compatibility:direction, relevance, score:Math.max(0, Math.min(100, relevance <= 1 ? Math.min(score, 39) : score)), method:'concrete_jd_evidence_constraints_v2' }
}

export function bestConcreteJobMatch(skillRequirements = [], userSkillSet = new Set(), options = {}) {
  const byJob = new Map()
  for (const requirement of skillRequirements || []) {
    const jobId = requirement.jobId || requirement.jobName || '__unknown__'
    if (!byJob.has(jobId)) byJob.set(jobId, [])
    byJob.get(jobId).push(requirement)
  }
  let best = null
  for (const [jobId, requirements] of byJob) {
    const requiredSkills = requirements.filter(item => String(item.requirementType || '').toLowerCase() === 'required').map(item => item.skillName || item.name)
    const bonusSkills = requirements.filter(item => String(item.requirementType || '').toLowerCase() !== 'required').map(item => item.skillName || item.name)
    const diagnosis = diagnoseJdSkillMatch([...userSkillSet], { requiredSkills, bonusSkills }, options)
    const requiredCoverage = diagnosis.required_coverage ?? diagnosis.bonus_coverage ?? 0
    const bonusCoverage = diagnosis.bonus_coverage ?? requiredCoverage
    const score = requiredCoverage * .8 + bonusCoverage * .2
    if (!best || score > best.selection_score || (score === best.selection_score && diagnosis.decision_count > best.diagnosis.decision_count)) {
      best = { jobId, requirements, diagnosis, selection_score:score }
    }
  }
  return best
}

export function recallCandidates(candidates, context = {}, options = {}) {
  const userSkills = new Set((context.skills || []).map(x => String(x).toLowerCase()))
  const direction = String(context.direction || '').trim().toLowerCase()
  const industry = String(context.industry || '').trim().toLowerCase()
  const limit = Math.max(1, Number(options.limit || 60))
  const minimum = Math.max(1, Math.min(limit, Number(options.minimum || 20)))
  const ranked = (candidates || []).map(candidate => {
    // per-job 覆盖度：在岗位群内按单个岗位匹配，取最佳岗位的覆盖度
    const perJob = userSkills.size ? bestPerJobCoverage(candidate.skillRequirements, userSkills) : null
    const candidateSkillCoverage = perJob ? perJob.coverage : (
      userSkills.size ? (candidate.skills || []).filter(x => userSkills.has(String(x).toLowerCase())).length / Math.max(1, (candidate.skills || []).length) : 0
    )
    const name = String(candidate.name || '').toLowerCase()
    const industries = (candidate.industries || []).filter(Boolean).map(x => String(x).toLowerCase())
    const directionScore = jobDirectionCompatibility(direction, name)
    const directionHit = directionScore !== null && directionScore >= 70
    const directionConflict = directionScore === 0
    const industryHit = industry.length >= 2 && industries.some(x => x.includes(industry) || industry.includes(x))
    const recallScore = candidateSkillCoverage * .7 + (directionScore !== null ? directionScore / 100 * .2 : 0) + (industryHit ? .1 : 0)
    return { ...candidate, recallScore, candidateSkillCoverage, directionScore, recallReasons: [perJob ? 'per_job_coverage' : null, (candidateSkillCoverage > 0 && !perJob) ? 'candidate_job_skill_coverage' : null, directionHit ? 'target_direction' : null, directionConflict ? 'direction_conflict' : null, industryHit ? 'target_industry' : null].filter(Boolean) }
  }).sort((a, b) => b.recallScore - a.recallScore || Number(b.jdCount || 0) - Number(a.jdCount || 0))
  const positive = ranked.filter(x => x.recallScore > 0)
  const selected = positive.length >= minimum ? positive.slice(0, limit) : ranked.slice(0, Math.min(limit, minimum))
  return { candidates: selected, total: ranked.length, recalled: selected.length, positive: positive.length, fallback: positive.length < minimum ? 'minimum_candidate_protection' : null }
}

export function skillRequirementWeight(requirement = {}, corpus = {}, now = new Date()) {
  const typeWeights = { required: 1, preferred: .6, bonus: .6, mentioned: .35 }
  const type = String(requirement.requirementType || 'mentioned').toLowerCase()
  const typeWeight = typeWeights[type] || typeWeights.mentioned
  const evidenceConfidence = Math.max(0, Math.min(1, Number(requirement.confidence ?? .5)))
  const totalJobs = Math.max(1, Number(corpus.totalJobs || 1))
  const documentFrequency = Math.max(0, Number(corpus.documentFrequency || 0))
  const idf = Math.log((totalJobs + 1) / (documentFrequency + 1)) + 1
  const maxIdf = Math.log(totalJobs + 1) + 1
  const discriminativeIdf = Math.max(.2, Math.min(1, idf / maxIdf))
  const observed = requirement.observedAt ? new Date(requirement.observedAt) : null
  const ageDays = observed && Number.isFinite(observed.getTime()) ? Math.max(0, (now.getTime() - observed.getTime()) / 86400000) : null
  const recencyWeight = ageDays === null ? .75 : Math.max(.5, Math.pow(.5, ageDays / 365))
  return { weight:typeWeight * evidenceConfidence * discriminativeIdf * recencyWeight, factors:{ requirementType:type, typeWeight, evidenceConfidence, discriminativeIdf, recencyWeight, documentFrequency, totalJobs } }
}

export function weightedSkillCoverage(requirements, matchedSkills, corpusStats = {}, now = new Date()) {
  const matched = new Set((matchedSkills || []).map(x => String(x).toLowerCase()))
  const bySkill = new Map()
  for (const requirement of requirements || []) {
    const name = String(requirement.name || '').trim()
    if (!name) continue
    const weighted = skillRequirementWeight(requirement, { totalJobs:corpusStats.totalJobs, documentFrequency:corpusStats.documentFrequency?.[name] || 0 }, now)
    const current = bySkill.get(name)
    if (!current || weighted.weight > current.weight) bySkill.set(name, {
      name,
      evidenceText:requirement.evidenceText || null,
      sourceUrl:requirement.sourceUrl || null,
      observedAt:requirement.observedAt || null,
      ...weighted,
    })
  }
  const details = [...bySkill.values()].map(item => ({ ...item, matched:matched.has(item.name.toLowerCase()) }))
  const totalWeight = details.reduce((sum, item) => sum + item.weight, 0)
  const matchedWeight = details.filter(x => x.matched).reduce((sum, item) => sum + item.weight, 0)
  const coverage = totalWeight > 0 ? Math.round(matchedWeight / totalWeight * 100) : 0
  const coverageFor = types => {
    const subset = details.filter(x => types.includes(x.factors.requirementType))
    const denominator = subset.reduce((sum, x) => sum + x.weight, 0)
    return denominator > 0 ? Math.round(subset.filter(x => x.matched).reduce((sum, x) => sum + x.weight, 0) / denominator * 100) : null
  }
  return { coverage, requiredCoverage:coverageFor(['required']), preferredCoverage:coverageFor(['preferred','bonus']), matchedWeight, totalWeight, details }
}

export function representativeClusterRequirements(requirements = [], jobCount = 0, options = {}) {
  const minimumRatio = Number(options.minimumRatio ?? .15)
  const minSkills = Math.max(1, Number(options.minSkills ?? 3))
  const maxSkills = Math.max(minSkills, Number(options.maxSkills ?? 20))
  const typeRank = type => ({ required:4, preferred:3, bonus:2, mentioned:1 })[String(type || 'mentioned').toLowerCase()] || 1
  const bySkill = new Map()
  for (const requirement of requirements) {
    const name = String(requirement.skillName || requirement.name || '').trim()
    if (!name) continue
    if (!bySkill.has(name)) bySkill.set(name, { name, jobIds:new Set(), requirements:[] })
    const evidence = bySkill.get(name)
    evidence.jobIds.add(requirement.jobId || '__unknown__')
    evidence.requirements.push(requirement)
  }
  const minimumFrequency = Math.max(2, Math.ceil(Math.max(1, Number(jobCount || 0)) * minimumRatio))
  const ranked = [...bySkill.values()].map(evidence => {
    const strongest = [...evidence.requirements].sort((a,b) => typeRank(b.requirementType) - typeRank(a.requirementType)
      || Number(b.confidence||0) - Number(a.confidence||0))[0]
    const type = String(strongest?.requirementType || 'mentioned').toLowerCase()
    const confidence = Number(strongest?.confidence || 0)
    return { ...evidence, strongest, frequency:evidence.jobIds.size, strongSingleEvidence:confidence >= .8 && ['required','preferred'].includes(type) }
  }).sort((a,b) => b.frequency - a.frequency || Number(b.strongest?.confidence||0) - Number(a.strongest?.confidence||0))
  let selected = ranked.filter(evidence => evidence.frequency >= minimumFrequency || evidence.strongSingleEvidence)
  if (selected.length < minSkills) selected = ranked.slice(0, Math.min(maxSkills, ranked.length))
  return selected.slice(0, maxSkills).map(evidence => ({
    name:evidence.name,
    requirementType:evidence.strongest?.requirementType,
    confidence:evidence.strongest?.confidence,
    observedAt:evidence.strongest?.observedAt,
    evidenceText:evidence.strongest?.evidenceText,
    sourceUrl:evidence.strongest?.sourceUrl,
    evidenceSource:evidence.strongest?.evidenceSource || null,
    frequency:evidence.frequency,
    groupJobCount:Number(jobCount || 0),
  }))
}

const DEGREE_RANK = { '中专':1, '高中':1, '大专':2, '专科':2, '本科':3, '学士':3, '硕士':4, '研究生':4, '博士':5 }

export function qualificationEvidenceScore(userDegree, requirementTexts) {
  const userRank = DEGREE_RANK[String(userDegree || '').trim()] || null
  const evidence = (requirementTexts || []).map(String).find(text => /(中专|高中|大专|专科|本科|学士|硕士|研究生|博士)(?:及以上|以上)?/.test(text))
  if (!userRank || !evidence) return { score:null, available:false, requiredDegree:null, evidence:null }
  const match = evidence.match(/(中专|高中|大专|专科|本科|学士|硕士|研究生|博士)(?:及以上|以上)?/)
  const requiredDegree = match?.[1] || null
  const requiredRank = DEGREE_RANK[requiredDegree] || null
  return { score:userRank >= requiredRank ? 100 : 0, available:true, requiredDegree, evidence:evidence.slice(0,500) }
}

export function projectSceneEvidenceScore(projectSkills, jobSkills) {
  const project = new Set((projectSkills || []).map(x => String(x).toLowerCase()))
  const required = [...new Set((jobSkills || []).map(x => String(x).toLowerCase()))]
  if (!project.size || !required.length) return { score:null, available:false, matchedSkills:[] }
  const matchedSkills = required.filter(x => project.has(x))
  return { score:Math.round(matchedSkills.length / required.length * 100), available:true, matchedSkills }
}

export function meanEmbedding(names, embeddingMap) {
  const vectors = (names || []).map(name => embeddingMap?.[name] || embeddingMap?.[String(name).toLowerCase()]).filter(Array.isArray)
  if (!vectors.length) return null
  const dimension = vectors[0].length
  if (!dimension || vectors.some(vector => vector.length !== dimension)) return null
  const mean = Array.from({length:dimension}, (_, index) => vectors.reduce((sum, vector) => sum + Number(vector[index] || 0), 0) / vectors.length)
  const norm = Math.sqrt(mean.reduce((sum, value) => sum + value * value, 0))
  return norm > 0 ? mean.map(value => value / norm) : null
}

export function embeddingSimilarityScore(left, right) {
  if (!Array.isArray(left) || !Array.isArray(right) || !left.length || left.length !== right.length) return null
  const leftNorm = Math.sqrt(left.reduce((sum, value) => sum + Number(value) ** 2, 0))
  const rightNorm = Math.sqrt(right.reduce((sum, value) => sum + Number(value) ** 2, 0))
  if (!leftNorm || !rightNorm) return null
  const cosine = left.reduce((sum, value, index) => sum + Number(value) * Number(right[index]), 0) / (leftNorm * rightNorm)
  return Math.round(Math.max(0, Math.min(1, (cosine + 1) / 2)) * 100)
}

export function decayedActionWeight(actionType, occurredAt, now = new Date(), halfLifeDays = 30) {
  const baseWeights = { exposure:.05, viewed:.15, click:.25, interested:.45, favorite:.6, applied:.8, interviewed:.9, hired:1, not_interested:-.5 }
  const base = baseWeights[actionType]
  if (base === undefined) return null
  const occurred = new Date(occurredAt)
  if (!Number.isFinite(occurred.getTime())) return null
  const ageDays = Math.max(0, (now.getTime() - occurred.getTime()) / 86400000)
  const decay = Math.pow(.5, ageDays / halfLifeDays)
  return { weight:base * decay, baseWeight:base, decay, ageDays }
}

export function aggregateBehaviorSignals(events, now = new Date()) {
  const byJob = new Map()
  for (const event of events || []) {
    const weighted = decayedActionWeight(event.action_type, event.created_at, now)
    if (!weighted) continue
    const jobId = String(event.job_id || '')
    if (!jobId) continue
    const current = byJob.get(jobId) || { rawWeight:0, eventCount:0, actions:[] }
    current.rawWeight += weighted.weight
    current.eventCount += 1
    current.actions.push(event.action_type)
    byJob.set(jobId, current)
  }
  for (const value of byJob.values()) {
    value.score = Math.round(Math.max(0, Math.min(100, 50 + value.rawWeight * 50)))
  }
  return byJob
}

export function diversifyRanking(candidates, seenJobIds = [], options = {}) {
  const limit = Math.min(Number(options.limit || 30), (candidates || []).length)
  const qualityWeight = Number(options.qualityWeight ?? .85)
  const quota = Math.min(limit, Math.ceil(limit * Number(options.explorationQuota ?? .2)))
  const seen = new Set((seenJobIds || []).map(String))
  const remaining = [...(candidates || [])]
  const selected = []
  let unseenSelected = 0
  const skills = item => [...new Set([...(item.matched_skills || []), ...(item.missing_skills || [])])]
  while (selected.length < limit && remaining.length) {
    const unseenNeeded = Math.max(0, quota - unseenSelected)
    const slotsLeft = limit - selected.length
    const forceUnseen = unseenNeeded > 0 && slotsLeft <= unseenNeeded
    const pool = forceUnseen ? remaining.filter(item => !seen.has(String(item.job_id))) : remaining
    const source = pool.length ? pool : remaining
    let best = null
    for (const item of source) {
      const redundancy = selected.length ? Math.max(...selected.map(chosen => weightedJaccard(skills(item), skills(chosen)))) : 0
      const unseenBonus = seen.has(String(item.job_id)) ? 0 : .05
      const rerankScore = qualityWeight * (Number(item.fused_score ?? item.match_score ?? 0) / 100) - (1-qualityWeight) * redundancy + unseenBonus
      if (!best || rerankScore > best.rerankScore) best = { item, rerankScore, redundancy, unseen:!seen.has(String(item.job_id)) }
    }
    best.item.diversity_rerank = { originalRank:(candidates || []).indexOf(best.item)+1, rerankScore:Math.round(best.rerankScore*10000)/10000, maxRedundancy:Math.round(best.redundancy*10000)/10000, unseen:best.unseen }
    selected.push(best.item)
    if (best.unseen) unseenSelected++
    remaining.splice(remaining.indexOf(best.item),1)
  }
  const pairDistances = []
  for (let i=0;i<selected.length;i++) for (let j=i+1;j<selected.length;j++) pairDistances.push(1-weightedJaccard(skills(selected[i]),skills(selected[j])))
  return { candidates:selected, metrics:{ requestedExplorationQuota:quota, unseenSelected, novelty:selected.length?unseenSelected/selected.length:0, intraListDiversity:pairDistances.length?pairDistances.reduce((a,b)=>a+b,0)/pairDistances.length:null } }
}

export function gapPriorityScore(factors = {}) {
  const requirementImportance = Math.max(.1, Math.min(1, Number(factors.requirementImportance ?? .35)))
  const marketDemand = Math.max(.1, Math.min(1, Number(factors.marketDemand ?? .1)))
  const evidenceConfidence = Math.max(.1, Math.min(1, Number(factors.evidenceConfidence ?? .5)))
  const careerRelevance = Math.max(.1, Math.min(1, Number(factors.careerRelevance ?? .4)))
  const learningCost = Math.max(.25, Number(factors.learningCost ?? 1))
  const raw = requirementImportance * marketDemand * evidenceConfidence * careerRelevance / learningCost
  return { raw, factors:{ requirementImportance, marketDemand, evidenceConfidence, careerRelevance, learningCost } }
}
