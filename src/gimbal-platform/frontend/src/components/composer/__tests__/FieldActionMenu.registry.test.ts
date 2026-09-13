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
  it('FAM-REG-1: 请求侧渲染「加入断言管理」项', () => {
    const w = mountMenu()
    expect(w.text()).toContain('加入断言管理')
    w.unmount()
  })
  it('FAM-REG-1b: 响应侧**同样**渲染「加入断言管理」—— 但值写入三项仍按域门控', () => {
    // 响应侧标记落 asserts[0].target(响应字段是断言目标,不是注入地址),
    // 故本项不再按域门控;引用/设为变量/动态注入仍是请求侧专有 —— 它们
    // 都写请求体的值,响应侧无从写起。两项与域无关(提取/断言)照旧。
    const w = mountMenu({ domain: 'response' })
    expect(w.text()).toContain('加入断言管理')
    expect(w.text()).not.toContain('设为变量')
    expect(w.text()).not.toContain('引用共享变量')
    expect(w.text()).not.toContain('向该字段动态注入')
    expect(w.text()).toContain('提取该字段')
    expect(w.text()).toContain('断言该字段')
    w.unmount()
  })
  it('FAM-REG-2: 点击 emit fieldRegistry(field) 并关闭', async () => {
    const w = mountMenu()
    await w.findAll('button').find((b) => b.text().includes('加入断言管理'))!.trigger('click')
    expect(w.emitted('fieldRegistry')![0]).toEqual([FIELD])
    expect(w.emitted('close')).toBeTruthy()
    w.unmount()
  })
})
