import test from 'node:test'
import assert from 'node:assert/strict'
import { authenticatedUserId, canAccessAdminApi, extractBearerToken } from './auth-utils.js'

test('only an Authorization Bearer token is accepted', () => {
  assert.equal(extractBearerToken('Bearer signed-token'), 'signed-token')
  assert.equal(extractBearerToken('Basic abc'), '')
  assert.equal(extractBearerToken('signed-token'), '')
})

test('admin namespace is denied to users except explicit shared capabilities', () => {
  const user = { id: 2, role: 'user' }
  assert.equal(canAccessAdminApi(user, 'GET', '/users'), false)
  assert.equal(canAccessAdminApi(user, 'GET', '/new-jobs/clusters'), true)
  assert.equal(canAccessAdminApi(user, 'POST', '/new-jobs/ai-define'), true)
  assert.equal(canAccessAdminApi(user, 'POST', '/users'), false)
  assert.equal(canAccessAdminApi({ id: 1, role: 'admin' }, 'GET', '/users'), true)
})

test('resource owner id comes from authenticated account', () => {
  assert.equal(authenticatedUserId({ id: 2, role: 'user' }), 2)
  assert.equal(authenticatedUserId(null), 0)
})
