import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useUserStore } from './user.js'

describe('user store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('normalizes nested API user data and persists it', () => {
    const store = useUserStore()
    store.setUser({ data: { user: { username: 'admin', realName: '管理员', role: 'admin' } } })

    expect(store.username).toBe('admin')
    expect(store.realName).toBe('管理员')
    expect(store.isLoggedIn).toBe(true)
    expect(store.isAdmin).toBe(true)
    expect(JSON.parse(localStorage.getItem('user')).real_name).toBe('管理员')
  })

  it('loads a stored user and applies safe defaults', () => {
    localStorage.setItem('user', JSON.stringify({ username: 'candidate' }))
    const store = useUserStore()

    expect(store.username).toBe('candidate')
    expect(store.role).toBe('user')
    expect(store.isAdmin).toBe(false)
  })

  it('ignores malformed storage and clears all login keys', () => {
    localStorage.setItem('user', '{broken json')
    const store = useUserStore()
    expect(store.isLoggedIn).toBe(false)

    store.setUser({ username: 'candidate' })
    localStorage.setItem('token', 'token')
    localStorage.setItem('remember_login', '1')
    store.clearUser()

    expect(store.user).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('remember_login')).toBeNull()
  })
})
