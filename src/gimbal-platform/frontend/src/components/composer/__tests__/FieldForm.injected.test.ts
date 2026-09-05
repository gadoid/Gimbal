/**
 * FieldForm — 动态注入只读态(2026-09-03 需求):
 * injected 命中字段(assign target=$.request_body.<path>)→ 值控件换
 * 只读提示条,原值降级为 continue 兜底行(仍存 body,不丢);
 * 未命中/不传 → 常规控件。菜单禁用态由 Canvas 挂载级测试覆盖(I3)。
 * key = 字段 path(实例地址唯一;name 在数组行间共享会整列误标 —
 * 目录化树渲染后改 path 键控)。
 */
import { describe, it, expect } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FieldForm from '@/components/composer/FieldForm.vue'
import type { IOFieldBinding } from '@/types/plate'

const flush = () => new Promise((r) => setTimeout(r, 0))

function mkBinding(over: Partial<IOFieldBinding> = {}): IOFieldBinding {
  return {
    name: 'orderId', path: '$.orderId', ui_kind: 'text',
    source_kind: 'independent', required: true,
    description: null, example: null, default: null, enum: null,
    ...over,
  } as IOFieldBinding
}

const INJ = { '$.orderId': [{ source: '$.oid', target: '$.request_body.orderId' }] }

describe('FieldForm — 动态注入只读态', () => {
  it('命中 → 提示条代替值控件;悬停列 source → target;兜底行透出原值', () => {
    const w = mount(defineComponent({
      setup: () => () => h(FieldForm, {
        bindings: [mkBinding()],
        body: { orderId: 'ord-1' },
        injected: INJ,
      }),
    }), { global: { plugins: [ElementPlus] } })
    expect(w.find('.ctl-injected').exists()).toBe(true)
    expect(w.text()).toContain('已使用动态策略注入')
    expect(w.find('.field-control input.ctl').exists()).toBe(false)
    expect(w.find('.ctl-injected').attributes('title')).toBe('$.oid → $.request_body.orderId')
    const fb = w.find('.injected-fallback')
    expect(fb.exists()).toBe(true)
    expect(fb.text()).toContain('ord-1')
    expect(fb.text()).toContain('continue')
  })

  it('命中但 body 无值 → 兜底行显示 (空)', () => {
    const w = mount(defineComponent({
      setup: () => () => h(FieldForm, {
        bindings: [mkBinding()],
        body: {},
        injected: INJ,
      }),
    }), { global: { plugins: [ElementPlus] } })
    expect(w.find('.injected-fallback').text()).toContain('(空)')
  })

  it('多条 assign 命中同字段 → 悬停 title 逐条列出', () => {
    const w = mount(defineComponent({
      setup: () => () => h(FieldForm, {
        bindings: [mkBinding()],
        body: { orderId: 'x' },
        injected: { '$.orderId': [
          { source: '$.a', target: '$.request_body.orderId' },
          { source: '$.b', target: '$.request_body.orderId' },
        ] },
      }),
    }), { global: { plugins: [ElementPlus] } })
    expect(w.find('.ctl-injected').attributes('title'))
      .toBe('$.a → $.request_body.orderId\n$.b → $.request_body.orderId')
  })

  it('未命中字段 path / 不传 injected → 常规 input 控件,无提示条', () => {
    const mk = (injected?: Record<string, Array<{ source: string; target: string }>>) =>
      mount(defineComponent({
        setup: () => () => h(FieldForm, {
          bindings: [mkBinding()],
          body: { orderId: 'ord-1' },
          ...(injected ? { injected } : {}),
        }),
      }), { global: { plugins: [ElementPlus] } })
    const a = mk({ '$.other': [{ source: '$.x', target: '$.request_body.other' }] })
    expect(a.find('.ctl-injected').exists()).toBe(false)
    expect((a.find('input.ctl').element as HTMLInputElement).value).toBe('ord-1')
    const b = mk()
    expect(b.find('.ctl-injected').exists()).toBe(false)
  })

  it('注入态与策略角标共存 — 只读化不影响角标跳转入口', async () => {
    const jumped: number[] = []
    const w = mount(defineComponent({
      setup: () => () => h(FieldForm, {
        bindings: [mkBinding()],
        body: { orderId: 'ord-1' },
        injected: INJ,
        strategyTags: { '$.orderId': [{ label: 'assign', idx: 0 }] },
        onStrategyJump: (idx: number) => jumped.push(idx),
      }),
    }), { global: { plugins: [ElementPlus] } })
    const tag = w.find('.field-label .strategy-tag')
    expect(tag.exists()).toBe(true)
    expect(tag.text()).toBe('assign')
    await tag.trigger('click')
    await flush()
    expect(jumped).toEqual([0])
  })
})
