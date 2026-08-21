/** "设为变量"提升交互(D8):整串替换 + 同名后缀 + 原值上抛。 */
import { expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import FieldForm from '../FieldForm.vue'
import type { IOFieldBinding } from '@/types/plate'

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
