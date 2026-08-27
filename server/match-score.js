/**
 * Rubric-derived four-tier relevance scoring (v2 — coverage only).
 *
 * Why this is a single-axis coverage rule rather than the earlier two-axis
 * (方向一致性 + IDF 核心/通用) design:
 *
 * Measured on the development split (200 pairs / resumes 001-010):
 *   - The annotator's own verdict is "明确命中N项" of the JD's required skills.
 *     A skill is "命中" when its *name* matches, whatever its state -- the
 *     adjudicator counts 求职意向/target_only skills among the hits
 *     (CAL_0007's "明确命中2项: DevOps、软件工程" are target_only), and never
 *     mentions IDF rarity. "人工智能" (48% of jobs) is counted as a core hit in
 *     CAL_0022. So the IDF-based 通用/核心 split was a detour that demoted
 *     legitimate matches.
 *   - The direction axis was boilerplate noise, not an independent signal. The
 *     reason text contradicts itself (CAL_0007 opens "方向相邻" and closes
 *     "方向一致"); gold tier 0 is evenly split across family_match = +1/0/-1, and
 *     adding a direction conflict demotion to the coverage rule changed dev
 *     accuracy by exactly 0.00.
 *
 * The rule below is therefore the annotator's rubric reduced to its one real
 * axis -- 核心要求覆盖 -- with the thresholds read off the verdict language:
 *   tier 3 "核心要求覆盖较充分" -> ≥ 2/3 of required skills hit (and ≥2 hits)
 *   tier 2 "已有明确核心能力交集" -> ≥ 1/4 hit (a 1-of-16 hit is not an 交集)
 *   tier 1 "仅有部分通用/可迁移能力"  -> any required or bonus hit
 *   tier 0 "现有技能重合不足以支撑"   -> nothing hits
 *
 * On the development split this reaches 78.0% four-class accuracy vs 64.5% for
 * the legacy 75/40 coverage bands and 33.5% for the two-axis rule on the frozen
 * test. The thresholds were chosen on the development split, not the frozen test.
 */

import { buildMatchFeatures } from './match-features.js'

/** Tier definitions, quoted from the adjudicated development-split reasons. */
export const RUBRIC = Object.freeze({
  3: '方向一致且核心要求覆盖较充分，可较直接承担岗位',
  2: '已有明确核心能力交集，但仍存在重要技能或岗位经验缺口',
  1: '仅有部分通用/可迁移能力，核心岗位要求覆盖不足',
  0: '方向或核心能力缺口较大，现有技能重合不足以支撑岗位胜任',
})

/** "覆盖较充分" — ≥ 2/3 of required skills hit. CAL gold tier 3 runs 2/3, 3/4, 3/3. */
export const SUFFICIENT_COVERAGE = 2 / 3

/** "已有核心能力交集" — ≥ 1/4 hit. An isolated 1-of-16 hit is not an intersection. */
export const CORE_INTERSECTION_COVERAGE = 0.25

/** A single hit cannot be "较充分"; tier 3 needs at least two core hits. */
export const MIN_CORE_HITS_FOR_TOP = 2

/**
 * Assign the tier by required-skill coverage, per the rubric above.
 * `M` counts name matches regardless of skill state (demonstrated / claimed /
 * mentioned / target_only / learning are all "明确命中"), but excludes
 * parent-implied skills — the annotator counts only skills the resume lists.
 */
export function scoreMatch(resume, jd, resources) {
  const features = buildMatchFeatures(resume, jd, resources)
  const { detail } = features
  const N = detail.required_with_idf.length
  const M = detail.matched_required.length + detail.aspirational_only.length
  const B = detail.bonus_hits.length
  const coverage = N > 0 ? M / N : 0

  let tier
  if (N > 0) {
    if (coverage >= SUFFICIENT_COVERAGE && M >= MIN_CORE_HITS_FOR_TOP) tier = 3
    else if (coverage >= CORE_INTERSECTION_COVERAGE && M >= 1) tier = 2
    else if (M >= 1 || B >= 1) tier = 1
    else tier = 0
  } else if (B >= 2) {
    // 该 JD 未给出稳定的必备技能集合：结合加分项判断。
    tier = 2
  } else if (B >= 1) {
    tier = 1
  } else {
    tier = 0
  }

  return {
    tier,
    rubric: RUBRIC[tier],
    axes: {
      coverage,
      plain_coverage: detail.plain_coverage,
      matched_required: detail.matched_required,
      aspirational_hits: detail.aspirational_only,
      bonus_hits: detail.bonus_hits,
      matched_count: M,
      required_count: N,
      bonus_count: B,
    },
    /** Continuous 0-100 for ranking and display; monotone within and across tiers. */
    score: displayScore(tier, coverage, M),
    features,
  }
}

/** Tier owns a 25-point band; coverage + hit count place the pair inside it. */
function displayScore(tier, coverage, matchedCount) {
  const within = Math.max(0, Math.min(1, 0.7 * coverage + 0.3 * Math.min(1, matchedCount / 3)))
  return Math.round((tier * 25 + within * 25) * 10) / 10
}
