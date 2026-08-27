const VERSION = 'resume_parser_v2'
const SECTION_RULES = [
  ['education', /^(?:教育背景|教育经历|学历|education)$/i], ['skills', /^(?:专业技能|职业技能|技能清单|技术栈|skills?)$/i],
  ['projects', /^(?:项目经历|项目经验|projects?)$/i], ['work', /^(?:工作经历|实习经历|校园经历|employment|experience)$/i],
  ['certificates', /^(?:荣誉证书|荣誉奖项|证书|认证|certificates?)$/i], ['intent', /^(?:求职意向|目标岗位|期望职位|objective)$/i],
  ['profile', /^(?:自我评价|个人评价|个人简介|个人总结|summary|profile)$/i],
]
const NEGATIVE = /了解中|学习中|正在学习|课程学习|计划学习|目标岗位|职位要求|期望掌握|希望从事/i
const PROFICIENCY = /精通|熟练|擅长|proficient|expert/i
const USED = /负责|开发|实现|搭建|使用|应用|优化|设计|维护|基于|参与|developed|built|implemented|using/i

function skillEvidenceAttributes(sentence, status) {
  const text = String(sentence || '')
  const proficiencyLevel = /精通|专家|expert/i.test(text) ? 5
    : /熟练掌握|熟练|proficient|advanced/i.test(text) ? 4
      : /熟悉|较熟悉|familiar|intermediate/i.test(text) ? 3
        : /了解|基础|beginner|basic/i.test(text) ? 2
          : status === 'demonstrated' ? 3 : status === 'claimed' ? 2 : 1
  const yearsMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:年|years?)/i)
  const dates = [...text.matchAll(/(?:19|20)\d{2}(?:[.\-/年](?:0?[1-9]|1[0-2]))?/g)].map(match => match[0])
  const evidenceType = status === 'demonstrated' ? 'work_or_project'
    : status === 'claimed' ? 'self_claimed'
      : status === 'learning' ? 'learning' : status === 'target_only' ? 'target_intent' : 'other_mention'
  const responsibility = /主导|负责人|技术负责人|架构|led|owned|architect/i.test(text) ? 'lead'
    : /独立完成|独立负责|核心开发|independently|core developer/i.test(text) ? 'owner'
      : status === 'demonstrated' ? 'participant' : null
  return { proficiency_level:proficiencyLevel, years_experience:yearsMatch ? Math.min(50, Number(yearsMatch[1])) : null, last_used_text:dates.at(-1) || null, evidence_type:evidenceType, responsibility }
}

export function classifySections(blocks) {
  let current = 'profile'
  const seenLayoutBlocks = new Set()
  return blocks.map((block, index) => {
    const text = String(block.text || '').trim()
    if (Number.isFinite(Number(block.x)) && Number.isFinite(Number(block.y))) {
      const layoutKey = `${Number(block.page || 1)}|${Math.round(Number(block.x))}|${Math.round(Number(block.y))}|${text}`
      if (seenLayoutBlocks.has(layoutKey)) return null
      seenLayoutBlocks.add(layoutKey)
    }
    const heading = SECTION_RULES.find(([, pattern]) => pattern.test(text) && text.length <= 40)
    if (heading) current = heading[0]
    return { ...block, block_id: block.block_id || `BLOCK_${index + 1}`, page: Number(block.page || 1), text, section: current, is_heading: Boolean(heading) }
  }).filter(x => x?.text)
}

const PROJECT_FIELD_LABEL = /^(?:项目名称|项目名|项目|项目成员|项目概述|项目介绍|项目背景|项目职责|主要职责|核心职责|个人职责|职责描述|成果亮点|项目成果|工作内容|技术栈|开发环境|担任角色|项目角色|角色)$/i
const PROJECT_NOISE = /^(?:\d+(?:\.\d+)?%?|\d{4}[.\-/年]\d{1,2}(?:\s*[-—至~]\s*\d{4}[.\-/年]\d{1,2})?|\d+(?:\.\d+)?[kK][-—~]\d+(?:\.\d+)?[kK]|(?:核心职责|成果亮点|项目概述|职业技能|专业技能|操作系统|网络技术|软件应用|硬件维护|信息安全|服务意识))$/i
const PROJECT_TITLE_HINT = /系统|平台|项目|模型|网站|小程序|应用|工具|引擎|机器人|校园|商城|管理|检测|识别|分析|研究|可视化|智能|算法|chatgpt|project|system|platform|model|app/i

function cleanProjectTitle(text) {
  return String(text || '').replace(/^(?:项目名称|项目名|项目)\s*[：:]\s*/i, '').replace(/\s+/g, ' ').trim()
}

