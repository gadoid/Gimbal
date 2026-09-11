// FieldActionMenu.registry.test.ts — 加入断言管理菜单项(spec v2 §4 / Task 4)
// 独立小测:组件零 IO、无 router/ElementPlus 依赖,裸 mount 即可。
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import FieldActionMenu from '../FieldActionMenu.vue'

const FIELD = { name: 'amount', path: '$.amount', required: true } as any

function mountMenu(over: Record<string, unknown> = {}) {
  return mount(FieldActionMenu, {
    props: { field: FIELD, value: '${var.amount}', varChoices: [], injectChoices: [], open: true, ...over },
  })
}

describe('FieldActionMenu — 加入断言管理(spec v2 §4)', () => {
  it('FAM-REG-1: 请求侧渲染「加入断言管理」项,response 侧不渲染', () => {
    const w = mountMenu()
    expect(w.text()).toContain('加入断言管理')
    const w2 = mountMenu({ domain: 'response' })
    expect(w2.text()).not.toContain('加入断言管理')
    w.unmount(); w2.unmount()
  })
  it('FAM-REG-2: 点击 emit fieldRegistry(field) 并关闭', async () => {
    const w = mountMenu()
    await w.findAll('button').find((b) => b.text().includes('加入断言管理'))!.trigger('click')
    expect(w.emitted('fieldRegistry')![0]).toEqual([FIELD])
    expect(w.emitted('close')).toBeTruthy()
    w.unmount()
  })
})
