import test from 'node:test'
import assert from 'node:assert/strict'
import { buildFeatureResources, buildMatchFeatures } from './match-features.js'
import { scoreMatch } from './match-score.js'

// A minimal ontology / document-frequency set. IDF is only used to weight the
// continuous score; the tier rule is pure required-skill coverage, so the exact
// frequencies do not affect the tier assertions.
const ontology = {
  Python: { standard_name: 'Python', aliases: ['py'], parent_skill: '' },
  PyTorch: { standard_name: 'PyTorch', aliases: ['torch'], parent_skill: '深度学习' },
  深度学习: { standard_name: '深度学习', aliases: [], parent_skill: '' },
  Kubernetes: { standard_name: 'Kubernetes', aliases: ['k8s'], parent_skill: '' },
  Docker: { standard_name: 'Docker', aliases: [], parent_skill: '' },
  Redis: { standard_name: 'Redis', aliases: [], parent_skill: '' },
  SQL: { standard_name: 'SQL', aliases: [], parent_skill: '' },
}
const resources = buildFeatureResources({
  ontology,
  documentFrequency: { Python: 900, 深度学习: 40, PyTorch: 40, Kubernetes: 10, Docker: 50, Redis: 30, SQL: 300 },
  totalJobs: 1000,
  jobFamilyRows: [],
})

const resume = {
  target_job: 'AI算法工程师',
  work_years: '3年',
  skills: ['Python', 'PyTorch', 'Kubernetes'],
  skill_states: { Python: 'demonstrated', PyTorch: 'demonstrated', Kubernetes: 'target_only' },
}

test('tier 3 needs ≥2/3 coverage and at least two core hits', () => {
  const jd = { required_skills: ['PyTorch', 'Python'] }
  assert.equal(scoreMatch(resume, jd, resources).tier, 3)
})

test('a single required hit is a tier-2 core intersection, never tier 3', () => {
  // Kubernetes is target_only: it counts as a 命中 but one hit cannot be "充分".
  const jd = { required_skills: ['Kubernetes'] }
  const s = scoreMatch(resume, jd, resources)
  assert.equal(s.axes.matched_count, 1)
  assert.equal(s.tier, 2)
})

test('partial coverage (1/2 to 2/3) lands in tier 2', () => {
  const jd = { required_skills: ['PyTorch', 'Python', 'Docker', 'Kubernetes', 'Redis', 'SQL'] }
  const s = scoreMatch(resume, jd, resources)
  // Python + PyTorch possessed, Kubernetes target_only -> 3 hits of 6.
  assert.equal(s.axes.matched_count, 3)
  assert.equal(s.tier, 2)
})

test('a lone hit of many required skills is tier 1, not a core intersection', () => {
  const lone = { ...resume, skills: ['Python'], skill_states: { Python: 'demonstrated' } }
  const jd = { required_skills: ['Python', 'PyTorch', 'Docker', 'Kubernetes', 'Redis', 'SQL'] }
  assert.equal(scoreMatch(lone, jd, resources).tier, 1)
})

test('nothing hits and nothing transfers resolves to tier 0', () => {
  const lone = { ...resume, skills: ['Python'], skill_states: { Python: 'demonstrated' } }
  const jd = { required_skills: ['Docker', 'Kubernetes', 'Redis'] }
  assert.equal(scoreMatch(lone, jd, resources).tier, 0)
})

test('parent-implied skills do not count as a 命中', () => {
  // PyTorch implies 深度学习 through the ontology, but the annotator only counts
  // skills the resume lists -- so 深度学习 alone must not register a hit.
  const jd = { required_skills: ['深度学习'] }
  const s = scoreMatch(resume, jd, resources)
  assert.equal(s.axes.matched_count, 0)
  assert.equal(s.tier, 0)
})

test('a JD with no required skills falls back to bonus hits', () => {
  const twoBonus = { ...resume, skills: ['Python', 'PyTorch'], skill_states: { Python: 'demonstrated', PyTorch: 'demonstrated' } }
  const jd = { required_skills: [], bonus_skills: ['Python', 'PyTorch'] }
  const s = scoreMatch(twoBonus, jd, resources)
  assert.equal(s.axes.required_count, 0)
  assert.equal(s.tier, 2) // two possessed bonus hits
})

test('the displayed score is monotone and never contradicts the tier band', () => {
  const jd = { required_skills: ['PyTorch', 'Python'] }
  const s = scoreMatch(resume, jd, resources)
  assert.ok(s.score >= s.tier * 25, `score ${s.score} below tier ${s.tier}`)
  assert.ok(s.score <= (s.tier + 1) * 25, `score ${s.score} above tier ${s.tier}`)
})

test('buildMatchFeatures keeps aspirational hits separate from possessed hits', () => {
  const f = buildMatchFeatures(resume, { required_skills: ['PyTorch', 'Python', 'Kubernetes'] }, resources)
  assert.deepEqual(f.detail.matched_required, ['PyTorch', 'Python'])
  assert.deepEqual(f.detail.aspirational_only, ['Kubernetes'])
})
