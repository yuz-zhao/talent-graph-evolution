import test from 'node:test';import assert from 'node:assert/strict';import{lagPublicView,lineagePublicView}from'./evidence-governance.js'
test('maps best lead and forbids causal claims',()=>{const x=lagPublicView({status:'exploratory',best_lead_months:2});assert.equal(x.lag_months,2);assert.equal(x.causal_claim,false)})
test('exposes lineage',()=>assert.equal(lineagePublicView({batch_id:'b',graph_relation_row:8}).graph_relation_row,8))
