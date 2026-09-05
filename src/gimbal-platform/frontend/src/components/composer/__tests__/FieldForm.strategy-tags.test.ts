/**
 * FieldForm — 策略角标(2026-09-02 需求1):
 * strategyTags 按字段 path 注入(实例地址唯一;name 在数组行间共享
 * 会整列误挂 — 目录化树渲染后改 path 键控)→ label 行尾(src-tag 后)
 * 渲染角标按钮;点击上抛 strategyJump(idx)= step.strategy 数组下标,
 * Canvas 定位策略卡。StrategyForm 复用本组件处不传该 prop → 零角标。
 */
import { describe, it, expect } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FieldForm from '@/components/composer/FieldForm.vue'
import type { IOFieldBinding } from '@/types/plate'

const flush = () => new Promise((r) => setTimeout(r, 0))

function mkBinding(over: Partial<IOFieldBinding> = {}): IOFieldBinding {
  return {
    name: 'total', path: '$.data.total', ui_kind: 'number',
    source_kind: 'independent', required: true,
    description: null, example: null, default: null, enum: null,
    ...over,
  } as IOFieldBinding
}

describe('FieldForm — 策略角标(需求1)', () => {
  it('strategyTags 命中字段 → label 行尾渲染角标,点击上抛 strategyJump(idx)', async () => {
    const jumped: number[] = []
    const body = ref<Record<string, unknown>>({})
    const Parent = defineComponent({
      setup() {
        return () => h(FieldForm, {
          bindings: [mkBinding()],
          body: body.value,
          strategyTags: { '$.data.total': [{ label: 'extract_1', idx: 2 }] },
          'onUpdate:body': (v: Record<string, unknown>) => { body.value = v },
          onStrategyJump: (idx: number) => jumped.push(idx),
        })
      },
    })
    const w = mount(Parent, { global: { plugins: [ElementPlus] } })
    const tag = w.find('.field-label .strategy-tag')
    expect(tag.exists()).toBe(true)
    expect(tag.text()).toBe('extract_1')
    await tag.trigger('click')
    await flush()
    expect(jumped).toEqual([2])
  })

  it('未命中字段 path / 不传 strategyTags → 无角标', () => {
    const a = mount(defineComponent({
      setup: () => () => h(FieldForm, {
        bindings: [mkBinding()], body: {},
        strategyTags: { '$.other': [{ label: 'extract', idx: 0 }] },
      }),
    }), { global: { plugins: [ElementPlus] } })
    expect(a.find('.strategy-tag').exists()).toBe(false)
    const b = mount(defineComponent({
      setup: () => () => h(FieldForm, { bindings: [mkBinding()], body: {} }),
    }), { global: { plugins: [ElementPlus] } })
    expect(b.find('.strategy-tag').exists()).toBe(false)
  })
})
