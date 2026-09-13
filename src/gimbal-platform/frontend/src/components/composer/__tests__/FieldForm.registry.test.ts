/** 「加入断言管理」的取值纪律(spec v3 §5,响应侧标记):
 *  响应字段是**只读契约树**(body=null),`getValue` 会回落到 example ——
 *  若把这个 example 当 value 存进条目,用户之后补上注入地址的那一刻,它会
 *  突然变成真正注入请求体的值。隐蔽陷阱,故响应域一律空串。
 *
 *  两条互为判别对:响应侧必须空(拿 example 会红);请求侧必须仍是字段当前
 *  字面量(拿空串会红)—— 单测任一条都挡不住「两域同式」的退化。 */
import { expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import FieldForm from '../FieldForm.vue'
import type { IOFieldBinding } from '@/types/plate'

const BINDINGS = [{
  name: 'code', path: '$.code', type: 'string', required: true,
  ui_kind: 'text', example: 'EX-1',
}] as unknown as IOFieldBinding[]

function mountForm(domain: 'request' | 'response', body: unknown) {
  let mark: { field: IOFieldBinding; value: unknown } | null = null
  const w = mount(defineComponent({
    setup() {
      return () => h(FieldForm, {
        bindings: BINDINGS,
        body,
        fieldActions: true,
        domain,
        readonly: domain === 'response',
        varChoices: [],
        injectChoices: [],
        onRegistryMark: (p: { field: IOFieldBinding; value: unknown }) => { mark = p },
      })
    },
  }))
  return { w, mark: () => mark }
}

async function clickRegistry(w: ReturnType<typeof mountForm>['w']) {
  await w.find('.fa-menu-btn').trigger('click')
  await w.findAll('button').find((b) => b.text().includes('加入断言管理'))!.trigger('click')
}

it('FRM-REG-1: 响应侧标记 → value 恒为空串(不得回落 example)', async () => {
  const { w, mark } = mountForm('response', null)
  // 前置:只读响应行**确实**把 example 显示出来了 —— 证明 getValue 在这套
  // 上下文里回落到 'EX-1'。没有这一条,下面的空串断言可能因为 getValue
  // 恰好返回 undefined 而假绿(测不到「回落」这个真陷阱)。
  expect((w.find('input.ctl').element as HTMLInputElement).value).toBe('EX-1')
  await clickRegistry(w)
  expect(mark()).not.toBeNull()
  expect(mark()!.field.name).toBe('code')
  expect(mark()!.value).toBe('')          // 不是 'EX-1'
  w.unmount()
})

it('FRM-REG-2: 请求侧标记 → value 仍是字段当前字面量(不回归)', async () => {
  const { w, mark } = mountForm('request', { code: 'LIT-9' })
  await clickRegistry(w)
  expect(mark()).not.toBeNull()
  expect(mark()!.value).toBe('LIT-9')
  w.unmount()
})
