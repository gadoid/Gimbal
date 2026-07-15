/**
 * VarsEditor.vue — Spec-2-5 vars editor (literal + generator specs).
 *
 * Verifies the rendering modes and the literal/spec save validation path.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import VarsEditor from '@/components/VarsEditor.vue'

function mountEditor(props: Record<string, unknown>) {
  return mount(VarsEditor, {
    props,
    global: { plugins: [createPinia(), ElementPlus] },
  })
}

describe('VarsEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders empty state when no vars', () => {
    const w = mountEditor({ modelValue: {} })
    expect(w.find('.el-empty').exists()).toBe(true)
  })

  it('renders one row per existing var', () => {
    const w = mountEditor({
      modelValue: { order_no: 'BIZ-literal', seq: 1 },
    })
    const rows = w.findAll('.ve-table tbody tr')
    expect(rows).toHaveLength(2)
    expect(w.text()).toContain('order_no')
    expect(w.text()).toContain('seq')
  })

  it('renders literal vs spec rows differently', () => {
    const w = mountEditor({
      modelValue: {
        order_no: 'literal-value',
        seq: { kind: 'seq', start: 1 },
      },
    })
    // literal row uses literal-row class, spec row uses spec-row class
    expect(w.find('.literal-row').exists()).toBe(true)
    expect(w.find('.spec-row').exists()).toBe(true)
    // spec row shows the kind tag (canonical "seq"; "sequence" is still
    // accepted by gimbal but the UI canonicalizes on save).
    expect(w.text()).toContain('kind: seq')
    expect(w.text()).toContain('start=1')
  })

  it('shows reference chip ${var.<key>}', () => {
    const w = mountEditor({ modelValue: { foo: 'bar' } })
    expect(w.text()).toContain('${var.foo}')
  })

  it('emits update:modelValue on save with literal', async () => {
    const w = mountEditor({ modelValue: { foo: 'bar' } })
    // Add a row, type key + value, click 保存
    await w.find('.el-button--primary').trigger('click') // + 新增变量
    const inputs = w.findAll('.ve-table tbody tr input')
    // The new row appended; existing 'foo' is row 0; new row is row 1
    await inputs[2].setValue('baz') // key
    await inputs[3].setValue('qux') // value
    await w.findAll('.ve-footer .el-button--primary')[0].trigger('click')
    const events = w.emitted('update:modelValue')
    expect(events).toBeTruthy()
    const payload = (events![0] as [Record<string, unknown>])[0]
    expect(payload).toEqual({ foo: 'bar', baz: 'qux' })
  })

  it('emits spec objects when value is JSON', async () => {
    const w = mountEditor({ modelValue: {} })
    await w.find('.el-button--primary').trigger('click') // + 新增
    const inputs = w.findAll('.ve-table tbody tr input')
    await inputs[0].setValue('seq')
    await inputs[1].setValue('{"kind":"seq","start":5}')
    await w.findAll('.ve-footer .el-button--primary')[0].trigger('click')
    const events = w.emitted('update:modelValue')
    const payload = (events![0] as [Record<string, unknown>])[0]
    expect(payload).toEqual({ seq: { kind: 'seq', start: 5 } })
  })

  it('rejects empty key on save', async () => {
    const w = mountEditor({ modelValue: {} })
    await w.find('.el-button--primary').trigger('click') // + 新增
    const inputs = w.findAll('.ve-table tbody tr input')
    await inputs[1].setValue('value-only') // leave key empty
    await w.findAll('.ve-footer .el-button--primary')[0].trigger('click')
    expect(w.emitted('update:modelValue')).toBeFalsy()
  })

  it('rejects duplicate keys', async () => {
    const w = mountEditor({ modelValue: { foo: 'a' } })
    await w.find('.el-button--primary').trigger('click') // + 新增
    const inputs = w.findAll('.ve-table tbody tr input')
    await inputs[2].setValue('foo') // duplicate
    await inputs[3].setValue('b')
    await w.findAll('.ve-footer .el-button--primary')[0].trigger('click')
    expect(w.emitted('update:modelValue')).toBeFalsy()
  })
})