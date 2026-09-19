/**
 * SchemeCard — 我的场景内联预览的方案卡。
 * 钉住:最近执行 → 描边/chip 口径一致;次数·并发徽章是可聚焦按钮而非 span,
 * 进编辑即 autofocus;提交落点仅在有变化且界内(越界给一句人话不进 PUT);
 * Esc 撤销不改数据;▶ 执行把整个 scheme 抛给父级。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SchemeCard from '@/components/scenario-lib/SchemeCard.vue'
import { toastState } from '@/utils/toast'
import type { SchemeV2 } from '@/api/scenario-composer'

const scheme = (over: Partial<SchemeV2> = {}): SchemeV2 => ({
  schemeId: 's1', name: '标准回归', isDefault: true, dataSetSelection: [],
  injectionEntryIds: [], serviceBindings: {}, stepTo: null, nRuns: 1, parallel: 1, ...over,
})

function mountCard(s: SchemeV2, lastRun: { status: string; at: string | null } | null, opts = {}) {
  return mount(SchemeCard, { props: { scheme: s, lastRun }, ...opts })
}

/** 找到「次数」/「并发」那枚按钮(编辑态下 input 的 aria-label 不同)。 */
const badge = (w: ReturnType<typeof mountCard>, text: string) =>
  w.findAll('button.mini-badge').find((b) => b.text().includes(text))!

async function edit(w: ReturnType<typeof mountCard>, text: string, value: string) {
  await badge(w, text).trigger('click')
  const input = w.find('.mini-badge.editing input')
  await input.setValue(value)
  await input.trigger('blur')
  await flushPromises()
}

describe('SchemeCard — 方案卡', () => {
  beforeEach(() => toastState.items.splice(0, toastState.items.length))

  it('最近执行状态 → 卡片描边 + chip 同一口径', async () => {
    const cases = [
      ['done', 'st-ok', '完成'],
      ['failed', 'st-bad', '失败'],
      ['running', 'st-run', '执行中'],
    ] as const
    for (const [status, tone, chip] of cases) {
      const w = mountCard(scheme(), { status, at: '2026-09-18T10:00:00' })
      expect(w.find('.scheme-card').classes()).toContain(tone)
      expect(w.find('.status-chip').classes()).toContain(chip === '完成' ? 'ok' : chip === '失败' ? 'bad' : 'run')
      expect(w.find('.status-chip').text()).toBe(chip)
      w.unmount()
    }
    const none = mountCard(scheme(), null)
    expect(none.find('.scheme-card').classes()).not.toContain('st-ok')
    expect(none.find('.status-chip').text()).toBe('未执行')
    none.unmount()
  })

  it('默认方案才挂「默认」徽章', () => {
    expect(mountCard(scheme({ isDefault: false }), null).find('.badge-default').exists()).toBe(false)
    expect(mountCard(scheme(), null).find('.badge-default').exists()).toBe(true)
  })

  it('次数/并发是真按钮且带 aria-label(此前是 span,键盘进不去)', () => {
    const w = mountCard(scheme({ nRuns: 3, parallel: 2 }), null)
    expect(badge(w, '次数').attributes('aria-label')).toContain('修改执行次数')
    expect(badge(w, '次数').text()).toContain('3')
    expect(badge(w, '并发').attributes('aria-label')).toContain('修改并发数')
    expect(badge(w, '并发').text()).toContain('2')
  })

  it('点徽章 → 换成输入框并自动聚焦、原值预填', async () => {
    // attachTo:未挂进 document 的元素 focus() 不改 activeElement
    const w = mountCard(scheme({ nRuns: 7 }), null, { attachTo: document.body })
    await badge(w, '次数').trigger('click')
    await flushPromises()
    const input = w.find('.mini-badge.editing input')
    expect(input.exists()).toBe(true)
    expect((input.element as HTMLInputElement).value).toBe('7')
    expect(document.activeElement).toBe(input.element)
    w.unmount()
  })

  it('合法值 blur → emit update 带 patch', async () => {
    const w = mountCard(scheme({ nRuns: 1 }), null)
    await edit(w, '次数', '4')
    expect(w.emitted('update')?.[0]).toEqual([expect.objectContaining({ schemeId: 's1' }), { nRuns: 4 }])
  })

  it('Enter 提交,Esc 撤销且不 emit', async () => {
    const w = mountCard(scheme({ parallel: 1 }), null)
    await badge(w, '并发').trigger('click')
    const input = w.find('.mini-badge.editing input')
    await input.setValue('6')
    await input.trigger('keyup.enter')
    await flushPromises()
    expect(w.emitted('update')?.[0]?.[1]).toEqual({ parallel: 6 })

    await badge(w, '并发').trigger('click')
    const again = w.find('.mini-badge.editing input')
    await again.setValue('9')
    await again.trigger('keyup.esc')
    await flushPromises()
    expect(w.find('.mini-badge.editing').exists()).toBe(false)
    expect(w.emitted('update')).toHaveLength(1)
  })

  it('越界(0 / 9999)拦下并给范围提示,值回原样', async () => {
    const w = mountCard(scheme({ nRuns: 1, parallel: 1 }), null)
    await edit(w, '并发', '9999')       // 上限 200
    expect(w.emitted('update')).toBeUndefined()
    expect(toastState.items.some((t) => t.kind === 'error' && t.message.includes('1–200'))).toBe(true)
    await edit(w, '次数', '0')          // 下限 1
    expect(w.emitted('update')).toBeUndefined()
    expect(toastState.items.some((t) => t.message.includes('1–500'))).toBe(true)
  })

  it('值没变不落 emit(避免空 PUT)', async () => {
    const w = mountCard(scheme({ nRuns: 5 }), null)
    await edit(w, '次数', '5')
    expect(w.emitted('update')).toBeUndefined()
    await edit(w, '次数', 'abc')
    expect(w.emitted('update')).toBeUndefined()
  })

  it('▶ 执行把整张方案抛给父级', async () => {
    const w = mountCard(scheme(), null)
    await w.find('.run-link').trigger('click')
    expect(w.emitted('run')?.[0]).toEqual([expect.objectContaining({ schemeId: 's1' })])
  })
})
