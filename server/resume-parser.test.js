import test from 'node:test'
import assert from 'node:assert/strict'
import { parseResumeBlocks, redactPrivacy, sanitizeParsedResume, textToBlocks } from './resume-parser.js'

const ontology = [{ name:'Python', category:'Backend', keywords:['Python'] }, { name:'Docker', category:'Cloud', keywords:['Docker'] }]

test('distinguishes demonstrated skills from learning and target mentions', () => {
  const parsed = parseResumeBlocks(textToBlocks('项目经历\n推荐系统\n负责使用 Python 开发召回服务。\n求职意向\n目标岗位要求 Docker。\n专业技能\n正在学习 Docker。'), ontology)
  assert.equal(parsed.skills.find(x => x.standard_name === 'Python').status, 'demonstrated')
  assert.equal(parsed.skills.some(x => x.standard_name === 'Docker'), false)
  assert.equal(parsed.all_skill_evidence.find(x => x.standard_name === 'Docker' && x.status === 'learning').status, 'learning')
})

test('keeps explicit standard-skill mentions outside project and skills sections', () => {
  const parsed = parseResumeBlocks(textToBlocks('EDUCATION\nComputer Science coursework: Python and Docker'), ontology)
  assert.equal(parsed.skills.find(x => x.standard_name === 'Python').status, 'mentioned')
  assert.equal(parsed.skills.find(x => x.standard_name === 'Docker').status, 'mentioned')
})

test('extracts proficiency, years, recency and responsibility from skill evidence', () => {
  const parsed = parseResumeBlocks(textToBlocks('项目经历\n推荐系统平台\n2024.06 独立负责并熟练使用 Python 3年，完成服务开发。'), ontology)
  const python = parsed.skills.find(item => item.standard_name === 'Python')
  assert.equal(python.proficiency_level,4)
  assert.equal(python.years_experience,3)
  assert.equal(python.last_used_text,'2024.06')
  assert.equal(python.evidence_type,'work_or_project')
  assert.equal(python.responsibility,'owner')
})

test('extracts candidate experience and seniority from the work section', () => {
  const parsed = parseResumeBlocks(textToBlocks('工作经历\n高级后端工程师\n负责 Python 服务开发3年'), ontology)
  assert.equal(parsed.candidate_profile.work_years,3)
  assert.equal(parsed.candidate_profile.seniority,'senior')
})

test('binds project skills to evidence', () => {
  const parsed = parseResumeBlocks(textToBlocks('项目经历\n智能问答平台\n基于 Python 和 Docker 搭建服务。'), ontology)
  assert.equal(parsed.projects[0].skills.length, 2)
  assert.equal(parsed.projects[0].project_name, '智能问答平台')
  assert.ok(parsed.projects[0].skills.every(x => x.evidence_text))
})

test('rejects dates, metrics, labels and fragments as project titles', () => {
  const parsed = parseResumeBlocks(textToBlocks('项目经历\n智能反诈识别模型\n项目概述\n基于 Python 开发诈骗识别服务。\n核心职责\n25%\n，特别在短信诈骗识别方面准确率达到\n90%\n2023.03-2024.06\n职业技能\n操作系统\n网络技术：熟练掌握 TCP/IP'), ontology)
  assert.deepEqual(parsed.projects.map(x => x.project_name), ['智能反诈识别模型'])
  assert.doesNotMatch(parsed.projects[0].description, /25%|90%|2023\.03/)
})

test('uses layout indentation and deduplicates PDF text-layer project blocks', () => {
  const parsed = parseResumeBlocks([
    { text:'项目经历', page:1, x:62, y:327 },
    { text:'项目经历', page:1, x:62, y:327 },
    { text:'ChatGPT4.0 语义模型技术对公安反诈工作的影响及应用', page:1, x:50, y:292 },
    { text:'ChatGPT4.0 语义模型技术对公安反诈工作的影响及应用', page:1, x:50, y:292 },
    { text:'核心职责：负责使用 Python 对比分析诈骗识别表现。', page:1, x:59, y:217 },
    { text:'6K-8K', page:1, x:343, y:778 },
    { text:'2023.03-2024.06', page:1, x:437, y:292 },
    { text:'职业技能', page:2, x:62, y:817 },
    { text:'信息安全', page:2, x:59, y:707 },
  ], ontology)
  assert.deepEqual(parsed.projects.map(x => x.project_name), ['ChatGPT4.0 语义模型技术对公安反诈工作的影响及应用'])
  assert.match(parsed.projects[0].description, /核心职责/)
})

test('redacts direct identifiers', () => {
  assert.equal(redactPrivacy('a@b.com 13800138000 110101199001011234'), '[EMAIL] [PHONE] [ID_NUMBER]')
  assert.match(redactPrivacy('姓名：张三\n性别：男\n年龄：22\n民族：汉族'), /\[NAME\].*\[GENDER\].*\[AGE_OR_BIRTH_DATE\].*\[ETHNICITY\]/s)
})

test('sanitized parse result drops raw sections and redacts evidence', () => {
  const parsed = parseResumeBlocks(textToBlocks('专业技能\n姓名：张三，熟练 Python，邮箱 a@b.com'), ontology)
  const safe = sanitizeParsedResume(parsed)
  assert.equal('sections' in safe, false)
  assert.equal(safe.privacy.raw_sections_persisted, false)
  assert.doesNotMatch(JSON.stringify(safe), /a@b\.com/)
})

test('keeps document quality metadata in the sanitized audit result', () => {
  const parsed=parseResumeBlocks(textToBlocks('SKILLS\nPython'),ontology)
  parsed.document_extraction={extraction_method:'tesseract_ocr',quality:{requires_human_confirmation:true}}
  assert.equal(sanitizeParsedResume(parsed).document_extraction.quality.requires_human_confirmation,true)
})

test('preserves layout and OCR metadata on classified blocks', () => {
  const parsed = parseResumeBlocks([{block_id:'OCR_1',page:2,x:10,y:20,character_confidence:.93,extraction_method:'tesseract_ocr',text:'SKILLS'}], ontology)
  assert.equal(parsed.sections[0].page, 2)
  assert.equal(parsed.sections[0].character_confidence, .93)
  assert.equal(parsed.sections[0].x, 10)
})

test('discounts extraction confidence and discloses uncalibrated probability', () => {
  const parsed = parseResumeBlocks([{text:'专业技能',page:1},{text:'熟练 Python',page:1,character_confidence:.5}], ontology)
  assert.equal(parsed.skills[0].confidence, .41)
  assert.equal(parsed.skills[0].raw_confidence, .82)
  assert.equal(parsed.confidence_calibration.status, 'uncalibrated')
})
