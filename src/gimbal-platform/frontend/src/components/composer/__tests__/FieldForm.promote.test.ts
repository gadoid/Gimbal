/** "设为变量"提升交互(D8):整串替换 + 同名后缀 + 原值上抛。 */
import { expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import FieldForm from '../FieldForm.vue'
import { buildTree } from '@/utils/declarations'
import type { DeclarationEntryView, IOFieldBinding } from '@/types/plate'

// IOFieldBinding 只用 name/path;其余字段按需补,类型不符处整体 as 收敛
const BINDINGS = [{
  name: 'customer_id', path: '$.customer_id', type: 'string', required: true,
  ui_kind: 'text',
}] as unknown as IOFieldBinding[]

function mountForm(varChoices: string[], body: Record<string, unknown>) {
  let gotBody: unknown = null
  let promoted: { name: string; value: unknown } | null = null
  const wrapper = mount(defineComponent({
    setup() {
      return () => h(FieldForm, {
        bindings: BINDINGS,
        body,
        fieldActions: true,
        varChoices: varChoices.map((n) => ({
          name: n, origin: 'config' as const, stepIdx: null, expression: null,
        })),
        'onUpdate:body': (v: unknown) => { gotBody = v },
        onVarPromote: (_f: IOFieldBinding, name: string, value: unknown) => {
          promoted = { name, value }
        },
      })
    },
  }))
  return {
    wrapper,
    getBody: () => gotBody,
    getPromoted: () => promoted,
  }
}

async function promote(wrapper: ReturnType<typeof mountForm>['wrapper']) {
  await wrapper.find('.fa-menu-btn').trigger('click')
  await wrapper.find('.fa-promote').trigger('click')
}

it('直填值整串替换为 ${var.customer_id},原值随 varPromote 上抛', async () => {
  const t = mountForm([], { customer_id: '261' })
  await promote(t.wrapper)
  expect(t.getBody()).toEqual({ customer_id: '${var.customer_id}' })
  expect(t.getPromoted()).toEqual({ name: 'customer_id', value: '261' })
})

it('同名冲突自动加后缀 _2(检查共享变量 + extract 两出身)', async () => {
  const t = mountForm(['customer_id'], { customer_id: '261' })
  await promote(t.wrapper)
  expect(t.getPromoted()).toEqual({ name: 'customer_id_2', value: '261' })
  expect(t.getBody()).toEqual({ customer_id: '${var.customer_id_2}' })
})

// ─── 编排侧不再标注「扰动位」(2026-09-13 裁定)─────────────────────
// 值整串 ${var.x} 只说明「这是模板」,**不说明「这是扰动点」**:模板一部分
// 是正常业务过程的模板化,另一部分才是扰动 —— 编排侧无从分辨(判据是纯
// 正则,既不查数据集也不查断言管理)。权威的扰动点列表 = 断言管理条目的
// path(其语义即注入地址)。故编排侧不再做这套标记。

it('PRT-1: 叶子行的整串模板值**不再**挂扰动位徽标(值本身照常显示)', async () => {
  const BINDINGS = [
    { name: 'amount', path: '$.amount', type: 'string', required: false, ui_kind: 'text' },
    { name: 'plain', path: '$.plain', type: 'string', required: false, ui_kind: 'text' },
  ] as unknown as IOFieldBinding[]
  const wrapper = mount(defineComponent({
    setup() {
      return () => h(FieldForm, {
        bindings: BINDINGS,
        body: { amount: '${var.amount}', plain: 'x' },
        'onUpdate:body': () => {},
      })
    },
  }))
  const rows = wrapper.findAll('.field')
  const amountRow = rows.find((r) => r.find('.label-text').text() === 'amount')
  expect(amountRow).toBeTruthy()
  // 非空洞:行照常渲染、模板串仍是控件的值 —— 删的是**标记**,不是能力
  expect((amountRow!.find('input.ctl').element as HTMLInputElement).value).toBe('${var.amount}')
  expect(amountRow!.find('.perturb-badge').exists()).toBe(false)
  wrapper.unmount()
})

it('PRT-2: 容器模板态徽标文案**回退**为「引用变量」(不 over-claim)', async () => {
  const decls = [{
    name: 'supplier', path: '$.supplier', type: 'object',
    ui_kind: 'json', source_kind: 'independent',
    required: false, description: '', assertable: false,
    children: [{
      name: 'id', path: '$.supplier.id',
      ui_kind: 'text', source_kind: 'independent',
      required: false, description: '', assertable: false,
    }],
  } as unknown as DeclarationEntryView]
  const body = { supplier: '${var.supplier}' }
  const wrapper = mount(defineComponent({
    setup() {
      return () => h(FieldForm, {
        nodes: buildTree(decls, undefined, body),
        body,
        'onUpdate:body': () => {},
      })
    },
  }))
  const badge = wrapper.find('.node-tpl-badge')
  expect(badge.exists()).toBe(true)
  // 该标签只说「这是模板串,不是字面量」—— 这件事仍然成立且有用
  expect(badge.text()).toContain('引用变量')
  expect(badge.text()).not.toContain('扰动位')
  wrapper.unmount()
})