function isProjectNoise(text) {
  const value = cleanProjectTitle(text)
  return !value || value.length < 3 || PROJECT_NOISE.test(value) || PROJECT_FIELD_LABEL.test(value) ||
    /^[\d\s.%年月日/—~+-]+$/.test(value) || /^\d+(?:余|多)?(?:台|次|例|人|项|个)/.test(value) ||
    /^(?:出生年月|出生日期|期望薪资|薪资)\s*[：:]?$/.test(value) || /^[，,；;。.!！、]/.test(value) ||
    /(?:以上|以下|正常运|准确率达到|满意度至)$/.test(value) || /^(?:以上|以下)[，,。.；;]/.test(value)
}

function looksLikeProjectTitle(block, projectHeading) {
  const value = cleanProjectTitle(block.text)
  if (isProjectNoise(value) || value.length > 80 || /[：:；;。！？!?]/.test(value) || /^(?:负责|参与|基于|使用|开发|实现|搭建|优化|维护)/i.test(value)) return false
  const hasLayout = Number.isFinite(Number(block.x)) && Number.isFinite(Number(projectHeading?.x))
  const startsAtTitleColumn = hasLayout && Number(block.x) <= Number(projectHeading.x) + 25
  return PROJECT_TITLE_HINT.test(value) && (!hasLayout || startsAtTitleColumn)
}

