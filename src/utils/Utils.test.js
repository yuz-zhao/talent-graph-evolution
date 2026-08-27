import { describe, expect, it, vi } from 'vitest'
import { adjustColorOpacity, formatThousands, formatValue, getCssVariable, oklchToRGBA } from './Utils.js'

describe('display utilities', () => {
  it('formats numeric and invalid values safely', () => {
    expect(formatValue(12500)).toMatch(/1\.25|1\.3|1万/)
    expect(formatValue('invalid')).toBe('0')
    expect(formatThousands(1000)).toBeTruthy()
  })

  it('reads a CSS variable and falls back when it is empty', () => {
    document.documentElement.style.setProperty('--metric-color', '#123456')
    expect(getCssVariable('--metric-color')).toBe('#123456')
    expect(getCssVariable('--missing-color', '#ffffff')).toBe('#ffffff')
  })

  it('adds opacity to supported color formats', () => {
    expect(adjustColorOpacity('#ff0000', 0.5)).toBe('rgba(255, 0, 0, 0.5)')
    expect(adjustColorOpacity('hsl(10, 20%, 30%)', 0.4)).toBe('hsla(10, 20%, 30%, 0.4)')
    expect(adjustColorOpacity('oklch(50% 0.2 30)', 0.3)).toBe('oklch(50% 0.2 30 / 0.3)')
    expect(adjustColorOpacity('', 0.2)).toBe('rgba(107, 114, 128, 0.2)')
    expect(() => adjustColorOpacity('rgb(1, 2, 3)', 0.5)).toThrow('Unsupported color format')
  })

  it('converts a color through computed style and removes its temporary node', () => {
    const styleSpy = vi.spyOn(window, 'getComputedStyle').mockReturnValue({ color: 'rgb(1, 2, 3)' })
    const before = document.body.children.length

    expect(oklchToRGBA('oklch(50% 0.2 30)')).toBe('rgb(1, 2, 3)')
    expect(document.body.children.length).toBe(before)
    expect(styleSpy).toHaveBeenCalledOnce()
  })
})
