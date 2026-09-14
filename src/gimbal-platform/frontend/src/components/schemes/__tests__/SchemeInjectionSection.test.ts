import { describe, it, expect } from 'vitest'
import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SchemeInjectionSection from '../SchemeInjectionSection.vue'

const ENTRIES = [
  { id: 'inj-1', label: '步骤0 $.a.b' },
  { id: 'inj-2', label: '步骤1 $.c' },
  { id: 'inj-dead', label: '步骤9 $.gone' },
]

describe('SchemeInjectionSection', () => {
  it('死条目禁选且灰显', () => {
    const w = mount(SchemeInjectionSection, {
      props: { modelValue: [], entries: ENTRIES, deadIds: new Set(['inj-dead']) },
      global: { plugins: [ElementPlus] },
    })
    const boxes = w.findAll('input[type="checkbox"]')
    expect(boxes[2].attributes('disabled')).toBeDefined()
    expect((boxes[2].element as HTMLInputElement).disabled).toBe(true)
  })

  it('勾选发出 update:modelValue;管理按钮跳断言编辑器', async () => {
    const w = mount(SchemeInjectionSection, {
      props: { modelValue: [], entries: ENTRIES, deadIds: new Set<string>() },
      global: { plugins: [ElementPlus] },
    })
    await w.findAll('input[type="checkbox"]')[0].setValue(true)
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual(['inj-1'])
    await w.find('[data-testid="manage-assertions"]').trigger('click')
    expect(w.emitted('manage')).toHaveLength(1)
  })

  it('快建弹层确认发出 quickCreate', async () => {
    const w = mount(SchemeInjectionSection, {
      props: { modelValue: [], entries: [], deadIds: new Set<string>() },
      global: { plugins: [ElementPlus] },
    })
    await w.find('[data-testid="quick-add"]').trigger('click')
    await w.find('[data-testid="qa-step"]').setValue('0')
    await w.find('[data-testid="qa-path"]').setValue('$.x.y')
    await w.find('[data-testid="qa-ok"]').trigger('click')
    expect(w.emitted('quickCreate')!.at(-1)![0]).toEqual({ stepIndex: 0, jsonpath: '$.x.y' })
  })

  // §13 T6-1:快建失败回调化 — 壳 PUT 失败调 onDone(false),弹层保持
  // 打开、输入保留(乐观关闭会把用户输入吞掉);成功 onDone(true) 才关闭
  it('快建失败回调:onDone(false) → 弹层仍开、输入保留;onDone(true) → 关闭', async () => {
    const w = mount(SchemeInjectionSection, {
      props: { modelValue: [], entries: [], deadIds: new Set<string>() },
      global: { plugins: [ElementPlus] },
    })
    await w.find('[data-testid="quick-add"]').trigger('click')
    await w.find('[data-testid="qa-step"]').setValue('2')
    await w.find('[data-testid="qa-path"]').setValue('$.retry.me')
    await w.find('[data-testid="qa-ok"]').trigger('click')
    // emit 契约:[draft, onDone] — 第二参为结果回调
    const call = w.emitted('quickCreate')!.at(-1)!
    expect(call[0]).toEqual({ stepIndex: 2, jsonpath: '$.retry.me' })
    expect(typeof call[1]).toBe('function')
    const onDone = call[1] as (ok: boolean) => void

    onDone(false)   // 壳 PUT 失败 → 弹层保持打开、输入原样保留可改后重试
    await nextTick()
    expect(w.find('[data-testid="qa-path"]').exists()).toBe(true)
    expect((w.find('[data-testid="qa-step"]').element as HTMLInputElement).value).toBe('2')
    expect((w.find('[data-testid="qa-path"]').element as HTMLInputElement).value).toBe('$.retry.me')

    onDone(true)    // 壳 PUT 成功 → 弹层关闭
    await nextTick()
    expect(w.find('[data-testid="qa-path"]').exists()).toBe(false)
  })
})
