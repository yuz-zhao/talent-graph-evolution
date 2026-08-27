import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { assessJdRelevance, normalizedSkillName } from '../../server/matching-utils.js'
import { scoreMatch } from '../../server/match-score.js'
import { loadMatchResources } from '../../server/match-resources.js'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const goldDir = join(root, 'crawler/data/gold/human/v1.1')
const reportPath = join(root, 'crawler/data/reports/jd_match_diagnosis_frozen_test.json')
const readJsonl = name => readFileSync(join(goldDir, name), 'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse)
const resumes = new Map(readJsonl('gold_resume_v1.1.jsonl').map(row => [row.resume_id, row]))
const jds = new Map(readJsonl('gold_jd_v1.1.jsonl').map(row => [row.sample_id, row]))
const pairs = readJsonl('gold_match_v1.1.jsonl').filter(row => row.split === 'test' || resumes.get(row.resume_id)?.split === 'test')

// The rubric scorer is the four-class relevance classifier under test. The legacy
// single-axis coverage bands are retained here as a comparison baseline only.
const resources = loadMatchResources()

let tp = 0, fp = 0, fn = 0, tn = 0
const relevanceGold = [], rubricPredicted = [], legacyPredicted = []
const samples = []
for (const pair of pairs) {
  const resume = resumes.get(pair.resume_id)
  const jd = jds.get(pair.jd_sample_id)
  if (!resume || !jd) continue
  const rubric = scoreMatch(resume, jd, resources)
  const userSkills = (resume.skills || []).map(name => ({ name, state:resume.skill_states?.[name] || 'demonstrated' }))
  const legacy = assessJdRelevance(userSkills, jd)
  relevanceGold.push(Number(pair.relevance))
  rubricPredicted.push(rubric.tier)
  legacyPredicted.push(legacy.relevance)
  const goldMatched = new Set((pair.matched_skills || []).map(normalizedSkillName))
  const decisions = legacy.decisions.map(item => {
    const actual = goldMatched.has(item.normalized_name)
    if (item.matched && actual) tp++
    else if (item.matched) fp++
    else if (actual) fn++
    else tn++
    return { skill:item.name, requirement_type:item.requirement_type, predicted:item.matched, actual }
  })
  samples.push({
    pair_id:pair.pair_id, resume_id:pair.resume_id, jd_sample_id:pair.jd_sample_id,
    relevance:pair.relevance,
    rubric_predicted_relevance:rubric.tier, rubric_score:rubric.score, rubric_axes:rubric.axes,
    legacy_predicted_relevance:legacy.relevance,
    decisions,
  })
}

const accuracy = (tp + tn) / Math.max(1, tp + fp + fn + tn)
const precision = tp / Math.max(1, tp + fp)
const recall = tp / Math.max(1, tp + fn)
const f1 = 2 * precision * recall / Math.max(Number.EPSILON, precision + recall)
const labels = [0,1,2,3]
function relevanceStats(gold, predicted) {
  const matrix = labels.map(actual => labels.map(pred => gold.filter((value,index) => value === actual && predicted[index] === pred).length))
  const acc = gold.filter((value,index) => value === predicted[index]).length / Math.max(1,gold.length)
  const f1 = labels.map(label => {
    const classTp = matrix[label][label]
    const classFp = labels.filter(other => other !== label).reduce((sum,other) => sum + matrix[other][label], 0)
    const classFn = labels.filter(other => other !== label).reduce((sum,other) => sum + matrix[label][other], 0)
    const p = classTp / Math.max(1,classTp + classFp), r = classTp / Math.max(1,classTp + classFn)
    return 2 * p * r / Math.max(Number.EPSILON,p + r)
  }).reduce((sum,value) => sum + value, 0) / labels.length
  return { accuracy:acc, macro_f1:f1, confusion_matrix:matrix }
}
const rubricMetric = relevanceStats(relevanceGold, rubricPredicted)
const legacyMetric = relevanceStats(relevanceGold, legacyPredicted)
let clusterRelevanceAccuracy = null
try {
  const formal = JSON.parse(readFileSync(join(root, 'crawler/data/reports/human_gold_v1_1_v8_readonly_evaluation.json'), 'utf8'))
  clusterRelevanceAccuracy = formal.metrics?.accuracy ?? formal.accuracy ?? null
} catch {}

const report = {
  schema_version:'1.1.0',
  evaluation_target:'jd_skill_match_diagnosis',
  gold_version:'gold_v1.1',
  split:'test',
  frozen_manifest:true,
  pair_count:samples.length,
  decision_count:tp + fp + fn + tn,
  leakage_control:'Only resume skills, skill evidence states, and JD required/bonus skills are model inputs. Gold matched_skills are used only after prediction for scoring.',
  metrics:{ accuracy, precision, recall, f1, tp, fp, fn, tn, threshold:.9, passed:accuracy >= .9 },
  concrete_jd_relevance_metric:{ ...rubricMetric, threshold:.9, passed:rubricMetric.accuracy >= .9, method:'rubric-derived two-axis ordinal scoring: 方向一致性 + IDF 核心/通用判别；无冻结标签作输入' },
  previous_cluster_relevance_metric:{ four_class_accuracy:clusterRelevanceAccuracy, note:'Legacy cluster-level fusion is retained only as a comparison baseline.' },
  legacy_coverage_bands_metric:{ ...legacyMetric, note:'原 75/40 单轴覆盖率硬阈值，仅作对比基线。' },
  claim_eligible:accuracy >= .9,
  samples,
}
writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n', 'utf8')
console.log(JSON.stringify({ report:reportPath, pair_count:report.pair_count, decision_count:report.decision_count, metrics:report.metrics, concrete_jd_relevance_metric:report.concrete_jd_relevance_metric, legacy_coverage_bands_metric:report.legacy_coverage_bands_metric, previous_cluster_relevance_metric:report.previous_cluster_relevance_metric }, null, 2))
