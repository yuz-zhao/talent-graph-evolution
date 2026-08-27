import assert from 'node:assert/strict'
import test from 'node:test'
import { aggregateBehaviorSignals, assessJdRelevance, bestConcreteJobMatch, calibratedMatchScore, decayedActionWeight, diagnoseJdSkillMatch, diversifyRanking, embeddingSimilarityScore, evaluateJdConstraints, fuseMatchScore, gapPriorityScore, jobDirectionCompatibility, matchLevel, MATCHING_FUSION_CONFIG, meanEmbedding, normalizedWeightedScore, parseExperienceYears, projectSceneEvidenceScore, qualificationEvidenceScore, recallCandidates, representativeClusterRequirements, skillRequirementWeight, weightedJaccard, weightedSkillCoverage } from './matching-utils.js'

test('Item-CF returns a positive score for jobs sharing skills', () => {
  const score = weightedJaccard(['Python', 'PostgreSQL'], ['Python', 'Docker'])
  assert.equal(score, 1 / 3)
})

test('missing dimensions are excluded and remaining weights are renormalized', () => {
  const result = normalizedWeightedScore(
    { required: 80, semantic: 60, project: null, cf: undefined },
    { required: .5, semantic: .3, project: .1, cf: .1 },
  )
  assert.equal(result.score, 73)
  assert.equal(result.available.project, false)
  assert.equal(result.availableWeight, .8)
})

test('first-stage recall prioritizes skill and profile evidence with minimum protection', () => {
  const result = recallCandidates([
    { name:'后端开发',skills:['Python','Docker'],industries:['互联网'],jdCount:5 },
    { name:'销售',skills:['沟通'],industries:['零售'],jdCount:20 },
    { name:'数据工程',skills:['SQL'],industries:['互联网'],jdCount:10 },
  ], { skills:['Python'],direction:'后端',industry:'互联网' }, { limit:2,minimum:1 })
  assert.deepEqual(result.candidates.map(x => x.name), ['后端开发','数据工程'])
  assert.equal(result.fallback, null)
  assert.equal(result.candidates[0].candidateSkillCoverage, .5)
  assert.ok(result.candidates[0].recallReasons.includes('candidate_job_skill_coverage'))
})

test('one auditable production fusion config includes shadow-only GNN weight', () => {
  assert.deepEqual(MATCHING_FUSION_CONFIG.weights,{required:.40,semantic:.20,kg:.15,project:.10,preference:.05,cf:.10,gnn:.00})
  assert.equal(MATCHING_FUSION_CONFIG.calibration.status,'rule_gated_unvalidated')
})

test('JD diagnosis excludes learning and target-only skills from possessed evidence', () => {
  const result = diagnoseJdSkillMatch([
    {name:'Python',state:'demonstrated'},
    {name:'Docker',state:'learning'},
    {name:'Kubernetes',state:'target_only'},
    {name:'SQL',state:'claimed'},
  ], {requiredSkills:['Python','Docker'],bonusSkills:['SQL','Kubernetes']})
  assert.deepEqual(result.matched_skills,['Python','SQL'])
  assert.deepEqual(result.missing_skills,['Docker','Kubernetes'])
  assert.equal(result.required_coverage,50)
  assert.equal(result.bonus_coverage,50)
})

test('cluster scoring selects one concrete JD instead of a synthetic union', () => {
  const result = bestConcreteJobMatch([
    {jobId:'backend',skillName:'Java',requirementType:'required'},
    {jobId:'backend',skillName:'Spring',requirementType:'required'},
    {jobId:'data',skillName:'Python',requirementType:'required'},
    {jobId:'data',skillName:'SQL',requirementType:'required'},
    {jobId:'data',skillName:'Docker',requirementType:'preferred'},
  ], new Set(['python','sql']))
  assert.equal(result.jobId,'data')
  assert.deepEqual(result.diagnosis.matched_skills,['Python','SQL'])
  assert.deepEqual(result.diagnosis.missing_skills,['Docker'])
})

test('concrete JD relevance uses fixed required-skill coverage bands', () => {
  const jd = {requiredSkills:['Python','SQL','Docker','Linux'],bonusSkills:['Git']}
  assert.equal(assessJdRelevance(['Python','SQL','Docker'],jd).relevance,3)
  assert.equal(assessJdRelevance(['Python','SQL'],jd).relevance,2)
  assert.equal(assessJdRelevance(['Git'],jd).relevance,1)
  assert.equal(assessJdRelevance(['Java'],jd).relevance,0)
})

test('skill minimums and OR groups prevent surface-only evidence from passing', () => {
  const jd = {
    requiredSkills:['Java','Golang','SQL'],
    skillGroups:[{operator:'OR',skills:['Java','Golang'],minimumMatch:1,required:true}],
    skillMinimumLevels:{Java:4},
  }
  const weak = diagnoseJdSkillMatch([{name:'Java',state:'claimed',proficiency_level:2}],jd)
  assert.equal(weak.decisions.find(item => item.name === 'Java').evidence_matched,true)
  assert.equal(weak.decisions.find(item => item.name === 'Java').matched,false)
  assert.equal(weak.required_groups_satisfied,false)
  const qualified = diagnoseJdSkillMatch([{name:'Golang',state:'demonstrated',proficiency_level:3}],jd)
  assert.equal(qualified.required_groups_satisfied,true)
})

