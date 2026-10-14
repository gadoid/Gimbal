/**
 * utils/ansi — 剥除测试(AD8 层 4)。
 */
import { describe, it, expect } from 'vitest'
import { stripAnsi, hasAnsi } from '@/utils/ansi'

describe('stripAnsi / hasAnsi', () => {
  it('剥除 SGR 色码与归零序列', () => {
    expect(stripAnsi('\x1b[32mOK\x1b[0m')).toBe('OK')
    expect(stripAnsi('\x1b[1m\x1b[36m2026\x1b[0m | INFO')).toBe('2026 | INFO')
  })

  it('剥除非 SGR 转义(光标/OSC)', () => {
    expect(stripAnsi('a\x1b[2Kb')).toBe('ab')
    expect(stripAnsi('x\x1b]0;title\x07y')).toBe('xy')
  })

  it('无转义原样返回;hasAnsi 判定', () => {
    expect(stripAnsi('plain 中文 ✓')).toBe('plain 中文 ✓')
    expect(hasAnsi('plain')).toBe(false)
    expect(hasAnsi('\x1b[31mred')).toBe(true)
  })
})
