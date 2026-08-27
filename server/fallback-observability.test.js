import test from 'node:test'
import assert from 'node:assert/strict'
import { fallbackEvent } from './fallback-observability.js'

test('fallback event exposes stable structured fields', () => {
  const event = fallbackEvent('matching_item_cf', new Error('neo4j unavailable'), { algorithm_mode: 'rule_fallback' })
  assert.equal(event.event, 'algorithm_fallback')
  assert.equal(event.stage, 'matching_item_cf')
  assert.equal(event.reason, 'neo4j unavailable')
  assert.equal(event.context.algorithm_mode, 'rule_fallback')
  assert.match(event.timestamp, /^\d{4}-\d{2}-\d{2}T/)
})
