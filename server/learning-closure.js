export function verifyLearningEvidence(input = {}) {
  const assessmentScore = Number(input.assessment_score)
  const evidenceUrl = String(input.evidence_url || '').trim()
  const completedTasks = Number(input.completed_tasks || 0)
  const totalTasks = Number(input.total_tasks || 0)
  const urlValid = /^https:\/\//i.test(evidenceUrl)
  const passed = totalTasks > 0 && completedTasks === totalTasks && assessmentScore >= 80 && assessmentScore <= 100 && urlValid
  return {
    passed,
    assessmentScore,
    evidenceUrl: urlValid ? evidenceUrl : null,
    gates: { all_tasks_completed:totalTasks > 0 && completedTasks === totalTasks, assessment_passed:assessmentScore >= 80 && assessmentScore <= 100, evidence_url_valid:urlValid },
    reason: passed ? null : 'completion_requires_all_tasks_assessment_80_and_https_evidence',
  }
}

export function compareMatchSnapshots(before = [], after = []) {
  const top = rows => [...rows].sort((a,b)=>Number(b.match_score)-Number(a.match_score))[0] || null
  const b=top(before),a=top(after)
  const byJob=new Map(after.map(x=>[String(x.job_name),x]))
  const comparable=b ? byJob.get(String(b.job_name)) : null
  return { before_top:b, after_top:a, same_job_delta:comparable&&b ? Number(comparable.match_score)-Number(b.match_score) : null, top_score_delta:a&&b ? Number(a.match_score)-Number(b.match_score) : null }
}
