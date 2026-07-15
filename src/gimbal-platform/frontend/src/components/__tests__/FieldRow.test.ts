/**
 * Regression tests for FieldRow.vue — Spec-1 sign-off bugs.
 *
 * FieldRow renders a label/value/👁 triple. Three behaviors must hold:
 *
 * 1. hidden=true && showHidden=false → row is display:none (collapsed)
 * 2. hidden=true && showHidden=true  → row reveals with .show-hidden class
 * 3. hidden=false (default)         → row is visible normally
 *
 * The eye button toggles the hide path via $emit('toggle-eye').
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import FieldRow from '@/components/FieldRow.vue'
import { useHideStore } from '@/stores/hide'

function mountRow(props: Record<string, unknown>) {
  return mount(FieldRow, {
    props,
    global: { plugins: [createPinia()] },
  })
}

describe('FieldRow', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders label and value by default', () => {
    const w = mountRow({ label: 'Authorization', value: 'Bearer x' })
    expect(w.text()).toContain('Authorization')
    expect(w.text()).toContain('Bearer x')
  })

  it('is visible by default (hidden=false)', () => {
    const w = mountRow({ label: 'k', value: 'v' })
    const row = w.find('.field-row')
    expect(row.exists()).toBe(true)
    expect(row.classes()).not.toContain('hidden')
    expect(row.isVisible()).toBe(true)
  })

  it('hidden=true collapses the row (display:none)', async () => {
    const w = mountRow({ label: 'sec-ch-ua', value: '"Windows"', hidden: true })
    const row = w.find('.field-row')
    expect(row.classes()).toContain('hidden')
    // Verify the collapse CSS rule applies (jsdom doesn't honor scoped CSS
    // visibility checks via isVisible, so check class instead).
    expect(row.element.classList.contains('hidden')).toBe(true)
  })

  it('hidden=true + showHidden=true reveals with .show-hidden class', async () => {
    const w = mountRow({ label: 'sec-ch-ua', value: '"Windows"', hidden: true })
    const hideStore = useHideStore()
    hideStore.showHidden = true
    await w.vm.$nextTick()
    const row = w.find('.field-row')
    expect(row.classes()).not.toContain('hidden')
    expect(row.classes()).toContain('show-hidden')
    expect(row.isVisible()).toBe(true)
  })

  it('hidden=false + showHidden=true stays visible (no class)', async () => {
    const w = mountRow({ label: 'Authorization', value: 'Bearer x' })
    const hideStore = useHideStore()
    hideStore.showHidden = true
    await w.vm.$nextTick()
    const row = w.find('.field-row')
    expect(row.classes()).not.toContain('hidden')
    expect(row.classes()).not.toContain('show-hidden')
  })

  it('shows eye button only when eye=true', () => {
    const noEye = mountRow({ label: 'k', value: 'v' })
    expect(noEye.find('.eye-button').exists()).toBe(false)
    const withEye = mountRow({ label: 'k', value: 'v', eye: true })
    expect(withEye.find('.eye-button').exists()).toBe(true)
  })

  it('eye button toggles between ◉ (hidden) and 👁 (visible)', async () => {
    const w = mountRow({ label: 'k', value: 'v', eye: true, hidden: true })
    expect(w.find('.eye-button').text()).toBe('◉')
    await w.setProps({ hidden: false })
    expect(w.find('.eye-button').text()).toBe('👁')
  })

  it('emits toggle-eye on eye click', async () => {
    const w = mountRow({ label: 'k', value: 'v', eye: true })
    await w.find('.eye-button').trigger('click')
    expect(w.emitted('toggle-eye')).toBeTruthy()
  })
})