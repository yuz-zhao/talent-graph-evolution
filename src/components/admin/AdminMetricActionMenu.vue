<template>
  <div class="relative inline-flex">
    <button
      ref="trigger"
      class="text-gray-400 hover:text-gray-600"
      @click.stop="toggleMenu"
      @mousedown.prevent
      aria-haspopup="true"
      :aria-expanded="open"
    >
      <svg class="w-5 h-5 fill-current" viewBox="0 0 32 32">
        <circle cx="16" cy="16" r="2" />
        <circle cx="10" cy="16" r="2" />
        <circle cx="22" cy="16" r="2" />
      </svg>
    </button>
    <transition
      enter-active-class="transition ease-out duration-200 transform"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition ease-out duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-show="open"
        ref="dropdown"
        class="origin-top-right z-30 absolute top-full right-0 min-w-[160px] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700/60 py-1.5 rounded-lg shadow-lg overflow-hidden mt-1"
      >
        <ul class="text-sm" @click="open = false">
          <li>
            <button class="w-full text-left flex items-center py-1.5 px-3 text-gray-600 dark:text-gray-300 hover:bg-violet-50 dark:hover:bg-violet-500/10 hover:text-violet-600" @click.stop="$emit('view-detail')">
              <svg class="w-3.5 h-3.5 mr-2 fill-current text-gray-400" viewBox="0 0 16 16"><path d="M9.5 8a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Z"/><path d="M15.6 7.2C14.1 4.7 11.3 2 8 2 4.7 2 1.9 4.7.4 7.2a1.8 1.8 0 0 0 0 1.6C1.9 11.3 4.7 14 8 14c3.3 0 6.1-2.7 7.6-5.2a1.8 1.8 0 0 0 0-1.6ZM8 11.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7Z"/></svg>
              查看指标详情
            </button>
          </li>
          <li>
            <button class="w-full text-left flex items-center py-1.5 px-3 text-gray-600 dark:text-gray-300 hover:bg-violet-50 dark:hover:bg-violet-500/10 hover:text-violet-600" @click.stop="$emit('export-metric')">
              <svg class="w-3.5 h-3.5 mr-2 fill-current text-gray-400" viewBox="0 0 16 16"><path d="M8.8 3.2a1 1 0 0 0-1.6 0L4.2 7.5a1 1 0 0 0 .8 1.5H7v5a1 1 0 0 0 2 0V9h2a1 1 0 0 0 .8-1.5L8.8 3.2Z"/><path d="M14 0H2a2 2 0 0 0-2 2v2a1 1 0 0 0 2 0V2h12v2a1 1 0 0 0 2 0V2a2 2 0 0 0-2-2Z"/></svg>
              导出当前指标
            </button>
          </li>
          <li>
            <button class="w-full text-left flex items-center py-1.5 px-3 text-gray-600 dark:text-gray-300 hover:bg-violet-50 dark:hover:bg-violet-500/10 hover:text-violet-600" @click.stop="$emit('refresh-metric')">
              <svg class="w-3.5 h-3.5 mr-2 fill-current text-gray-400" viewBox="0 0 16 16"><path d="M5 8a1 1 0 0 0-1-1H.5a.5.5 0 0 0-.5.5V12a1 1 0 0 0 2 0v-1.3a7 7 0 0 0 11.1 2A1 1 0 0 0 11.4 11a5 5 0 0 1-6.7-.5L7.4 9A1 1 0 0 0 7 8H5Z"/><path d="M15.5 4H12a1 1 0 0 0 0 2h1.3a7 7 0 0 0-11.1-2A1 1 0 0 0 4.6 5a5 5 0 0 1 6.7.5L8.6 7A1 1 0 0 0 9 9h2a1 1 0 0 0 1-1V5.5a.5.5 0 0 0-.5-.5h0Z"/></svg>
              刷新该指标
            </button>
          </li>
        </ul>
      </div>
    </transition>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'

export default {
  name: 'AdminMetricActionMenu',
  emits: ['view-detail', 'export-metric', 'refresh-metric'],
  setup() {
    const open = ref(false)
    const trigger = ref(null)
    const dropdown = ref(null)
    let clickHandler = null

    const toggleMenu = () => {
      open.value = !open.value
    }

    onMounted(() => {
      clickHandler = ({ target }) => {
        if (!open.value) return
        if (dropdown.value && (dropdown.value.contains(target) || trigger.value.contains(target))) return
        open.value = false
      }
      document.addEventListener('click', clickHandler)
    })

    onUnmounted(() => {
      if (clickHandler) document.removeEventListener('click', clickHandler)
    })

    return { open, trigger, dropdown, toggleMenu }
  },
}
</script>
