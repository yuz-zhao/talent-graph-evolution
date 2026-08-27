import test from 'node:test'
import assert from 'node:assert/strict'
import { compareMatchSnapshots, verifyLearningEvidence } from './learning-closure.js'

test('course clicks alone cannot promote a skill',()=>assert.equal(verifyLearningEvidence({completed_tasks:5,total_tasks:5,assessment_score:79,evidence_url:'https://example.com/work'}).passed,false))
test('assessment and HTTPS work evidence close the learning gate',()=>assert.equal(verifyLearningEvidence({completed_tasks:5,total_tasks:5,assessment_score:88,evidence_url:'https://github.com/example/work'}).passed,true))
test('compares before and after matching snapshots',()=>assert.equal(compareMatchSnapshots([{job_name:'A',match_score:60}],[{job_name:'A',match_score:72}]).same_job_delta,12))
