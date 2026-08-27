/**
 * Feature extraction for four-class (0-3) resume-to-JD relevance.
 *
 * The previous classifier decided the tier from a single feature -- exact-string
 * required-skill coverage -- behind two hard thresholds (75/40). An exhaustive
 * threshold search proved that feature saturates at 66.00% accuracy on the frozen
 * test, so the remaining headroom has to come from new signal, not new cut points.
 *
 * Feature discipline: a scalar that is constant within a resume (skill count,
 * work years, text length) cannot discriminate between that resume's candidates
 * under leave-one-resume-out, and its coefficient is extrapolated from the other
 * nine resumes. Those are exactly the features that inflate CV and collapse on
 * unseen resumes. Resume-side scalars therefore enter only as interactions with a
 * JD-side quantity, never raw.
 */

const ASPIRATIONAL_STATES = new Set(['learning', 'target_only'])
const EVIDENCE_WEIGHT = { demonstrated: 1, claimed: 0.7, mentioned: 0.4 }
const SENIORITY_TITLE_RANK = [
  [/(实习|intern)/i, 0],
  [/(初级|junior|应届|graduate|校招)/i, 1],
  [/(中级|intermediate)/i, 2],
  [/(高级|senior|sr\.?)/i, 3],
  [/(资深|专家|principal|staff|lead|架构师|architect)/i, 4],
  [/(总监|director|经理|manager)/i, 5],
]

/** Ontology names and resume skills both carry a `待新增:` prefix for out-of-ontology terms. */
export function normalizeSkill(value) {
  return String(value || '').trim().replace(/^待新增[:：]\s*/, '').toLowerCase()
}

function charNgrams(value, sizes = [2, 3]) {
  const text = String(value || '').toLowerCase().replace(/\s+/g, '')
  const counts = new Map()
  for (const size of sizes) {
    for (let i = 0; i + size <= text.length; i++) {
      const gram = text.slice(i, i + size)
      counts.set(gram, (counts.get(gram) || 0) + 1)
    }
  }
  return counts
}

/** Cosine over character n-gram term frequencies. Zero external dependencies. */
export function ngramCosine(left, right, sizes = [2, 3]) {
  const a = charNgrams(left, sizes), b = charNgrams(right, sizes)
  if (!a.size || !b.size) return null
  let dot = 0
  const [small, large] = a.size <= b.size ? [a, b] : [b, a]
  for (const [gram, count] of small) dot += count * (large.get(gram) || 0)
  const norm = map => Math.sqrt([...map.values()].reduce((sum, v) => sum + v * v, 0))
  const denominator = norm(a) * norm(b)
  return denominator > 0 ? dot / denominator : null
}

/**
 * Build lookup tables once and reuse across every pair.
 * `ontology` is crawler/data/gold/reference/skill_ontology.json,
 * `documentFrequency`/`totalJobs` come from crawler/data/reference/skill_document_frequency.json,
 * `jobFamilyRows` are the reviewed rows of job_standard_dict.csv.
 */
export function buildFeatureResources({ ontology = {}, documentFrequency = {}, totalJobs = 1, jobFamilyRows = [] } = {}) {
  const aliasToStandard = new Map()
  const parentOf = new Map()
  for (const [name, entry] of Object.entries(ontology)) {
    const standard = entry?.standard_name || name
    aliasToStandard.set(normalizeSkill(name), standard)
    aliasToStandard.set(normalizeSkill(standard), standard)
    for (const alias of entry?.aliases || []) aliasToStandard.set(normalizeSkill(alias), standard)
    if (entry?.parent_skill) parentOf.set(normalizeSkill(standard), normalizeSkill(entry.parent_skill))
  }

  const total = Math.max(1, Number(totalJobs) || 1)
  const maxIdf = Math.log(total + 1) + 1
  const idfBySkill = new Map()
  for (const [name, df] of Object.entries(documentFrequency)) {
    const idf = Math.log((total + 1) / (Number(df) + 1)) + 1
    idfBySkill.set(normalizeSkill(name), Math.max(0, Math.min(1, idf / maxIdf)))
  }

  // Reviewed dictionary rows only: 971 of 2,451 rows are `待审核` placeholders
  // whose job_family carries no information.
  const familyByJobName = new Map()
  for (const row of jobFamilyRows) {
    const family = String(row.job_family || '').trim()
    if (!family || family === '待审核') continue
    for (const key of [row.standard_job_name, row.raw_job_name]) {
      const normalized = String(key || '').trim().toLowerCase()
      if (normalized && !familyByJobName.has(normalized)) familyByJobName.set(normalized, family)
    }
  }

  return { aliasToStandard, parentOf, idfBySkill, familyByJobName, totalJobs: total, defaultIdf: 0.75 }
}

