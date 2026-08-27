<template>
  <div class="relative inline-flex">
    <button
      ref="trigger"
      class="btn bg-white dark:bg-gray-800 border-gray-200 hover:border-gray-300 dark:border-gray-700/60 dark:hover:border-gray-600 text-gray-700 dark:text-gray-200 shadow-xs"
      aria-haspopup="true"
      @click.prevent="dropdownOpen = !dropdownOpen"
      :aria-expanded="dropdownOpen"
    >
      <svg class="shrink-0 text-gray-400 dark:text-gray-500" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="4" width="18" height="18" rx="2" />
        <path d="M16 2v4M8 2v4M3 10h18" />
      </svg>
      <span class="ml-2 text-sm font-medium">统计范围：{{ selectedRange }}</span>
      <svg class="w-3 h-3 shrink-0 ml-2 fill-current text-gray-400 dark:text-gray-500 transition-transform" :class="dropdownOpen && 'rotate-180'" viewBox="0 0 12 12">
        <path d="M5.9 11.4L.5 6l1.4-1.4 4 4 4-4L11.3 6z" />
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
      <div v-show="dropdownOpen" class="origin-top-right z-10 absolute top-full min-w-56 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700/60 py-2 rounded-lg shadow-lg overflow-hidden mt-1" :class="align === 'right' ? 'right-0' : 'left-0'">
        <div ref="dropdown">
          <button
            v-for="range in ranges"
            :key="range"
            class="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700/30"
            :class="selectedRange === range ? 'text-violet-600 dark:text-violet-300 font-medium' : 'text-gray-700 dark:text-gray-200'"
            @click="selectRange(range)"
          >
            <span>{{ range }}</span>
            <span v-if="selectedRange === range" class="w-1.5 h-1.5 rounded-full bg-violet-500"></span>
          </button>

          <div v-if="selectedRange === '自定义时间'" class="px-3 pt-2 pb-3 border-t border-gray-100 dark:border-gray-700/60 mt-1">
            <div class="grid grid-cols-2 gap-2">
              <input class="form-input text-xs px-2 py-1.5" type="date" />
              <input class="form-input text-xs px-2 py-1.5" type="date" />
            </div>
          </div>

          <div class="px-3 pt-2 pb-1 border-t border-gray-100 dark:border-gray-700/60 text-xs text-gray-400">
            最后更新：暂无数据
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'

export default {
  name: 'Datepicker',
  props: ['align'],
  setup() {
    const dropdownOpen = ref(false)
    const selectedRange = ref('全部数据')
    const trigger = ref(null)
    const dropdown = ref(null)
    const ranges = ['全部数据', '近7天', '近30天', '近90天', '本月', '自定义时间']

    const selectRange = (range) => {
      selectedRange.value = range
      if (range !== '自定义时间') dropdownOpen.value = false
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
    })

    onUnmounted(() => {
      document.removeEventListener('click', clickHandler)
      document.removeEventListener('keydown', keyHandler)
    })

    return {
      dropdownOpen,
      selectedRange,
      ranges,
      trigger,
      dropdown,
      selectRange,
    }
  },
}
</script>
