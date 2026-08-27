import { beforeEach, describe, expect, it, vi } from 'vitest'
import { installAuthenticatedFetch } from './authFetch.js'

describe('installAuthenticatedFetch', () => {
  let nativeFetch

  beforeEach(() => {
    localStorage.clear()
    window.history.replaceState({}, '', '/')
    delete window.__talentGraphAuthFetchInstalled
    nativeFetch = vi.fn().mockResolvedValue({ status: 200 })
    window.fetch = nativeFetch
  })

  it('adds a bearer token only to protected API requests', async () => {
    localStorage.setItem('token', 'secret-token')
    installAuthenticatedFetch()

    await window.fetch('/api/jobs', { headers: { Accept: 'application/json' } })
    const protectedHeaders = nativeFetch.mock.calls[0][1].headers
    expect(protectedHeaders.get('Authorization')).toBe('Bearer secret-token')
    expect(protectedHeaders.get('Accept')).toBe('application/json')

    await window.fetch('/api/login')
    const publicHeaders = nativeFetch.mock.calls[1][1].headers
    expect(publicHeaders.has('Authorization')).toBe(false)
  })

  it('preserves an explicit authorization header', async () => {
    localStorage.setItem('token', 'stored-token')
    installAuthenticatedFetch()

    await window.fetch('/api/profile', { headers: { Authorization: 'Bearer explicit-token' } })

    expect(nativeFetch.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer explicit-token')
  })

  it('clears login state after an unauthorized protected response', async () => {
    window.history.replaceState({}, '', '/signin')
    localStorage.setItem('token', 'expired')
    localStorage.setItem('user', '{"username":"demo"}')
    localStorage.setItem('remember_login', '1')
    nativeFetch.mockResolvedValue({ status: 401 })
    installAuthenticatedFetch()

    await window.fetch('/api/profile')

    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
    expect(localStorage.getItem('remember_login')).toBeNull()
  })

  it('is installed only once', async () => {
    installAuthenticatedFetch()
    const wrappedFetch = window.fetch
    installAuthenticatedFetch()

    expect(window.fetch).toBe(wrappedFetch)
    await window.fetch('/not-api')
    expect(nativeFetch).toHaveBeenCalledOnce()
  })
})
