/** FieldForm — 提升面(2026-09-14 spec §4.3/§4.4):
 *  extras 残留行「提升」按钮(emit promoted,模板路径);
 *  promotedPaths 命中的树节点行尾下拉无 carry(含嵌套容器内)。
 *  mount 包装镜像 FieldForm.deep.test.ts(父持 body ref)。 */
import { describe, it, expect } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FieldForm from '@/components/composer/FieldForm.vue'
import { buildTree } from '@/utils/declarations'
import type { DeclarationEntryView, FieldState } from '@/types/plate'

function mkDecl(over: Partial<DeclarationEntryView> = {}): DeclarationEntryView {
  return {
    name: 'x', path: '$.x', required: false, description: '',
    ui_kind: 'text', source_kind: 'independent', assertable: false,
    ...over,
  }
}

function mountForm(opts: {
  decls?: DeclarationEntryView[]
  nodes?: ReturnType<typeof buildTree>
  deepExtras?: Array<{ path: string; top: boolean }>
  promotedPaths?: Set<string>
  body?: unknown
}) {
  const body = ref<unknown>(opts.body ?? {})
  const promoted: string[] = []
  const Parent = defineComponent({
    setup() {
      return () => h(FieldForm, {
        nodes: opts.nodes ?? buildTree(opts.decls ?? [], undefined, body.value),
        deepExtras: opts.deepExtras ?? [],
        body: body.value,
        stateControl: true,
        promotedPaths: opts.promotedPaths,
        'onUpdate:body': (v: unknown) => { body.value = v },
        'onPromote': (p: string) => { promoted.push(p) },
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [ElementPlus] } })
  return { w, promoted }
}

describe('FieldForm — extras 提升(§4.3)', () => {
  it('FF-P1: 残留行「提升」按钮 → emit promoted(实例路径剥 [i] 模板化)', async () => {
    const { w, promoted } = mountForm({
      deepExtras: [{ path: '$.arr[0].x', top: false }, { path: '$.extra', top: false }],
      body: { arr: [{ x: 1 }], extra: 'E' },
    })
    await w.find('.extras-toggle').trigger('click')
    const btns = w.findAll('.extra-promote')
    expect(btns).toHaveLength(2)
    await btns[0].trigger('click')   // $.arr[0].x → 模板化 $.arr.x
    await btns[1].trigger('click')
    expect(promoted).toEqual(['$.arr.x', '$.extra'])
  })

  it('FF-P2: 不传 stateControl 的复用面无提升按钮(StrategyForm 零变化)', async () => {
    const w = mount(FieldForm, {
      props: { nodes: [], body: {}, deepExtras: [{ path: '$.extra', top: false }] },
      global: { plugins: [ElementPlus] },
    })
    // 展开折叠区后断言(行渲染才见按钮位):复用面不传 stateControl → 无提升钮
    await w.find('.extras-toggle').trigger('click')
    expect(w.find('.extra-row').exists()).toBe(true)
    expect(w.find('.extra-promote').exists()).toBe(false)
  })
})

describe('FieldForm — promotedPaths carry 门禁(§4.4)', () => {
  it('FF-P3: 命中节点的行尾下拉无 carry;未命中节点三态齐', async () => {
    // 目录树 $.cfg{t} + 提升树 $.extra(promotedDecls 形状:顶层叶)
    const cfg = mkDecl({ name: 'cfg', path: '$.cfg', type: 'object', children: [
      mkDecl({ name: 't', path: '$.cfg.t' }),
    ] })
    const extra = mkDecl({ name: 'extra', path: '$.extra', type: 'string' })
    const { w } = mountForm({
      nodes: buildTree([cfg, extra], undefined, { cfg: { t: 1 }, extra: 2 }),
      promotedPaths: new Set(['$.extra']),
      body: { cfg: { t: 1 }, extra: 2 },
    })
    // 实际 DOM:下拉 3 枚 = cfg 头 + cfg.t 叶(嵌套)+ extra 叶(顶层)
    expect(w.findAll('.fss-sel')).toHaveLength(3)
    // cfg 头(未命中)三态齐;extra 叶(命中 $.extra)无 carry
    const cfgHead = w.find('.obj-node > .node-head .fss-sel')
    expect(cfgHead.findAll('option').map((o) => o.attributes('value')))
      .toEqual(['form', 'collapse', 'carry'])
    const extraField = w.findAll('.field').find((f) => f.text().includes('$.extra'))
    expect(extraField).toBeTruthy()
    expect(extraField!.find('.fss-sel').findAll('option').map((o) => o.attributes('value')))
      .toEqual(['form', 'collapse'])
  })

  it('FF-P4: 嵌套容器内的命中叶同样无 carry(promotedPaths 经递归转发)', () => {
    // $.box.extra = 提升进容器内的叶(promotedPaths 含实例模板路径)
    const box = mkDecl({ name: 'box', path: '$.box', type: 'object', children: [
      mkDecl({ name: 'extra', path: '$.box.extra' }),
      mkDecl({ name: 't', path: '$.box.t' }),
    ] })
    const { w } = mountForm({
      nodes: buildTree([box], undefined, { box: { extra: 1, t: 2 } }),
      promotedPaths: new Set(['$.box.extra']),
      body: { box: { extra: 1, t: 2 } },
    })
    // 嵌套体两叶:extra(命中)两态;t(未命中)三态
    const fields = w.findAll('.obj-body .field')
    expect(fields).toHaveLength(2)
    const optsOf = (i: number) =>
      fields[i].find('.fss-sel').findAll('option').map((o) => o.attributes('value'))
    expect(optsOf(0)).toEqual(['form', 'collapse'])
    expect(optsOf(1)).toEqual(['form', 'collapse', 'carry'])
  })
})
