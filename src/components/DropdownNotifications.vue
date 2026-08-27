<template>
  <div class="relative inline-flex">
    <button
      ref="trigger"
      class="w-8 h-8 flex items-center justify-center hover:bg-gray-100 lg:hover:bg-gray-200 dark:hover:bg-gray-700/50 dark:lg:hover:bg-gray-800 rounded-full"
      :class="{ 'bg-gray-200 dark:bg-gray-800': dropdownOpen }"
      aria-haspopup="true"
      @click.prevent="dropdownOpen = !dropdownOpen"
      :aria-expanded="dropdownOpen"
    >
      <span class="sr-only">通知</span>
      <svg class="fill-current text-gray-500/80 dark:text-gray-400/80" width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
        <path d="M7 0a7 7 0 0 0-7 7c0 1.202.308 2.33.84 3.316l-.789 2.368a1 1 0 0 0 1.265 1.265l2.595-.865a1 1 0 0 0-.632-1.898l-.698.233.3-.9a1 1 0 0 0-.104-.85A4.97 4.97 0 0 1 2 7a5 5 0 0 1 5-5 4.99 4.99 0 0 1 4.093 2.135 1 1 0 1 0 1.638-1.148A6.99 6.99 0 0 0 7 0Z" />
        <path d="M11 6a5 5 0 0 0 0 10c.807 0 1.567-.194 2.24-.533l1.444.482a1 1 0 0 0 1.265-1.265l-.482-1.444A4.962 4.962 0 0 0 16 11a5 5 0 0 0-5-5Zm-3 5a3 3 0 0 1 6 0c0 .588-.171 1.134-.466 1.6a1 1 0 0 0-.115.82 1 1 0 0 0-.82.114A2.973 2.973 0 0 1 11 14a3 3 0 0 1-3-3Z" />
      </svg>
      <div v-if="notifications.length > 0" class="absolute top-0 right-0 w-2.5 h-2.5 bg-red-500 border-2 border-gray-100 dark:border-gray-900 rounded-full"></div>
    </button>

    <transition
      enter-active-class="transition ease-out duration-200 transform"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition ease-out duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-show="dropdownOpen" class="origin-top-right z-10 absolute top-full -mr-48 sm:mr-0 min-w-80 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700/60 py-1.5 rounded-lg shadow-lg overflow-hidden mt-1" :class="align === 'right' ? 'right-0' : 'left-0'">
        <div class="text-xs font-semibold text-gray-400 dark:text-gray-500 pt-1.5 pb-2 px-4">系统通知</div>

        <ul v-if="notifications.length > 0" ref="dropdown" @focusin="dropdownOpen = true" @focusout="dropdownOpen = false">
          <li v-for="item in notifications" :key="item.id || item.title" class="border-b border-gray-200 dark:border-gray-700/60 last:border-0">
            <router-link class="block py-2 px-4 hover:bg-gray-50 dark:hover:bg-gray-700/20" :to="item.link || fallbackLink" @click="openNotification(item)">
              <span class="block text-sm mb-2"><span class="font-medium text-gray-800 dark:text-gray-100">{{ item.title }}</span> {{ item.content }}</span>
              <span class="block text-xs font-medium text-gray-400 dark:text-gray-500">{{ item.date || '--' }}</span>
            </router-link>
          </li>
        </ul>

        <div v-else ref="dropdown" class="px-4 py-8 text-center">
          <div class="mx-auto w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-700/50 flex items-center justify-center mb-3">
            <svg class="w-5 h-5 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 7-3 7h18s-3 0-3-7" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
          </div>
          <div class="text-sm font-medium text-gray-700 dark:text-gray-200">暂无系统通知</div>
          <div class="text-xs text-gray-400 mt-1">接入后端后将自动实时显示</div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'

const normalizeNotifications = (data) => {
  const source = Array.isArray(data) ? data : (Array.isArray(data?.items) ? data.items : [])
  return source.map((item, index) => ({
    id: item.id ?? index,
    title: item.title ?? '系统通知',
    content: item.content ?? item.message ?? '',
    date: item.date ?? item.created_at ?? item.createdAt ?? '--',
    link: item.link || '',
    isRead: Boolean(item.is_read),
  })).filter((item) => item.title || item.content)
}

export default {
  name: 'DropdownNotifications',
  props: ['align'],
  setup() {
    const dropdownOpen = ref(false)
    const trigger = ref(null)
    const dropdown = ref(null)
    const notifications = ref([])
    const fallbackLink = (() => { try { return JSON.parse(localStorage.getItem('user')||'null')?.role === 'admin' ? '/admin/dashboard' : '/user/dashboard' } catch { return '/user/dashboard' } })()
    let timer = null

    const fetchNotifications = async () => {
      try {
        const response = await fetch('/api/notifications', { cache: 'no-store' })
        if (!response.ok) throw new Error(`Notification request failed: ${response.status}`)
        notifications.value = normalizeNotifications(await response.json())
      } catch (error) {
        console.error(error)
        notifications.value = []
      }
    }
    const openNotification = async item => {
      dropdownOpen.value = false
      if (!item.isRead) {
        await fetch(`/api/notifications/${item.id}/read`, { method:'PUT' }).catch(() => null)
        item.isRead = true
      }
    }

    const clickHandler = ({ target }) => {
      if (!dropdownOpen.value || dropdown.value.contains(target) || trigger.value.contains(target)) return
      dropdownOpen.value = false
    }

    const keyHandler = ({ keyCode }) => {
      if (!dropdownOpen.value || keyCode !== 27) return
      dropdownOpen.value = false
    }

    onMounted(() => {
      document.addEventListener('click', clickHandler)
      document.addEventListener('keydown', keyHandler)
      fetchNotifications()
      timer = window.setInterval(fetchNotifications, 30000)
    })

    onUnmounted(() => {
      document.removeEventListener('click', clickHandler)
      document.removeEventListener('keydown', keyHandler)
      if (timer) window.clearInterval(timer)
    })

    return {
      dropdownOpen,
      trigger,
      dropdown,
      notifications,
      fallbackLink,
      openNotification,
    }
  }
}
</script>
