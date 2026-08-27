<template>
  <teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-start justify-center px-4 sm:px-6" style="padding-top:6rem;">
      <!-- 遮罩层 -->
      <div class="fixed inset-0 bg-gray-900/30 transition-opacity duration-200" @click="$emit('close')"></div>
      <!-- 弹窗面板 -->
      <div
        ref="modalContent"
        class="relative bg-white dark:bg-gray-800 border border-transparent dark:border-gray-700/60 w-full max-w-lg rounded-xl shadow-lg z-10 flex flex-col"
        style="max-height: 75vh;"
        @click.stop
      >
        <!-- 头部 -->
        <div class="shrink-0 px-6 py-5 border-b border-gray-200 dark:border-gray-700/60 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100">指标详情：{{ safe(val.title) }}</h2>
          <button class="text-gray-400 hover:text-gray-600 cursor-pointer p-1 -mr-1" @click="$emit('close')" aria-label="关闭">
            <svg class="w-5 h-5 fill-current" viewBox="0 0 24 24"><path d="M18.7 5.3a1 1 0 0 0-1.4 0L12 10.6 6.7 5.3a1 1 0 1 0-1.4 1.4l5.3 5.3-5.3 5.3a1 1 0 1 0 1.4 1.4l5.3-5.3 5.3 5.3a1 1 0 0 0 1.4-1.4l-5.3-5.3 5.3-5.3a1 1 0 0 0 0-1.4Z"/></svg>
          </button>
        </div>
        <!-- 正文（可滚动） -->
        <div class="overflow-y-auto px-6 py-4 space-y-3 text-sm" v-if="val" style="max-height: 50vh;">
          <div class="grid grid-cols-[100px_1fr] gap-x-4 gap-y-2.5">
            <span class="text-gray-400">指标名称</span><span class="text-gray-800 dark:text-gray-100 font-medium">{{ safe(val.title) }}</span>
            <span class="text-gray-400">当前数值</span><span class="text-gray-800 dark:text-gray-100 font-bold text-lg">{{ safe(val.value, '0') }}</span>
            <span class="text-gray-400">较上月变化</span><span class="text-gray-800 dark:text-gray-100">{{ safe(val.change, '0%') }}</span>
            <span class="text-gray-400">所属页面</span><span class="text-gray-600 dark:text-gray-300">{{ safe(val.pageName) }}</span>
            <span class="text-gray-400">统计范围</span><span class="text-gray-600 dark:text-gray-300">{{ safe(val.range, '全部数据') }}</span>
            <span class="text-gray-400">数据来源</span><span class="text-gray-600 dark:text-gray-300">{{ safe(val.source, '--') }}</span>
            <span class="text-gray-400">更新时间</span><span class="text-gray-600 dark:text-gray-300">{{ safe(val.updatedAt, '--') }}</span>
          </div>
          <div class="pt-3 border-t border-gray-100 dark:border-gray-700/60">
            <div class="text-xs text-gray-400 mb-1.5">指标说明</div>
            <div class="text-sm text-gray-700 dark:text-gray-200 leading-relaxed">{{ safe(val.description, '--') }}</div>
          </div>
          <div v-if="showEmptyTip" class="rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-100 dark:border-amber-500/20 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
            当前暂无真实数据，以上展示为空系统占位视图。
          </div>
        </div>
        <!-- 底部 -->
        <div class="shrink-0 px-6 py-3 border-t border-gray-200 dark:border-gray-700/60 text-right">
          <button class="btn-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 text-xs px-4 cursor-pointer" @click="$emit('close')">关闭</button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'

export default {
  name: 'AdminMetricDetailModal',
  props: {
    open: { type: Boolean, default: false },
    metric: { type: Object, default: () => null },
  },
  emits: ['close'],
  setup(props, { emit }) {
    const modalContent = ref(null)
    const val = computed(() => props.metric)
    const showEmptyTip = computed(() => {
      if (!val.value) return true
      const v = val.value.value
      return v === 0 || v === '0' || v === '0%' || v === '--' || v === null || v === undefined
    })

    const safe = (text, fb = '--') => {
      if (text === null || text === undefined) return fb
      const s = String(text)
      return (s.trim() === '' || s === 'NaN' || s === 'undefined' || s === 'null') ? fb : s
    }

    const handleKeydown = (e) => {
      if (e.key === 'Escape' && props.open) {
        emit('close')
      }
    }

    onMounted(() => {
      document.addEventListener('keydown', handleKeydown)
    })

    onUnmounted(() => {
      document.removeEventListener('keydown', handleKeydown)
    })

    return { modalContent, val, showEmptyTip, safe }
  },
}
</script>
