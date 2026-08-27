import test from 'node:test'
import assert from 'node:assert/strict'
import { createEvidenceRag } from './rag-core.js'
import { readFileSync } from 'fs'

const rag = createEvidenceRag(new URL('..', import.meta.url).pathname.replace(/^\/(.:)/, '$1'))
test('grounded facts all cite existing evidence', () => {
  const result = rag.groundedResponse('Python 岗位需要哪些能力')
  assert.equal(result.status, 'grounded')
  assert.equal(result.citation_coverage, 1)
  assert.ok(result.facts.every(x => x.evidence_ids.length === 1))
})
test('unknown query refuses to answer', () => {
  const result = rag.groundedResponse('XQZV9999 FLORBAX NULLEX 技能')
  assert.equal(result.status, 'insufficient_evidence')
  assert.equal(result.answer, '证据不足')
})
test('published response schema covers citation gate fields', () => {
  const root = new URL('..', import.meta.url).pathname.replace(/^\/(.:)/, '$1')
  const schema = JSON.parse(readFileSync(`${root}/crawler/config/rag_response.schema.json`, 'utf8'))
  assert.deepEqual(schema.required, ['status', 'answer', 'facts', 'evidence', 'citation_coverage', 'algorithm_version'])
  assert.equal(schema.properties.facts.items.properties.evidence_ids.minItems, 1)
})
test('retrieval ablations expose single-channel modes',()=>{for(const mode of ['bm25','ontology','graph'])assert.ok(rag.search('Python 岗位能力',5,[],{mode}).length>0)})
test('generated skills outside retrieved evidence enter human review',()=>{const grounded=rag.groundedResponse('Python 岗位能力');const result=rag.validateGeneratedSkills(['Python','虚构技能'],grounded);assert.equal(result.passed,false);assert.equal(result.review_queue[0].status,'pending_human_review')})
