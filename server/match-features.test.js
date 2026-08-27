import test from 'node:test'
import assert from 'node:assert/strict'
import {
  FEATURE_NAMES, buildFeatureResources, buildMatchFeatures, ngramCosine, normalizeSkill, resumeSkillTiers,
} from './match-features.js'

const ontology = {
  Python: { standard_name: 'Python', aliases: ['py'], parent_skill: '' },
  PyTorch: { standard_name: 'PyTorch', aliases: ['torch'], parent_skill: '深度学习' },
  深度学习: { standard_name: '深度学习', aliases: ['deep learning'], parent_skill: '机器学习' },
  机器学习: { standard_name: '机器学习', aliases: ['ml'], parent_skill: '' },
  Kubernetes: { standard_name: 'Kubernetes', aliases: ['k8s'], parent_skill: '' },
}

// Python is deliberately common and Kubernetes rare, so IDF must separate them.
const resources = buildFeatureResources({
  ontology,
  documentFrequency: { Python: 900, 机器学习: 300, 深度学习: 120, PyTorch: 40, Kubernetes: 10 },
  totalJobs: 1000,
  jobFamilyRows: [
    { standard_job_name: '机器学习工程师', raw_job_name: '机器学习工程师', job_family: '人工智能' },
    { standard_job_name: '深度学习工程师', raw_job_name: '深度学习工程师', job_family: '人工智能' },
    { standard_job_name: '市场营销经理', raw_job_name: '市场营销经理', job_family: '市场' },
    { standard_job_name: '占位岗位', raw_job_name: '占位岗位', job_family: '待审核' },
  ],
})

const resume = {
  target_job: '机器学习工程师',
  work_years: '3年',
  skills: ['Python', 'PyTorch', 'Kubernetes', 'DevOps'],
  skill_states: { Python: 'demonstrated', PyTorch: 'claimed', Kubernetes: 'mentioned', DevOps: 'target_only' },
  skill_evidence_text: 'PyTorch｜使用 PyTorch 训练图像分类模型',
  projects_text: '• 基于 PyTorch 的图像分类项目',
}

const feature = (r, j) => buildMatchFeatures(r, j, resources).byName

test('normalizeSkill strips the 待新增 prefix that marks out-of-ontology terms', () => {
  assert.equal(normalizeSkill('待新增:CNCF'), 'cncf')
  assert.equal(normalizeSkill('待新增：CNCF'), 'cncf')
  assert.equal(normalizeSkill('  PyTorch '), 'pytorch')
})

test('aliases resolve to the standard name', () => {
  const { possessed } = resumeSkillTiers({ skills: ['py', 'k8s'], skill_states: {} }, resources)
  assert.ok(possessed.has('python'))
  assert.ok(possessed.has('kubernetes'))
})

test('aspirational states are held out of possession but tracked separately', () => {
  const { possessed, aspirational } = resumeSkillTiers(resume, resources)
  assert.ok(!possessed.has('devops'), 'target_only must not count as possessed')
  assert.ok(aspirational.has('devops'))
})

test('evidence state grades the coverage instead of being binary', () => {
  const demonstrated = feature(
    { skills: ['Python'], skill_states: { Python: 'demonstrated' } }, { required_skills: ['Python'] })
  const mentioned = feature(
    { skills: ['Python'], skill_states: { Python: 'mentioned' } }, { required_skills: ['Python'] })
  assert.equal(demonstrated.req_cov_exact, 1)
  assert.equal(mentioned.req_cov_exact, 1, 'exact coverage stays binary')
  assert.ok(demonstrated.req_cov_evidence > mentioned.req_cov_evidence, 'evidence coverage must separate them')
})

test('an ontology parent is implied by its child', () => {
  const f = feature(resume, { required_skills: ['深度学习'] })
  assert.equal(f.req_cov_exact, 0, 'the resume never states 深度学习 outright')
  assert.ok(f.req_cov_with_parent > 0, 'PyTorch implies 深度学习')
})

test('aspirational delta recovers the gold-2/3-predicted-0 cases without faking possession', () => {
  const f = feature(resume, { required_skills: ['DevOps'] })
  assert.equal(f.req_cov_exact, 0, 'a 求职意向 skill is not possession')
  assert.equal(f.req_cov_aspirational_delta, 1, 'but it must be visible to the model')
})

test('IDF separates a common hit from a rare one', () => {
  const common = feature({ skills: ['Python'], skill_states: {} }, { required_skills: ['Python'] })
  const rare = feature({ skills: ['Kubernetes'], skill_states: {} }, { required_skills: ['Kubernetes'] })
  assert.equal(common.req_cov_exact, rare.req_cov_exact, 'plain coverage cannot tell them apart')
  assert.ok(rare.matched_idf_max > common.matched_idf_max, 'IDF must: this is the 35-case g0->p1 fix')
})

test('job family match is signed and ignores 待审核 placeholder rows', () => {
  assert.equal(feature(resume, { standard_job_name: '深度学习工程师' }).family_match, 1)
  assert.equal(feature(resume, { standard_job_name: '市场营销经理' }).family_match, -1)
  assert.equal(feature(resume, { standard_job_name: '占位岗位' }).family_match, 0, 'unreviewed rows carry no signal')
  assert.equal(feature(resume, { standard_job_name: '从未见过的岗位' }).family_match, 0)
})

test('required years are read out of the JD prose, since the gold has no structured field', () => {
  const junior = feature(resume, { required_skills: ['Python'], original_text: '要求1年以上相关工作经验' })
  const senior = feature(resume, { required_skills: ['Python'], original_text: '要求8年以上相关工作经验' })
  assert.ok(junior.years_gap > 0, '3 years covers a 1-year ask')
  assert.ok(senior.years_gap < 0, '3 years falls short of an 8-year ask')
})

test('seniority gap falls back to tenure when the target title carries no level word', () => {
  const f = feature(resume, { job_title: '资深机器学习专家' })
  assert.ok(f.seniority_gap < 0, '3 years of tenure is below a 资深 posting')
  assert.ok(f.jd_seniority > 0)
})

test('a JD with no required skills is flagged rather than silently scored', () => {
  const f = feature(resume, { required_skills: [], bonus_skills: ['Python'] })
  assert.equal(f.has_required, 0)
  assert.equal(f.req_cov_exact, 0)
  assert.equal(f.bonus_cov, 1)
})

test('feature vector is aligned to FEATURE_NAMES and free of nulls', () => {
  const built = buildMatchFeatures(resume, { required_skills: ['Python'], standard_job_name: '机器学习工程师' }, resources)
  assert.equal(built.values.length, FEATURE_NAMES.length)
  for (const [index, name] of FEATURE_NAMES.entries()) {
    assert.equal(built.values[index], built.byName[name], `${name} out of order`)
    assert.ok(Number.isFinite(built.values[index]), `${name} is not finite`)
  }
})

test('ngramCosine is 1 for identical text and null when a side is empty', () => {
  assert.equal(ngramCosine('机器学习工程师', '机器学习工程师'), 1)
  assert.equal(ngramCosine('', '机器学习'), null)
  assert.ok(ngramCosine('机器学习工程师', '深度学习工程师') > 0)
})
