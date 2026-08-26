/**
 * ConstantPoolPanel — F4-F8:
 * F4 渲染(空态/条目/徽标/双载荷行);
 * F5 复制载荷(字面量值文本、生成器 key、生成器 spec JSON);
 * F6 生成器 key 插入成功 → 追加引用 + emit seedVar;
 * F7 value 插入纯文本(生成器 spec JSON / 字面量值)不 emit seedVar;
 * F8 无插入目标 → ElMessage.info 且不 emit。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ConstantPoolPanel from '@/components/composer/ConstantPoolPanel.vue'
import { INSERT_TARGET_KEY, useInsertTarget } from '@/composables/useInsertTarget'
import { copyText } from '@/utils/clipboard'
import { ElMessage } from 'element-plus'
import type { ConstantEntry } from '@/types/constants'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/utils/clipboard', () => ({ copyText: vi.fn().mockResolvedValue(true) }))

const GEN: ConstantEntry = {
  id: 1,
  name: 'bl_no',
  description: '业务单号',
  entry_kind: 'generator',
  value: null,
  spec: { kind: 'random_decorated', charset: 'alnum', length: 6, head: 'GIMBAL728', separator: '-' },
  created_at: '',
  updated_at: '',
}
const LIT: ConstantEntry = {
  id: 2,
  name: 'bank_id',
  description: '',
  entry_kind: 'literal',
  value: '319666690256273408',
  spec: null,
  created_at: '',
  updated_at: '',
}
const GEN_SPEC_JSON = JSON.stringify(GEN.spec)

function mountPanel(entries: ConstantEntry[]) {
  const inserter = useInsertTarget()
  const root = document.createElement('div')
  document.body.appendChild(root)
  inserter.start(root)
  const w = mount(ConstantPoolPanel, {
    props: { entries },
    global: { provide: { [INSERT_TARGET_KEY as symbol]: inserter } },
    attachTo: root,
  })
  return { w, inserter, root }
}

function focus(el: Element): void {
  el.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ConstantPoolPanel', () => {
  it('F4: 渲染条目/徽标/双载荷行;空态提示', () => {
    const { w } = mountPanel([GEN, LIT])
    expect(w.find('.cp-panel').exists()).toBe(true)
    const gen = w.find('[data-entry="bl_no"]')
    expect(gen.exists()).toBe(true)
    expect(gen.find('.cp-badge.generator').text()).toBe('生成器')
    expect(gen.find('.act-copy-key').exists()).toBe(true) // key 载荷行
    expect(gen.find('.act-copy-value').exists()).toBe(true) // value 载荷行
    const lit = w.find('[data-entry="bank_id"]')
    expect(lit.find('.cp-badge.literal').text()).toBe('常量')
    expect(lit.find('.act-copy-key').exists()).toBe(false) // 字面量无 key 行
    w.unmount()

    const empty = mountPanel([])
    expect(empty.w.text()).toContain('常量池为空')
    empty.w.unmount()
  })

  it('F5: 复制载荷 — 字面量值文本 / 生成器 key / 生成器 spec JSON', async () => {
    const { w } = mountPanel([GEN, LIT])
    await w.find('[data-entry="bank_id"] .act-copy-value').trigger('click')
    expect(copyText).toHaveBeenCalledWith('319666690256273408')

    await w.find('[data-entry="bl_no"] .act-copy-key').trigger('click')
    expect(copyText).toHaveBeenCalledWith('${var.bl_no}')

    await w.find('[data-entry="bl_no"] .act-copy-value').trigger('click')
    expect(copyText).toHaveBeenCalledWith(GEN_SPEC_JSON)
    w.unmount()
  })

  it('F6: 生成器 key 插入 → 追加引用 + emit seedVar(含 spec 快照)', async () => {
    const { w, root } = mountPanel([GEN])
    const input = document.createElement('input')
    input.type = 'text'
    input.value = 'prefix-'
    root.appendChild(input)
    focus(input)

    await w.find('[data-entry="bl_no"] .act-insert-key').trigger('click')
    expect(input.value).toBe('prefix-${var.bl_no}')
    expect(w.emitted('seedVar')).toBeTruthy()
    const [[name, spec]] = w.emitted('seedVar')!
    expect(name).toBe('bl_no')
    expect(spec).toEqual(GEN.spec)
    w.unmount()
  })

  it('F7: value 插入纯文本(生成器 spec JSON / 字面量值)不 emit seedVar', async () => {
    const { w, root } = mountPanel([GEN, LIT])
    const input = document.createElement('input')
    input.type = 'text'
    root.appendChild(input)
    focus(input)

    await w.find('[data-entry="bl_no"] .act-insert-value').trigger('click')
    expect(input.value).toBe(GEN_SPEC_JSON)
    expect(w.emitted('seedVar')).toBeFalsy()

    await w.find('[data-entry="bank_id"] .act-insert-value').trigger('click')
    expect(input.value).toBe(`${GEN_SPEC_JSON}319666690256273408`)
    expect(w.emitted('seedVar')).toBeFalsy()
    w.unmount()
  })

  it('F8: 无插入目标 → ElMessage.info 且不 emit、不复制', async () => {
    const { w } = mountPanel([GEN])
    await w.find('[data-entry="bl_no"] .act-insert-key').trigger('click')
    expect(ElMessage.info).toHaveBeenCalledWith(
      expect.stringContaining('请先点击'),
    )
    expect(w.emitted('seedVar')).toBeFalsy()
    expect(copyText).not.toHaveBeenCalled()
    w.unmount()
  })
})
