import test from 'node:test'
import assert from 'node:assert/strict'
import { trainKnn } from './knn-model.js'

test('KNN predicts the nearest labelled neighbourhood', () => {
  const model = trainKnn([
    { x:[0, 0], y:0 }, { x:[0.1, 0], y:0 },
    { x:[1, 1], y:2 }, { x:[0.9, 1], y:2 },
  ], { k:2 })
  assert.equal(model.predict([0.05, 0]), 0)
  assert.equal(model.predict([0.95, 1]), 2)
})

test('KNN probabilities are normalized', () => {
  const model = trainKnn([{ x:[0], y:0 }, { x:[1], y:1 }], { k:2 })
  const probabilities = model.probabilities([0.5])
  assert.ok(Math.abs(probabilities.reduce((a,b)=>a+b,0)-1) < 1e-9)
})