const canonical = (name, resources) =>
  resources.aliasToStandard.get(normalizeSkill(name)) ?? String(name || '').trim()

const idfOf = (name, resources) =>
  resources.idfBySkill.get(normalizeSkill(canonical(name, resources))) ?? resources.defaultIdf

/** Split resume skills into evidence tiers, canonicalising through the ontology. */
export function resumeSkillTiers(resume, resources) {
  const possessed = new Map()      // canonical -> best evidence weight
  const aspirational = new Set()   // learning / target_only
  for (const raw of resume?.skills || []) {
    const name = typeof raw === 'string' ? raw : (raw?.name ?? raw?.standard_name)
    if (!name) continue
    const state = String(
      (typeof raw === 'object' && (raw.state || raw.skill_state)) || resume?.skill_states?.[name] || 'demonstrated',
    ).toLowerCase()
    const key = normalizeSkill(canonical(name, resources))
    if (!key) continue
    if (ASPIRATIONAL_STATES.has(state)) { aspirational.add(key); continue }
    const weight = EVIDENCE_WEIGHT[state] ?? EVIDENCE_WEIGHT.mentioned
    possessed.set(key, Math.max(possessed.get(key) ?? 0, weight))
  }
  // An ontology parent is weakly implied by its child (PyTorch implies 深度学习).
  const implied = new Map()
  for (const [key, weight] of possessed) {
    const parent = resources.parentOf.get(key)
    if (parent && !possessed.has(parent)) implied.set(parent, Math.max(implied.get(parent) ?? 0, weight * 0.6))
  }
  return { possessed, aspirational, implied }
}

function titleSeniority(value) {
  const text = String(value || '')
  let rank = null
  for (const [pattern, level] of SENIORITY_TITLE_RANK) if (pattern.test(text)) rank = Math.max(rank ?? 0, level)
  return rank
}

function parseYears(value) {
  const text = String(value ?? '')
  if (text && Number.isFinite(Number(text))) return Math.max(0, Number(text))
  const match = text.match(/(\d+(?:\.\d+)?)\s*(?:年|years?)/i)
  return match ? Number(match[1]) : null
}

/**
 * The JD gold has no structured `experience` field (0 of 100 samples), so the
 * requirement has to come out of the prose or the feature is dead weight.
 */
function requiredYearsFromText(text) {
  const body = String(text || '')
  const patterns = [
    /(\d+(?:\.\d+)?)\s*年(?:以上|及以上|或以上)?(?:的)?(?:相关)?(?:工作|研发|开发|从业)?经[验历]/,
    /(?:工作|从业|相关)经[验历][^。；;\n]{0,6}?(\d+(?:\.\d+)?)\s*年/,
    /(\d+(?:\.\d+)?)\s*\+?\s*years?\s+(?:of\s+)?experience/i,
  ]
  for (const pattern of patterns) {
    const match = body.match(pattern)
    if (match) return Number(match[1])
  }
  return null
}

/** Resume target titles carry no seniority word, so infer the level from tenure. */
function seniorityFromYears(years) {
  if (years === null) return null
  if (years < 1) return 0
  if (years < 2) return 1
  if (years < 5) return 2
  if (years < 8) return 3
  return 4
}

const mean = values => (values.length ? values.reduce((a, b) => a + b, 0) / values.length : null)
const ratio = (part, whole) => (whole > 0 ? part / whole : null)

