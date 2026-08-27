const publicApiPaths = new Set(['/api/health', '/api/login', '/api/register'])

const apiPath = (input) => {
  try {
    const raw = typeof input === 'string' ? input : input?.url
    if (!raw) return ''
    return new URL(raw, window.location.origin).pathname
  } catch {
    return ''
  }
}

export function installAuthenticatedFetch() {
  if (window.__talentGraphAuthFetchInstalled) return
  window.__talentGraphAuthFetchInstalled = true

  const nativeFetch = window.fetch.bind(window)
  window.fetch = async (input, init = {}) => {
    const path = apiPath(input)
    const protectedApi = path.startsWith('/api/') && !publicApiPaths.has(path)
    const token = protectedApi ? localStorage.getItem('token') : ''
    const headers = new Headers(input instanceof Request ? input.headers : undefined)
    new Headers(init.headers || {}).forEach((value, key) => headers.set(key, value))
    if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)

    const response = await nativeFetch(input, { ...init, headers })
    if (protectedApi && response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      localStorage.removeItem('remember_login')
      if (!['/signin', '/register'].includes(window.location.pathname)) {
        window.location.assign('/signin')
      }
    }
    return response
  }
}