test('experience, seniority and hard constraints cap relevance', () => {
  assert.equal(parseExperienceYears('3-5年'),3)
  const constraints = evaluateJdConstraints({work_years:1,seniority:'初级',certificate:null},{minimum_work_years:3,seniority:'高级',hard_constraints:[{field:'certificate',operator:'required'}]})
  assert.equal(constraints.passed,false)
  assert.deepEqual(constraints.failures.map(item => item.type),['work_experience','seniority','certificate'])
  const result = assessJdRelevance(['Python','SQL'],{requiredSkills:['Python','SQL'],minimum_work_years:3},{candidate:{work_years:1}})
  assert.equal(result.relevance,1)
  assert.ok(result.score < 40)
})

test('calibration hard-gates known direction conflicts and caps no-skill similarity', () => {
  assert.deepEqual(calibratedMatchScore(88,{directionPreference:0,matchedSkillCount:4}),{score:39,adjustment:'direction_conflict_low_match_cap'})
  assert.deepEqual(calibratedMatchScore(88,{directionPreference:0,matchedSkillCount:0}),{score:0,adjustment:'direction_conflict_no_evidence'})
  assert.deepEqual(calibratedMatchScore(72,{directionPreference:null,matchedSkillCount:0}),{score:39,adjustment:'no_direct_skill_cap'})
  assert.deepEqual(calibratedMatchScore(82,{directionPreference:100,matchedSkillCount:2}),{score:82,adjustment:null})
  assert.deepEqual(calibratedMatchScore(82,{directionPreference:100,matchedSkillCount:2,maximumScore:39,maximumReason:'hard_constraint'}),{score:39,adjustment:'hard_constraint'})
})

test('job direction compatibility recognizes families without penalizing unknown terms', () => {
  assert.equal(jobDirectionCompatibility('机器学习工程师', '深度学习算法工程师'), 100)
  assert.equal(jobDirectionCompatibility('DevOps工程师', '市场营销经理'), 0)
  assert.equal(jobDirectionCompatibility('全栈工程师', '后端开发工程师'), 85)
  assert.equal(jobDirectionCompatibility('量子技术顾问', '研究顾问'), null)
})

test('first-stage recall prefers a compatible direction when skill evidence ties', () => {
  const result = recallCandidates([
    { name:'市场营销经理',skills:['Python'],industries:[],jdCount:20 },
    { name:'机器学习工程师',skills:['Python'],industries:[],jdCount:5 },
  ], { skills:['Python'],direction:'人工智能工程师' }, { limit:2,minimum:1 })
  assert.equal(result.candidates[0].name, '机器学习工程师')
  assert.equal(result.candidates[1].recallReasons.includes('direction_conflict'), true)
})

test('required, confident and rare skills receive more weight', () => {
  const now = new Date('2026-08-05T00:00:00Z')
  const rareRequired = skillRequirementWeight({requirementType:'required',confidence:.95,observedAt:'2026-08-01'}, {totalJobs:1000,documentFrequency:10}, now)
  const commonMention = skillRequirementWeight({requirementType:'mentioned',confidence:.75,observedAt:'2025-08-05'}, {totalJobs:1000,documentFrequency:800}, now)
  assert.ok(rareRequired.weight > commonMention.weight * 5)
})

test('weighted coverage penalizes a missing core skill more than a common mention', () => {
  const requirements = [
    {name:'Kubernetes',requirementType:'required',confidence:.95,observedAt:'2026-08-01',evidenceText:'必须熟练掌握 Kubernetes',sourceUrl:'https://example.test/job/1'},
    {name:'Git',requirementType:'mentioned',confidence:.8,observedAt:'2026-08-01'},
  ]
  const corpus = {totalJobs:1000,documentFrequency:{Kubernetes:30,Git:900}}
  const onlyCommon = weightedSkillCoverage(requirements,['Git'],corpus,new Date('2026-08-05'))
  const onlyCore = weightedSkillCoverage(requirements,['Kubernetes'],corpus,new Date('2026-08-05'))
  assert.ok(onlyCore.coverage > onlyCommon.coverage)
  assert.equal(onlyCore.requiredCoverage,100)
  assert.equal(onlyCore.details[0].evidenceText,'必须熟练掌握 Kubernetes')
  assert.equal(onlyCore.details[0].sourceUrl,'https://example.test/job/1')
})

