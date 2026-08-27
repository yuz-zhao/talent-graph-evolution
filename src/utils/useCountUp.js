import { ref, watch } from 'vue'

/**
 * 数字滚动计数 composable
 * @param {import('vue').Ref<number>|number} target — 目标数值（响应式或静态）
 * @param {object} options
 * @param {number} options.duration — 动画时长 ms，默认 800
 * @param {function} options.easing — 缓动函数，默认 easeOutCubic
 * @param {boolean} options.format — 是否格式化逗号分隔，默认 true
 * @returns {{ display: import('vue').Ref<string>, animating: import('vue').Ref<boolean>, start: function }}
 */
export function useCountUp(target, options = {}) {
  const { duration = 800, format = true } = options

  const display = ref('0')
  const animating = ref(false)

  const fmt = (n) => {
    if (!format) return String(Math.round(n))
    return Math.round(n).toLocaleString('en-US')
  }

  const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3)

  let rafId = null

  const animate = (from, to) => {
    if (rafId) cancelAnimationFrame(rafId)
    const startTime = performance.now()
    animating.value = true

    const step = (now) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = easeOutCubic(progress)
      const current = from + (to - from) * eased
      display.value = fmt(current)

      if (progress < 1) {
        rafId = requestAnimationFrame(step)
      } else {
        display.value = fmt(to)
        animating.value = false
      }
    }

    rafId = requestAnimationFrame(step)
  }

  const start = (from = 0) => {
    const to = typeof target === 'object' && 'value' in target ? target.value : target
    animate(from, Number(to) || 0)
  }

  // If target is a ref, watch for changes
  if (typeof target === 'object' && 'value' in target) {
    watch(target, (val) => {
      animate(0, Number(val) || 0)
    })
  }

  return { display, animating, start }
}

export default useCountUp