/** Stable feature order. The trainer relies on this for its coefficient vector. */
export const FEATURE_NAMES = Object.freeze([
  'req_cov_exact',
  'req_cov_idf',
  'req_cov_evidence',
  'req_cov_with_parent',
  'req_cov_aspirational_delta',
  'bonus_cov',
  'matched_idf_mean',
  'matched_idf_max',
  'missed_idf_mean',
  'family_match',
  'title_sim_standard',
  'title_sim_raw',
  'jd_seniority',
  'seniority_gap',
  'years_gap',
  'text_sim_evidence',
  'text_sim_projects',
  'req_count',
  'bonus_count',
  'has_required',
])

/**
 * Returns { values, byName, detail }. `values` is aligned to FEATURE_NAMES;
 * unavailable signals are 0 with a companion availability flag where it matters,
 * so the caller never has to reason about nulls.
 */
export function buildMatchFeatures(resume, jd, resources) {
  const { possessed, aspirational, implied } = resumeSkillTiers(resume, resources)
  const required = [...new Set((jd?.required_skills || []).map(name => canonical(name, resources)))]
  const bonus = [...new Set((jd?.bonus_skills || []).map(name => canonical(name, resources)))]
    .filter(name => !required.includes(name))

  const hit = name => possessed.has(normalizeSkill(name))
  const matchedRequired = required.filter(hit)
  const missedRequired = required.filter(name => !hit(name))

  // A -- coverage family
  const reqCovExact = ratio(matchedRequired.length, required.length)
  const idfWeight = name => idfOf(name, resources)
  const totalIdf = required.reduce((sum, name) => sum + idfWeight(name), 0)
  const reqCovIdf = ratio(matchedRequired.reduce((sum, name) => sum + idfWeight(name), 0), totalIdf)
  const reqCovEvidence = ratio(
    required.reduce((sum, name) => sum + (possessed.get(normalizeSkill(name)) ?? 0), 0), required.length,
  )
  const withParent = required.filter(name => hit(name) || implied.has(normalizeSkill(name)))
  const reqCovWithParent = ratio(withParent.length, required.length)
  // Aspirational skills (求职意向-derived) are kept as a separate delta rather than
  // folded into possession: annotators counted them, the parser does not, and the
  // model should learn how much they are worth instead of us guessing.
  const withAspirational = required.filter(name => hit(name) || aspirational.has(normalizeSkill(name)))
  const reqCovAspirationalDelta = ratio(withAspirational.length - matchedRequired.length, required.length)
  const bonusCov = ratio(bonus.filter(hit).length, bonus.length)

  // B -- discriminativeness. Matching 人工智能 (present in 48% of jobs) is not
  // the same evidence as matching a rare skill; the old rule treated them alike.
  const matchedIdfs = matchedRequired.map(idfWeight)
  const missedIdfs = missedRequired.map(idfWeight)

  // C -- direction
  const targetJob = String(resume?.target_job || '').trim()
  const standardName = String(jd?.standard_job_name || '').trim()
  const rawTitle = String(jd?.job_title || '').trim()
  const resumeFamily = resources.familyByJobName.get(targetJob.toLowerCase())
  const jdFamily = resources.familyByJobName.get(standardName.toLowerCase())
    ?? resources.familyByJobName.get(rawTitle.toLowerCase())
  const familyMatch = resumeFamily && jdFamily ? (resumeFamily === jdFamily ? 1 : -1) : 0

  // D -- seniority and experience. Resume-side tenure enters only as a gap
  // against the JD's demand, never as a raw per-resume constant.
  const jdSeniority = titleSeniority(rawTitle) ?? titleSeniority(standardName)
  const resumeYears = parseYears(resume?.work_years)
  const resumeSeniority = titleSeniority(resume?.target_job) ?? seniorityFromYears(resumeYears)
  const seniorityGap = jdSeniority === null || resumeSeniority === null
    ? 0 : Math.max(-1, Math.min(1, (resumeSeniority - jdSeniority) / 3))
  const requiredYears = parseYears(jd?.experience ?? jd?.minimum_work_years)
    ?? requiredYearsFromText(jd?.original_text)
  const yearsGap = resumeYears === null || requiredYears === null
    ? 0 : Math.max(-1, Math.min(1, (resumeYears - requiredYears) / 5))

  // E1 -- character n-gram text overlap
  const jdText = jd?.original_text || ''
  const textSimEvidence = ngramCosine(resume?.skill_evidence_text, jdText)
  const textSimProjects = ngramCosine(resume?.projects_text, jdText)

  const byName = {
    req_cov_exact: reqCovExact ?? 0,
    req_cov_idf: reqCovIdf ?? 0,
    req_cov_evidence: reqCovEvidence ?? 0,
    req_cov_with_parent: reqCovWithParent ?? 0,
    req_cov_aspirational_delta: reqCovAspirationalDelta ?? 0,
    bonus_cov: bonusCov ?? 0,
    matched_idf_mean: mean(matchedIdfs) ?? 0,
    matched_idf_max: matchedIdfs.length ? Math.max(...matchedIdfs) : 0,
    missed_idf_mean: mean(missedIdfs) ?? 0,
    family_match: familyMatch,
    title_sim_standard: ngramCosine(targetJob, standardName) ?? 0,
    title_sim_raw: ngramCosine(targetJob, rawTitle) ?? 0,
    jd_seniority: jdSeniority === null ? 0 : jdSeniority / 5,
    seniority_gap: seniorityGap,
    years_gap: yearsGap,
    text_sim_evidence: textSimEvidence ?? 0,
    text_sim_projects: textSimProjects ?? 0,
    req_count: Math.min(required.length, 15) / 15,
    bonus_count: Math.min(bonus.length, 15) / 15,
    has_required: required.length ? 1 : 0,
  }

  // The rubric grades "核心要求覆盖" by how much of the JD's *weighted* demand is
  // met. Evidence strength is a separate axis and deliberately not multiplied in
  // here: folding it into coverage would deflate every claimed-but-not-demonstrated
  // skill, and the development resumes are claimed-dominant (60 claimed / 26
  // demonstrated), which would leave their coverage permanently out of the top band.
  const credit = name => {
    const key = normalizeSkill(name)
    if (possessed.has(key)) return 1
    if (implied.has(key)) return 0.6
    return 0
  }
  const evidenceOf = name => possessed.get(normalizeSkill(name)) ?? implied.get(normalizeSkill(name)) ?? 0
  const effectiveCoverage = ratio(
    required.reduce((sum, name) => sum + credit(name) * idfWeight(name), 0), totalIdf,
  )
  const evidenceStrength = mean(matchedRequired.map(evidenceOf))
  // The tier-3 rubric counts plain hits ("明确命中N项") without IDF weighting, and
  // the adjudicator's own reasons count aspirational skills among the hits. This is
  // the coverage the top band is judged on; effective_coverage stays for ranking.
  const plainCoverage = ratio(
    required.filter(name => hit(name) || implied.has(normalizeSkill(name)) || aspirational.has(normalizeSkill(name))).length,
    required.length,
  )

  return {
    values: FEATURE_NAMES.map(name => byName[name]),
    byName,
    detail: {
      matched_required: matchedRequired,
      missed_required: missedRequired,
      aspirational_only: required.filter(name => !hit(name) && aspirational.has(normalizeSkill(name))),
      parent_implied: required.filter(name => !hit(name) && implied.has(normalizeSkill(name))),
      resume_family: resumeFamily ?? null,
      jd_family: jdFamily ?? null,
      /** Per-skill IDF so the scorer can tell a 核心 hit from a 通用 one. */
      matched_with_idf: matchedRequired.map(name => ({ name, idf: idfWeight(name), evidence: evidenceOf(name) })),
      required_with_idf: required.map(name => ({ name, idf: idfWeight(name), credit: credit(name) })),
      bonus_hits: bonus.filter(name => hit(name) || implied.has(normalizeSkill(name))),
      bonus_hits_with_idf: bonus.filter(name => hit(name) || implied.has(normalizeSkill(name)))
        .map(name => ({ name, idf: idfWeight(name) })),
      effective_coverage: effectiveCoverage ?? 0,
      plain_coverage: plainCoverage ?? 0,
      evidence_strength: evidenceStrength ?? 0,
    },
  }
}
