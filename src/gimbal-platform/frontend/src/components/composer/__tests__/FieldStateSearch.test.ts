/**
 * FieldStateSearch — 字段找回搜索框(2026-09-07 spec §2.2):
 * 全量语料(含 carry)过滤、命中行状态上抛(select/reset —— 级联与
 * 批量落地归 Canvas,§2.3/§2.4)、防抖 200ms、>50 折叠、ESC/失焦清面板。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import FieldStateSearch from '../FieldStateSearch.vue'
import type { FieldSearchRow } from '@/utils/declarations'
import type { FieldState } from '@/types/plate'

function mkRow(over: Partial<FieldSearchRow> = {}): FieldSearchRow {
  return {
    path: '$.x', name: 'x', description: '', type: 'string',
    resolved: 'form', overlay: false, breadcrumb: '',
    ...over,
  }
}

const CORPUS: FieldSearchRow[] = [
  mkRow({
    path: '$.supplier', name: 'supplier', type: 'object',
    resolved: 'carry', breadcrumb: '',
  }),
  mkRow({
    path: '$.supplier.contact.phone', name: 'phone',
    resolved: 'form', breadcrumb: 'supplier › contact',
  }),
  mkRow({
    path: '$.remark', name: 'remark', description: '订单备注',
    resolved: 'form', overlay: true,
  }),
]

async function type(wrapper: ReturnType<typeof mount>, text: string) {
  await wrapper.find('input.fss-search-input').setValue(text)
  vi.advanceTimersByTime(200)
  await Promise.resolve()
}

describe('FieldStateSearch — 渲染与过滤', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('挂载渲染输入框(placeholder 点明含 carry 语料)', () => {
    const w = mount(FieldStateSearch, { props: { corpus: CORPUS } })
    const input = w.find('input.fss-search-input')
    expect(input.exists()).toBe(true)
    expect(input.attributes('placeholder')).toContain('carry')
  })

  it('空查询不渲染结果面板(定位语义,非全量清单)', async () => {
    const w = mount(FieldStateSearch, { props: { corpus: CORPUS } })
    await type(w, '')
    expect(w.find('.fss-search-panel').exists()).toBe(false)
  })

  it('name/path/description 大小写不敏感子串过滤', async () => {
    const w = mount(FieldStateSearch, { props: { corpus: CORPUS } })
    await type(w, 'PHONE')
    expect(w.findAll('.fss-search-row')).toHaveLength(1)
    expect(w.find('.fss-search-row').text()).toContain('phone')

    await type(w, '$.supplier')
    expect(w.findAll('.fss-search-row')).toHaveLength(2)

    await type(w, '订单备注')
    expect(w.findAll('.fss-search-row')).toHaveLength(1)

    await type(w, 'zzz-不存在')
    expect(w.find('.fss-search-panel').exists()).toBe(false)
  })

  it('命中 >50 折叠为前 50 + 计数提示', async () => {
    const big = Array.from({ length: 60 }, (_, i) =>
      mkRow({ path: `$.f${i}`, name: `f${i}` }))
    const w = mount(FieldStateSearch, { props: { corpus: big } })
    await type(w, 'f')
    expect(w.findAll('.fss-search-row')).toHaveLength(50)
    expect(w.find('.fss-search-more').text()).toContain('60')
  })

  it('ESC 清空查询与面板', async () => {
    const w = mount(FieldStateSearch, { props: { corpus: CORPUS } })
    await type(w, 'phone')
    expect(w.find('.fss-search-panel').exists()).toBe(true)
    await w.find('input.fss-search-input').trigger('keydown.esc')
    expect((w.find('input.fss-search-input').element as HTMLInputElement).value).toBe('')
    expect(w.find('.fss-search-panel').exists()).toBe(false)
  })

  it('失焦收起面板(v-if 移除;面板 mousedown.prevent 防点击丢焦)', async () => {
    const w = mount(FieldStateSearch, { props: { corpus: CORPUS } })
    await type(w, 'phone')
    expect(w.find('.fss-search-panel').exists()).toBe(true)
    await w.find('input.fss-search-input').trigger('blur')
    expect(w.find('.fss-search-panel').exists()).toBe(false)
    // 重新聚焦 + 查询仍在 → 面板回来(查询词不清,继续缩小范围)
    await w.find('input.fss-search-input').trigger('focus')
    expect(w.find('.fss-search-panel').exists()).toBe(true)
  })
})

describe('FieldStateSearch — 状态上抛(级联归 Canvas)', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('命中行选择状态 → emit select(path, target)', async () => {
    const w = mount(FieldStateSearch, { props: { corpus: CORPUS } })
    await type(w, 'supplier')
    const sel = w.find('.fss-search-row select.fss-sel')
    await sel.setValue('carry')
    const emitted = w.emitted<{ 0: string; 1: FieldState }[]>('select')
    expect(emitted).toBeTruthy()
    expect(emitted![0]).toEqual(['$.supplier', 'carry'])
  })

  it('overlay 行 ↺ → emit reset(path)', async () => {
    const w = mount(FieldStateSearch, { props: { corpus: CORPUS } })
    await type(w, 'remark')
    await w.find('.fss-search-row button.fss-reset').trigger('click')
    expect(w.emitted<'$.remark'[]>('reset')![0]).toEqual(['$.remark'])
  })
})
