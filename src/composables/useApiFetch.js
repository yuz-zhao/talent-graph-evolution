import { ref, readonly } from 'vue'

/**
 * 统一 API 请求 composable
 * 封装 loading / error / refreshMessage / 数据获取生命周期
 *
 * @param {Function} fetcher - 异步函数，接收参数对象，返回响应数据
 * @returns {{ data, loading, error, refreshMessage, execute, resetMessage }}
 */
export function useApiFetch(fetcher) {
  const data = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const refreshMessage = ref('')

  let lastFetcher = fetcher

  async function execute(...args) {
    loading.value = true
    error.value = null
    refreshMessage.value = ''

    try {
      const result = await (lastFetcher)(...args)
      data.value = result
      return result
    } catch (err) {
      error.value = err?.message || String(err)
      refreshMessage.value = `加载失败: ${error.value}`
      return null
    } finally {
      loading.value = false
    }
  }

  function setSuccessMessage(msg) {
    refreshMessage.value = msg || '数据已刷新'
  }

  function resetMessage() {
    refreshMessage.value = ''
  }

  return {
    data: readonly(data),
    loading: readonly(loading),
    error: readonly(error),
    refreshMessage: readonly(refreshMessage),
    execute,
    setSuccessMessage,
    resetMessage,
  }
}
