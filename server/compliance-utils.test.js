import test from 'node:test'
import assert from 'node:assert/strict'
import { allowedMatchingProfile, matchingFeatureAudit } from './compliance-utils.js'

test('matching profile excludes direct and sensitive identifiers', () => {
  const profile = allowedMatchingProfile({ major:'软件工程', degree:'本科', target_direction:'后端', real_name:'张三', gender:'男', age:22, phone:'13800138000' })
  assert.deepEqual(profile, { major:'软件工程', degree:'本科', target_direction:'后端', target_industry:'', target_city:'' })
})

test('sensitive-field changes cannot alter allowed ranking features', () => {
  const base = { major:'计算机', degree:'硕士', target_direction:'算法', target_industry:'互联网', target_city:'北京' }
  const first = allowedMatchingProfile({ ...base, real_name:'甲', gender:'女', age:21, ethnicity:'A' })
  const second = allowedMatchingProfile({ ...base, real_name:'乙', gender:'男', age:55, ethnicity:'B' })
  assert.deepEqual(first, second)
  assert.equal(matchingFeatureAudit({ ...base, gender:'女' }).sensitive_features_used, false)
})
