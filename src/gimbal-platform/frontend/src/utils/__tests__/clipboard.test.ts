/**
 * clipboard.ts — 双通道剪贴板(clipboard API 主 + execCommand 回退)。
 * F 用例: 主通道成功;主通道缺失/抛错时回退 execCommand;回退后 DOM 清理。
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { copyText } from '@/utils/clipboard'

describe('copyText', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('主通道: navigator.clipboard.writeText 成功 → true 且传参正确', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    await expect(copyText('${var.bl_no}')).resolves.toBe(true)
    expect(writeText).toHaveBeenCalledWith('${var.bl_no}')
  })

  it('回退通道: clipboard 缺失 → execCommand(copy),textarea 用后即删', async () => {
    const orig = navigator.clipboard
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    const exec = vi.fn(() => true)
    document.execCommand = exec as unknown as typeof document.execCommand
    await expect(copyText('abc')).resolves.toBe(true)
    expect(exec).toHaveBeenCalledWith('copy')
    expect(document.querySelector('textarea')).toBeNull() // DOM 已清理
    Object.defineProperty(navigator, 'clipboard', { value: orig, configurable: true })
  })

  it('主通道抛错 → 落到回退通道', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    Object.assign(navigator, { clipboard: { writeText } })
    const exec = vi.fn(() => true)
    document.execCommand = exec as unknown as typeof document.execCommand
    await expect(copyText('x')).resolves.toBe(true)
    expect(exec).toHaveBeenCalled()
  })
})
