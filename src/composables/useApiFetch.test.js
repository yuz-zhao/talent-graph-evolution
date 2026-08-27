import { describe, expect, it, vi } from 'vitest'
import { useApiFetch } from './useApiFetch.js'

describe('useApiFetch', () => {
  it('publishes data and resets loading after a successful request', async () => {
    const fetcher = vi.fn().mockResolvedValue({ jobs: [1, 2] })
    const api = useApiFetch(fetcher)

    const result = await api.execute('python')

    expect(fetcher).toHaveBeenCalledWith('python')
    expect(result).toEqual({ jobs: [1, 2] })
    expect(api.data.value).toEqual({ jobs: [1, 2] })
    expect(api.loading.value).toBe(false)
    expect(api.error.value).toBeNull()
  })

  it('converts a rejected request into visible error state', async () => {
    const api = useApiFetch(() => Promise.reject(new Error('network down')))

    const result = await api.execute()

    expect(result).toBeNull()
    expect(api.error.value).toBe('network down')
    expect(api.refreshMessage.value).toContain('network down')
    expect(api.loading.value).toBe(false)
  })

  it('sets and clears refresh messages', () => {
    const api = useApiFetch(vi.fn())

    api.setSuccessMessage('刷新完成')
    expect(api.refreshMessage.value).toBe('刷新完成')
    api.resetMessage()
    expect(api.refreshMessage.value).toBe('')
  })
})
