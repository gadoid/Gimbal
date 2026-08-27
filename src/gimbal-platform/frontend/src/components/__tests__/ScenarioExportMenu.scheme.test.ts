/**
 * ScenarioExportMenu — 按方案导出(spec §8,Task 14;D2 环境退役适配)。
 *
 * 方案子项把方案的 overlay({serviceBindings};envId 已随 D2 退役,
 * dataSetIds 有意不带 — spec §7.3 导出是场景级)交给 store.exportJson
 * 物化导出。
 *
 * 建件遵循 UsersCard.test.ts 惯例:ElementPlus 插件 + attachTo
 * document.body,弹层走真实 teleport,以 document.querySelectorAll 检索、
 * 原生 .click() 触发(CaseComposer.run.test.ts 记录过 popper 组件与
 * teleport stub 叠加在 jsdom 递归更新爆表,故不用 teleport stub)。
 *
 * store mock 走 importOriginal 展开:保留真实 schemeToOverlay 参与
 * 断言(overlay 无 envId 键),而非 mock 自证。
 */
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ScenarioExportMenu from '../ScenarioExportMenu.vue'

/** 组件与测试共享的 mock store 单例(draft 可按测试覆写) */
const mockStore = vi.hoisted(() => ({
  draft: null as null | { orchestration: { runSchemes: unknown[] } },
  exportJson: vi.fn().mockResolvedValue(undefined),
  exportYaml: vi.fn().mockResolvedValue(undefined),
  copyJson: vi.fn(),
}))

vi.mock('@/stores/scenario-draft', async (importOriginal) => {
  const real = await importOriginal<typeof import('@/stores/scenario-draft')>()
  return { ...real, useScenarioDraftStore: () => mockStore }
})

const schemes = [
  { name: '冒烟-qa1', dataSetIds: [],
    serviceBindings: { 'fin-service': { authAlias: 'qa1' } } },
  { name: '回归-qa2', dataSetIds: [],
    serviceBindings: { 'fin-service': { authAlias: 'qa2' } } },
]

function mountMenu() {
  return mount(ScenarioExportMenu, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

/** 点开菜单,返回 teleport 到 body 的下拉项 */
async function openMenu(w: ReturnType<typeof mountMenu>): Promise<HTMLElement[]> {
  await w.find('.se-trigger').trigger('click')
  await flushPromises()
  return [...document.querySelectorAll('.el-dropdown-menu__item')] as HTMLElement[]
}

beforeEach(() => {
  mockStore.exportJson.mockClear()
  mockStore.exportYaml.mockClear()
  mockStore.copyJson.mockClear()
  mockStore.draft = null
})

afterEach(() => {
  // jsdom 不跑 transition,卸载时处于开态的下拉 popper 残留在 body —
  // 手工摘除,避免跨测试串到 document.querySelectorAll 的结果里。
  document.querySelectorAll('.el-dropdown__popper').forEach((el) => el.remove())
})

describe('ScenarioExportMenu — 按方案导出', () => {
  it('方案子项走 exportJson(overlay)', async () => {
    mockStore.draft = { orchestration: { runSchemes: schemes } }
    const w = mountMenu()
    const items = await openMenu(w)
    // 原三动作仍在(svg 图标让 textContent 带空白,用 includes 断言)
    expect(items.some((i) => i.textContent!.includes('导出 JSON'))).toBe(true)
    const item = items.find((i) => i.textContent!.includes('冒烟-qa1'))
    expect(item).toBeTruthy()
    item!.click()
    await flushPromises()
    expect(mockStore.exportJson).toHaveBeenCalledTimes(1)
    expect(mockStore.exportJson).toHaveBeenCalledWith({
      serviceBindings: { 'fin-service': { authAlias: 'qa1' } } })
    w.unmount()
  })

  it('overlay 只带 serviceBindings(envId 已退役;dataSetIds 有意不带)', async () => {
    mockStore.draft = { orchestration: { runSchemes: schemes } }
    const w = mountMenu()
    const items = await openMenu(w)
    const item = items.find((i) => i.textContent!.includes('回归-qa2'))
    expect(item).toBeTruthy()
    item!.click()
    await flushPromises()
    const overlay = mockStore.exportJson.mock.calls[0][0]
    expect('envId' in overlay).toBe(false)
    // dataSetIds 有意不带(spec §7.3 导出是场景级)
    expect('dataSetIds' in overlay).toBe(false)
    expect(overlay.serviceBindings).toEqual({ 'fin-service': { authAlias: 'qa2' } })
    w.unmount()
  })

  it('无方案时菜单只剩原三动作,导出 JSON 零参调用(行为不变)', async () => {
    mockStore.draft = { orchestration: { runSchemes: [] } }
    const w = mountMenu()
    const items = await openMenu(w)
    expect(items).toHaveLength(3)
    expect(items.some((i) => i.textContent!.includes('按方案导出'))).toBe(false)
    items.find((i) => i.textContent!.includes('导出 JSON'))!.click()
    await flushPromises()
    expect(mockStore.exportJson).toHaveBeenCalledTimes(1)
    expect(mockStore.exportJson.mock.calls[0]).toHaveLength(0) // 无 overlay 参
    w.unmount()
  })
})
