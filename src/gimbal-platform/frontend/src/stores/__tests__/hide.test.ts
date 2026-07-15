/**
 * Regression tests for the hide store (Spec-1 sign-off).
 *
 * The store powers the "L3 默认隐藏 + L1 字段👁 + 👁 显示隐藏" UX in
 * CaseConfigReadonly's step-cards. FieldRow.vue reads from this store to
 * decide whether to collapse (display:none) or show with a subtle background.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useHideStore, L3_DEFAULTS } from '@/stores/hide'

describe('useHideStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with L3 preset applied', () => {
    const s = useHideStore()
    for (const p of L3_DEFAULTS) {
      expect(s.isHidden(p)).toBe(true)
    }
  })

  it('starts with showHidden off', () => {
    const s = useHideStore()
    expect(s.showHidden).toBe(false)
  })

  it('toggleL1 adds and removes a path', () => {
    const s = useHideStore()
    const path = 'api.headers["x-custom"]'
    expect(s.isHidden(path)).toBe(false)
    s.toggleL1(path)
    expect(s.isHidden(path)).toBe(true)
    s.toggleL1(path)
    expect(s.isHidden(path)).toBe(false)
  })

  it('reset() restores L3 + showHidden=false', () => {
    const s = useHideStore()
    s.toggleL1('api.headers["x-custom"]')
    s.showHidden = true
    s.reset()
    expect(s.showHidden).toBe(false)
    expect(s.isHidden('api.headers["x-custom"]')).toBe(false)
    // L3 path still hidden
    expect(s.isHidden(L3_DEFAULTS[0])).toBe(true)
  })

  it('hiddenCount reflects distinct paths', () => {
    const s = useHideStore()
    const base = s.hiddenCount
    s.toggleL1('a.b.c')
    expect(s.hiddenCount).toBe(base + 1)
    s.toggleL1('a.b.c')  // toggles off
    expect(s.hiddenCount).toBe(base)
  })
})