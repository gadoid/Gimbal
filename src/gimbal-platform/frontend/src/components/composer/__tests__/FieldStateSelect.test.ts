/** FieldStateSelect — 三态下拉;noCarry 门禁(2026-09-14 §4.4)。 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FieldStateSelect from '@/components/composer/FieldStateSelect.vue'

describe('FieldStateSelect — noCarry', () => {
  it('缺省三态齐(现行为)', () => {
    const w = mount(FieldStateSelect, { props: { state: 'form' } })
    expect(w.findAll('option').map((o) => o.attributes('value')))
      .toEqual(['form', 'collapse', 'carry'])
  })
  it('noCarry → carry 选项缺席', () => {
    const w = mount(FieldStateSelect, { props: { state: 'form', noCarry: true } })
    expect(w.findAll('option').map((o) => o.attributes('value')))
      .toEqual(['form', 'collapse'])
  })
})
