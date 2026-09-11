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

// ─── 扰动位徽标(spec §5.1)────────────────────────────────────────
// 提升后的输入字段行挂"扰动位"徽标 —— 叶子行值整串 ${var.x} 模板 +
// 容器模板态(node-tpl-badge)文案从"引用变量"升级为"扰动位"
// (数据集行可逐行换值的身份呈现,零新通路)。

it('PRT-1: 叶子行值整串 ${var.x} → .perturb-badge "扰动位"', async () => {
  const PERTURB_BINDINGS = [
    { name: 'amount', path: '$.amount', type: 'string', required: false, ui_kind: 'text' },
    { name: 'plain', path: '$.plain', type: 'string', required: false, ui_kind: 'text' },
  ] as unknown as IOFieldBinding[]
  const wrapper = mount(defineComponent({
    setup() {
      return () => h(FieldForm, {
        bindings: PERTURB_BINDINGS,
        body: { amount: '${var.amount}', plain: 'x' },
        'onUpdate:body': () => {},
      })
    },
  }))
  const rows = wrapper.findAll('.field')
  const amountRow = rows.find((r) => r.find('.label-text').text() === 'amount')
  const plainRow = rows.find((r) => r.find('.label-text').text() === 'plain')
  expect(amountRow).toBeTruthy()
  expect(plainRow).toBeTruthy()
  // 模板行:label 区挂 .perturb-badge,文案"扰动位"
  expect(amountRow!.find('.field-label .perturb-badge').exists()).toBe(true)
  expect(amountRow!.find('.perturb-badge').text()).toContain('扰动位')
  // 字面量行:无徽标
  expect(plainRow!.find('.perturb-badge').exists()).toBe(false)
  wrapper.unmount()
})

it('PRT-2: 容器模板态徽标文案升级"扰动位"', async () => {
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
  expect(badge.text()).toContain('扰动位')
  expect(badge.text()).not.toContain('引用变量')
  wrapper.unmount()
})
