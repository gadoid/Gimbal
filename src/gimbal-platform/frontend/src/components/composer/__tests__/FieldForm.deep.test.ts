/**
 * FieldForm — 深层字段读写闭环(Task 6,D7/D8):
 *
 * D8 清空分流:平铺字段清空维持 ''(现状);dot 嵌套与 bracket 深层清空走
 * pruneByPath 容器级剪枝 — 叶子删后祖先链全空 → 连锁删到根键,
 * 防幻影容器({cfg:{}})挡 carry 整包注入。
 * D7 carry 容器接管警告行:深层字段根键命中 Canvas 传入的 carryRoots
 * → field-desc 位置渲染「手填接管,清空恢复注入」警告。
 * 裁定14 顺手锁:view_only 上级 title 显示原通道,不再误标 binding。
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
    name: 'order_id',
    path: '$.order_id',
    ui_kind: 'text',
    source_kind: 'independent',
    required: true,
    description: null,
    example: null,
    default: null,
    enum: null,
    ...over,
  } as IOFieldBinding
}

/** 生产用法镜像:父持 body ref,子 update:body 双向 */
function mountWithParent(opts: {
  bindings: IOFieldBinding[]
  body?: Record<string, unknown> | null
  carryRoots?: string[]
  injected?: Record<string, Array<{ source: string; target: string }>>
}) {
  const body = ref<Record<string, unknown>>(opts.body ?? { order_id: 'ord-1' })
  const Parent = defineComponent({
    setup() {
      return () => h(FieldForm, {
        bindings: opts.bindings,
        body: opts.body === null ? null : body.value,
        carryRoots: opts.carryRoots,
        injected: opts.injected,
        'onUpdate:body': (v: Record<string, unknown>) => { body.value = v },
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [ElementPlus] } })
  return { w, body }
}

describe('FieldForm — 深层字段清空剪枝(D8)', () => {
  it('D1: dot 嵌套字段清空 → 容器整体消失(body 不残留幻影空容器)', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding({ name: 'timeout', path: '$.cfg.timeout' })],
      body: { cfg: { timeout: 30 } },
    })
    await w.find('input.ctl').setValue('')
    await flush()
    expect(body.value).toEqual({})
  })

  it('D2: bracket 深层字段清空 → 数组容器连锁剪枝消失', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding({ name: 'sku', path: '$.items[0].sku' })],
      body: { items: [{ sku: 'sku-1' }] },
    })
    await w.find('input.ctl').setValue('')
    await flush()
    expect(body.value).toEqual({})
  })

  it('D3: 平铺字段清空 → 维持 \'\'(现状不变,不误伤)', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1' },
    })
    await w.find('input.ctl').setValue('')
    await flush()
    expect(body.value).toEqual({ order_id: '' })
  })

  it('D3b: 深层字段非清空输入 → 正常 setByPath 写入(剪枝只在清空时)', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding({ name: 'timeout', path: '$.cfg.timeout' })],
      body: { cfg: { timeout: 30 } },
    })
    await w.find('input.ctl').setValue('60')
    await flush()
    expect(body.value).toEqual({ cfg: { timeout: '60' } })
  })
})

describe('FieldForm — carry 容器接管警告行(D7)', () => {
  it('C1: 深层字段根键命中 carryRoots → 警告行透出容器与接管语义', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'timeout', path: '$.cfg.timeout' })],
      body: { cfg: { timeout: 30 } },
      carryRoots: ['cfg'],
    })
    const note = w.find('.deep-carry-note')
    expect(note.exists()).toBe(true)
    expect(note.text()).toContain('上级容器 $.cfg 为 carry 整包传递')
    expect(note.text()).toContain('手填将接管该容器,清空可恢复注入')
  })

  it('C2: 深层字段但根键不在 carryRoots(binding 容器)→ 无警告行', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'ref', path: '$.meta.ref' })],
      body: { meta: { ref: 'r' } },
      carryRoots: ['cfg'],
    })
    expect(w.find('.deep-carry-note').exists()).toBe(false)
  })

  it('C3: 根键命中但平铺字段(非深层)→ 无警告行', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1' },
      carryRoots: ['order_id'],
    })
    expect(w.find('.deep-carry-note').exists()).toBe(false)
  })

  it('C4: 不传 carryRoots(StrategyForm/响应页复用)→ 零警告行', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'timeout', path: '$.cfg.timeout' })],
      body: { cfg: { timeout: 30 } },
    })
    expect(w.find('.deep-carry-note').exists()).toBe(false)
  })
})

describe('FieldForm — 深层字段注入共存与上级通道标注', () => {
  it('X1: 深层字段注入 assign → 提示条与 path 角标(及 carry 警告行)共存', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'timeout', path: '$.cfg.timeout' })],
      body: { cfg: { timeout: 30 } },
      injected: { timeout: [{ source: '$.oid', target: '$.request_body.cfg.timeout' }] },
      carryRoots: ['cfg'],
    })
    expect(w.find('.ctl-injected').exists()).toBe(true)
    expect(w.find('.path-badge').exists()).toBe(true)
    expect(w.find('.deep-carry-note').exists()).toBe(true)
  })

  it('X2(裁定14): view_only 上级 → title 显示原通道,不再误标 binding', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({
        name: 'code',
        path: '$.data.code',
        parentPath: '$.data',
        parentChannel: 'view_only',
      })],
      body: {},
    })
    expect(w.find('.path-badge').attributes('title'))
      .toBe('$.data.code · 上级 $.data(view_only)')
  })
})
