export const SHARED_ADMIN_CAPABILITIES = new Set([
  'GET /new-jobs/clusters',
  'POST /new-jobs/ai-define',
])

export function extractBearerToken(authorization) {
  const value = String(authorization || '')
  return value.startsWith('Bearer ') ? value.slice(7).trim() : ''
}

export function canAccessAdminApi(user, method, path) {
  return user?.role === 'admin' || SHARED_ADMIN_CAPABILITIES.has(`${method} ${path}`)
}

export function authenticatedUserId(user) {
  return Number(user?.id) || 0
}