test('cluster requirements preserve representative gaps instead of the easiest single JD', () => {
  const requirements = [
    {jobId:'j1',skillName:'Python',requirementType:'required',confidence:.9},
    {jobId:'j1',skillName:'SQL',requirementType:'required',confidence:.9},
    {jobId:'j2',skillName:'Python',requirementType:'required',confidence:.9},
    {jobId:'j2',skillName:'Docker',requirementType:'preferred',confidence:.85},
    {jobId:'j3',skillName:'Python',requirementType:'required',confidence:.9},
    {jobId:'j3',skillName:'SQL',requirementType:'required',confidence:.8},
  ]
  const representative = representativeClusterRequirements(requirements, 3)
  assert.deepEqual(representative.map(item => item.name), ['Python','SQL','Docker'])
  assert.equal(representative.find(item => item.name === 'Python').frequency, 3)
})

test('qualification is unavailable without explicit JD evidence', () => {
  assert.equal(qualificationEvidenceScore('本科',['负责系统开发']).available,false)
  const qualified = qualificationEvidenceScore('硕士',['计算机相关专业本科及以上学历'])
  assert.equal(qualified.score,100)
  assert.equal(qualified.requiredDegree,'本科')
})

test('project scene score requires actual project skills', () => {
  assert.equal(projectSceneEvidenceScore([],['Python']).available,false)
  assert.equal(projectSceneEvidenceScore(['Python'],['Python','Docker']).score,50)
})

test('GNN embedding score is unavailable without both vectors', () => {
  assert.equal(meanEmbedding(['missing'], {}), null)
  assert.equal(embeddingSimilarityScore([1,0], null), null)
})

test('GNN user representation averages skill neighbors and scores cosine', () => {
  const user = meanEmbedding(['Python','Docker'], {Python:[1,0],Docker:[1,0]})
  assert.deepEqual(user,[1,0])
  assert.equal(embeddingSimilarityScore(user,[1,0]),100)
  assert.equal(embeddingSimilarityScore(user,[-1,0]),0)
})

test('behavior weights preserve action strength and decay over time', () => {
  const now = new Date('2026-08-05T00:00:00Z')
  assert.equal(decayedActionWeight('hired', now, now).weight, 1)
  assert.equal(decayedActionWeight('favorite', '2026-07-06T00:00:00Z', now).weight, .3)
  assert.ok(decayedActionWeight('not_interested', now, now).weight < 0)
  assert.equal(decayedActionWeight('unknown', now, now), null)
})

test('event stream aggregates explicit feedback without treating exposure as negative', () => {
  const now = new Date('2026-08-05T00:00:00Z')
  const signals = aggregateBehaviorSignals([
    {job_id:'A',action_type:'favorite',created_at:now},
    {job_id:'A',action_type:'not_interested',created_at:now},
    {job_id:'B',action_type:'exposure',created_at:now},
  ], now)
  assert.equal(signals.get('A').score,55)
  assert.equal(signals.get('B').score,53)
  assert.equal(aggregateBehaviorSignals([],now).size,0)
})

test('diversity reranker reserves unseen quota without changing match scores', () => {
  const candidates = [
    {job_id:'A',fused_score:95,matched_skills:['Python','SQL'],missing_skills:[]},
    {job_id:'B',fused_score:94,matched_skills:['Python','SQL'],missing_skills:[]},
    {job_id:'C',fused_score:80,matched_skills:['Java'],missing_skills:['Redis']},
    {job_id:'D',fused_score:79,matched_skills:['React'],missing_skills:['CSS']},
  ]
  const result = diversifyRanking(candidates,['A','B'],{limit:4,explorationQuota:.5})
  assert.equal(result.metrics.unseenSelected,2)
  assert.equal(result.candidates[0].fused_score,95)
  assert.ok(result.metrics.intraListDiversity > 0)
  assert.equal(result.candidates.every(item => item.diversity_rerank),true)
})

test('gap priority favors important evidence-backed demand and lower learning cost', () => {
  const core = gapPriorityScore({requirementImportance:1,marketDemand:.8,evidenceConfidence:.95,careerRelevance:1,learningCost:1})
  const mention = gapPriorityScore({requirementImportance:.35,marketDemand:.4,evidenceConfidence:.7,careerRelevance:.4,learningCost:2})
  assert.ok(core.raw > mention.raw * 10)
  assert.equal(core.factors.learningCost,1)
})

test('Item-CF is case-insensitive and bounded', () => {
  assert.equal(weightedJaccard(['PYTHON'], ['python']), 1)
  assert.equal(weightedJaccard([], []), 0)
})

test('fusion score is the persisted final score', () => {
  const score = fuseMatchScore({
    skillScore: 80,
    semanticScore: 60,
    cfScore: 40,
    feedbackAdjust: 2,
    weights: { skill: 0.5, semantic: 0.3, cf: 0.2 },
  })
  assert.equal(score, 68)
  assert.equal(matchLevel(score), 'medium')
})

test('matchLevel is four-tier and prefers the concrete JD tier', () => {
  assert.equal(matchLevel(68), 'medium')
  assert.equal(matchLevel(85), 'high')
  assert.equal(matchLevel(25), 'low')
  assert.equal(matchLevel(5), 'none')
  assert.equal(matchLevel(68, 0), 'none')
  assert.equal(matchLevel(68, 1), 'low')
  assert.equal(matchLevel(68, 2), 'medium')
  assert.equal(matchLevel(68, 3), 'high')
})
