/**
 * FieldForm — enum 顺车票(2026-09-07 spec §7.1):
 * plate 目录在 action/active_tab/sort_order 等 ui_kind='text' 字段上回填了
 * enum,但主面 select 分支条件含 `ui_kind === 'select'` 合取,先命中的
 * text 分支把它渲染成 text input —— select 通道从未生效。
 * 规则:enum 非空即 select,优先于一切 ui_kind 分支;number 型 enum
 * 写值经 Number 包裹(select.value 恒为 string);回显 String() 匹配。
 */
import { describe, expect, it } from 'vitest'
import { h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FieldForm from '../FieldForm.vue'
import type { IOFieldBinding } from '@/types/plate'

function mountField(entry: Partial<IOFieldBinding>, body: unknown) {
  const b = ref(body as any)
  const w = mount({
    setup() {
      return () => h(FieldForm, {
        bindings: [{ name: 'f', path: '$.f', required: false, description: '',
                     default: null, example: null, enum: null,
                     ui_kind: 'unknown', source_kind: 'independent', ...entry } as IOFieldBinding],
        body: b.value,
        'onUpdate:body': (v: unknown) => { b.value = v },
      })
    },
  }, { global: { plugins: [ElementPlus] } })
  return { w, b }
}

describe('FieldForm enum 通道(spec §7.1)', () => {
  it('ui_kind=text + enum → select', () => {
    const { w } = mountField({ ui_kind: 'text', enum: ['a', 'b'] }, {})
    expect(w.find('select.ctl').exists()).toBe(true)
  })

  it('ui_kind=unknown + enum → select', () => {
    const { w } = mountField({ ui_kind: 'unknown', enum: ['a'] }, {})
    expect(w.find('select.ctl').exists()).toBe(true)
  })

  it('enum 选择写字面量(string)', async () => {
    const { w, b } = mountField({ ui_kind: 'text', enum: ['a', 'b'] }, {})
    await (w.find('select.ctl').element as HTMLSelectElement) &&
      await w.find('select.ctl').setValue('b')
    expect(b.value.f).toBe('b')
  })

  it('number 型 enum 写值为 number 非 "1"(§7.1 number 陷阱)', async () => {
    const { w, b } = mountField({ ui_kind: 'text', type: 'integer',
                                  enum: [1, 2] }, {})
    await w.find('select.ctl').setValue('2')
    expect(b.value.f).toBe(2)
    expect(typeof b.value.f).toBe('number')
  })

  it('body 已有 number 值时 select 正确回显(不显空)', () => {
    const { w } = mountField({ ui_kind: 'text', type: 'integer', enum: [1, 2] }, { f: 2 })
    const sel = w.find('select.ctl').element as HTMLSelectElement
    expect(sel.value).toBe('2')
  })

  it('模板串降级 text 输入(既有行为保持)', () => {
    const { w } = mountField({ ui_kind: 'select', enum: ['a'] }, { f: '${var.x}' })
    expect(w.find('select.ctl').exists()).toBe(false)
    expect(w.find('input.ctl.tpl').exists()).toBe(true)
  })
})