function boundaryMatch(text, keyword) {
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const ascii = /^[a-z0-9.+#-]+$/i.test(keyword)
  const pattern = ascii ? new RegExp(`(^|[^a-z0-9])(${escaped})(?=$|[^a-z0-9])`, 'i') : new RegExp(escaped, 'i')
  return text.match(pattern)
}

function statusFor(section, sentence) {
  if (section === 'intent') return 'target_only'
  if (NEGATIVE.test(sentence)) return 'learning'
  if (['projects', 'work'].includes(section) && USED.test(sentence)) return 'demonstrated'
  if (section === 'skills' || PROFICIENCY.test(sentence)) return 'claimed'
  return 'mentioned'
}

export function parseResumeBlocks(blocks, ontology) {
  const classified = classifySections(blocks)
  const workText = classified.filter(block => block.section === 'work' && !block.is_heading).map(block => block.text).join('\n')
  const explicitYears = [...workText.matchAll(/(\d+(?:\.\d+)?)\s*(?:年|years?)/gi)].map(match => Number(match[1])).filter(Number.isFinite)
  const currentSeniority = /总监|director/i.test(workText) ? 'director'
    : /经理|负责人|manager|lead/i.test(workText) ? 'lead'
      : /专家|资深|principal|expert/i.test(workText) ? 'expert'
        : /高级|senior/i.test(workText) ? 'senior'
          : /中级|intermediate|mid-level/i.test(workText) ? 'mid'
            : /实习|intern/i.test(workText) ? 'intern' : null
  const candidateProfile = { work_years:explicitYears.length ? Math.max(...explicitYears) : null, seniority:currentSeniority, source:explicitYears.length || currentSeniority ? 'resume_work_section' : 'unavailable' }
  const evidence = []
  for (const block of classified) {
    if (block.is_heading) continue
    const sentences = block.text.split(/(?<=[。！？!?；;])|\n/).map(x => x.trim()).filter(Boolean)
    for (const sentence of sentences) {
      for (const skill of ontology) {
        const keywords = [skill.name, ...(skill.keywords || [])].filter(Boolean).sort((a, b) => b.length - a.length)
        const matched = keywords.find(keyword => boundaryMatch(sentence, keyword))
        if (!matched) continue
        const status = statusFor(block.section, sentence)
        const base = status === 'demonstrated' ? .9 : status === 'claimed' ? .82 : status === 'learning' ? .58 : status === 'target_only' ? .35 : .62
        const documentConfidence = Number.isFinite(Number(block.character_confidence)) ? Math.max(0, Math.min(1, Number(block.character_confidence))) : 1
        const confidence = Math.round(base * documentConfidence * 1000) / 1000
        evidence.push({ skill_name: skill.name, standard_name: skill.name, category: skill.category || '其他', status, confidence, raw_confidence: base, document_confidence: documentConfidence, ...skillEvidenceAttributes(sentence, status),
          evidence_text: sentence.slice(0, 500), section: block.section, page: block.page, block_id: block.block_id })
      }
    }
  }
  const rank = { demonstrated: 5, claimed: 4, mentioned: 3, learning: 2, target_only: 1 }
  const best = new Map()
  for (const item of evidence) {
    const previous = best.get(item.standard_name)
    if (!previous || rank[item.status] > rank[previous.status] || item.confidence > previous.confidence) best.set(item.standard_name, item)
  }
  const projects = []
  const projectBlocks = classified.filter(x => x.section === 'projects' && !x.is_heading)
  const projectHeading = classified.find(x => x.section === 'projects' && x.is_heading)
  let currentProject = null
  for (const block of projectBlocks) {
    const blockSkills = evidence.filter(x => x.block_id === block.block_id && x.status !== 'target_only').map(x => ({ skill_name:x.standard_name,evidence_text:x.evidence_text,confidence:x.confidence }))
    if (looksLikeProjectTitle(block, projectHeading)) {
      const title = cleanProjectTitle(block.text).slice(0, 80)
      const duplicate = projects.find(project => project.project_name.toLowerCase() === title.toLowerCase())
      if (duplicate) { currentProject = duplicate; continue }
      currentProject={project_name:title,description:'',page:block.page,block_id:block.block_id,skills:[...blockSkills]};projects.push(currentProject)
    } else if (currentProject && !isProjectNoise(block.text)) {
      currentProject.description=[currentProject.description, block.text].filter(Boolean).join('\n').slice(0,1000)
      currentProject.skills.push(...blockSkills)
    }
  }
  for(const project of projects){const unique=new Map();for(const skill of project.skills)if(!unique.has(skill.skill_name))unique.set(skill.skill_name,skill);project.skills=[...unique.values()]}
  // A resume skill inventory must include explicit mentions from education,
  // profile and certificate blocks as well as stronger project/skills-section
  // evidence. Learning intentions and target-job requirements remain excluded
  // so that the matcher never treats aspirational skills as possessed skills.
  const safeSkills = [...best.values()].filter(x => ['demonstrated', 'claimed', 'mentioned'].includes(x.status)).sort((a, b) => b.confidence - a.confidence).slice(0, 50)
  return { algorithm_version: VERSION, confidence_calibration: { status:'uncalibrated', method:null, reason:'independent_human_validation_set_unavailable' }, sections: classified, skills: safeSkills, all_skill_evidence: evidence, projects, candidate_profile:candidateProfile,
    quality: { block_count: classified.length, section_count: new Set(classified.map(x => x.section)).size, evidence_count: evidence.length, project_skill_relations: projects.reduce((n, x) => n + x.skills.length, 0) } }
}

export function redactPrivacy(text) {
  return String(text || '').replace(/^(\s*(?:姓名|name)\s*[：:])\s*[^\n]+/gim, '$1 [NAME]')
    .replace(/^(\s*(?:性别|gender|sex)\s*[：:])\s*[^\n]+/gim, '$1 [GENDER]')
    .replace(/^(\s*(?:年龄|age|出生日期|生日|birthday|date of birth)\s*[：:])\s*[^\n]+/gim, '$1 [AGE_OR_BIRTH_DATE]')
    .replace(/^(\s*(?:民族|ethnicity|nation)\s*[：:])\s*[^\n]+/gim, '$1 [ETHNICITY]')
    .replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, '[EMAIL]')
    .replace(/(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)/g, '[PHONE]')
    .replace(/(?<!\d)\d{17}[\dXx](?!\d)/g, '[ID_NUMBER]')
}

export function sanitizeParsedResume(parsed = {}) {
  const redactItem = item => ({
    ...item,
    evidence_text: redactPrivacy(item?.evidence_text || ''),
    source_text: redactPrivacy(item?.source_text || ''),
  })
  return {
    algorithm_version: parsed.algorithm_version,
    confidence_calibration: parsed.confidence_calibration,
    skills: (parsed.skills || []).map(redactItem),
    all_skill_evidence: (parsed.all_skill_evidence || []).map(redactItem),
    projects: (parsed.projects || []).map(project => ({
      ...project,
      description: redactPrivacy(project?.description || ''),
      skills: (project?.skills || []).map(redactItem),
    })),
    candidate_profile: parsed.candidate_profile || { work_years:null, seniority:null, source:'unavailable' },
    document_extraction: parsed.document_extraction,
    quality: parsed.quality,
    privacy: { raw_sections_persisted: false, direct_identifiers_redacted: true, policy_version: 'resume_privacy_v1' },
  }
}

export function textToBlocks(text) {
  return String(text || '').split(/\r?\n/).map((value, index) => ({ block_id: `LINE_${index + 1}`, page: 1, text: value.trim() })).filter(x => x.text)
}
