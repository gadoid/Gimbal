/**
 * StrategyForm — order 字段可配置(2026-09-04):
 * 卡身 number 输入编辑执行顺序(StrategyBase 公共字段,同 phase 内升序),
 * 卡头 #N 角标显式设置时可见(折叠态也可见);清空输入 → 删 key 回缺省,
 * 不写 0 进 payload。引擎侧 dispatch_phase 按 order 稳定排序,
 * 全缺省时执行序=数组序,平台新增策略骨架不含 order → 零角标零噪音。
 */
import { describe, it, expect } from 'vitest'
import { defineComponent, h, reactive } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import StrategyForm from '@/components/composer/StrategyForm.vue'
import type { StrategyKindDetailView, StrategyView } from '@/types/plate'

/** 最小 detail:fields 留业务字段示意,base_fields 只放 order/onFailure 两个描述符 */
const detail: StrategyKindDetailView = {
  kind: 'assign', label: '准备入参赋值', phase: 'before_request',
  fields: [
    { name: 'target', path: '$.target', required: true, default: null, description: '', enum: null, ui_kind: 'text' },
    { name: 'source', path: '$.source', required: false, default: null, description: '', enum: null, ui_kind: 'json' },
  ],
  base_fields: [
    { name: 'order', path: '$.order', required: false, default: 0, description: '执行顺序', enum: null, ui_kind: 'number' },
    {
      name: 'onFailure', path: '$.onFailure', required: false, default: 'abort', description: '',
      enum: ['abort', 'continue', 'warn', 'retry'], ui_kind: 'select',
    },
  ],
}

function mountWith(strategy: StrategyView) {
  const s = reactive(strategy) as StrategyView
  const w = mount(defineComponent({
    setup: () => () => h(StrategyForm, { strategy: s, detail, startExpanded: true }),
  }), { global: { plugins: [ElementPlus] } })
  return { w, s }
}

describe('StrategyForm — order 可配置', () => {
  it('未设置 order → 无卡头角标,输入框空(placeholder 示意缺省)', () => {
    const { w } = mountWith({ kind: 'assign', target: '$.data.age', source: 18 })
    expect(w.find('.sf-order').exists()).toBe(false)
    const input = w.find('.sf-order-input')
    expect(input.exists()).toBe(true)
    expect((input.element as HTMLInputElement).value).toBe('')
  })

  it('显式 order(导入场景) → 卡头 #N 角标 + 输入框回显,折叠态角标仍在', async () => {
    const { w } = mountWith({ kind: 'assign', target: '$.data', source: { age: 1 }, order: 5 })
    expect(w.find('.sf-order').text()).toBe('#5')
    expect((w.find('.sf-order-input').element as HTMLInputElement).value).toBe('5')
    // 折叠后角标仍可见(执行序一屏可读)
    await w.find('.sf-head').trigger('click')
    expect(w.find('.sf-order').text()).toBe('#5')
    expect(w.find('.sf-order-input').isVisible()).toBe(false)
  })

  it('编辑输入 → order 写入策略对象;清空 → 删 key 回缺省(不写 0)', async () => {
    const { w, s } = mountWith({ kind: 'assign', target: '$.data.age', source: 18 })
    const input = w.find('.sf-order-input')
    await input.setValue('3')
    await input.trigger('change')
    expect((s as any).order).toBe(3)
    expect(w.find('.sf-order').text()).toBe('#3')

    await input.setValue('')
    await input.trigger('change')
    expect((s as any).order).toBeUndefined()
    expect(w.find('.sf-order').exists()).toBe(false)
  })

  it('非整数输入 → 回滚显示,不写入', async () => {
    const { w, s } = mountWith({ kind: 'assign', target: '$.data.age', source: 18, order: 2 })
    const input = w.find('.sf-order-input')
    await input.setValue('1.5')
    await input.trigger('change')
    expect((s as any).order).toBe(2)
    expect((input.element as HTMLInputElement).value).toBe('2')
  })

  it('detail.base_fields 无 order 描述符 → 编辑行整体不渲染(降级)', () => {
    const noOrder: StrategyKindDetailView = { ...detail, base_fields: [] }
    const w = mount(defineComponent({
      setup: () => () => h(StrategyForm, {
        strategy: { kind: 'assign', target: '$.a', source: 1 } as StrategyView,
        detail: noOrder, startExpanded: true,
      }),
    }), { global: { plugins: [ElementPlus] } })
    expect(w.find('.sf-order-input').exists()).toBe(false)
    expect(w.find('.sf-order').exists()).toBe(false)
  })
})
