import test from 'node:test'
import assert from 'node:assert/strict'
import { buildGraphFilteredNodeQuery, normalizeGraphFilters } from './graph-filter-query.js'

test('tech stack and level are bound into the backend Cypher query', () => {
  const filters = normalizeGraphFilters({ tech_stack: 'Kubernetes', level: 'senior' })
  const query = buildGraphFilteredNodeQuery(filters, 123)
  assert.equal(query.params.techStack, 'Kubernetes')
  assert.ok(query.params.levelTerms.includes('高级'))
  assert.match(query.cypher, /\$techStack/)
  assert.match(query.cypher, /\$levelTerms/)
  assert.match(query.cypher, /要求技能/)
  assert.match(query.cypher, /LIMIT 123/)
})

test('unknown level cannot be injected into Cypher', () => {
  const query = buildGraphFilteredNodeQuery(normalizeGraphFilters({ level: 'senior\" MATCH (n)' }))
  assert.doesNotMatch(query.cypher, /senior\" MATCH/)
  assert.deepEqual(query.params.levelTerms, [])
})
