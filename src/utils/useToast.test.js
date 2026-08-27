import { createApp } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { useToast } from './useToast.js'

describe('useToast', () => {
  it('returns the application-provided toast service', () => {
    const service = { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() }
    const app = createApp({})
    app.provide('$toast', service)

    const result = app.runWithContext(() => useToast())

    expect(result).toBe(service)
  })

  it('uses console methods when no provider is mounted', () => {
    const log = vi.spyOn(console, 'log').mockImplementation(() => {})
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    const info = vi.spyOn(console, 'info').mockImplementation(() => {})
    const toast = useToast()

    toast.success('ok')
    toast.warning('warn')
    toast.error('bad')
    toast.info('info')

    expect(log).toHaveBeenCalledWith('[Toast]', 'ok')
    expect(warn).toHaveBeenCalledWith('[Toast]', 'warn')
    expect(error).toHaveBeenCalledWith('[Toast]', 'bad')
    expect(info).toHaveBeenCalledWith('[Toast]', 'info')
  })
})
