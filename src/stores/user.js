import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const normalizeUser = (data) => data?.user ?? data?.data?.user ?? data

export const useUserStore = defineStore('user', () => {
  // state
  const raw = ref(null)

  // getters
  const user = computed(() => raw.value)
  const isLoggedIn = computed(() => !!raw.value?.username)
  const isAdmin = computed(() => raw.value?.role === 'admin')
  const username = computed(() => raw.value?.username ?? '')
  const realName = computed(() => raw.value?.real_name ?? raw.value?.realName ?? '用户')
  const role = computed(() => raw.value?.role ?? 'user')

  // actions
  function loadFromStorage() {
    try {
      const data = JSON.parse(localStorage.getItem('user') || 'null')
      if (data) raw.value = data
    } catch { /* ignore */ }
  }

  function setUser(data) {
    const u = normalizeUser(data)
    const safe = {
      ...u,
      real_name: u?.real_name || u?.realName || '用户',
      role: u?.role || 'user',
    }
    raw.value = safe
    localStorage.setItem('user', JSON.stringify(safe))
  }

  function clearUser() {
    raw.value = null
    localStorage.removeItem('user')
    localStorage.removeItem('token')
    localStorage.removeItem('remember_login')
  }

  // auto-init
  loadFromStorage()

  return {
    user, isLoggedIn, isAdmin, username, realName, role,
    loadFromStorage, setUser, clearUser,
  }
})
