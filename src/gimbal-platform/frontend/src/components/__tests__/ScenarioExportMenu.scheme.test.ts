/**
 * ScenarioExportMenu — 按方案导出(spec §8;阶段④:方案列表迁新 CRUD)。
 *
 * 方案子项把方案的 overlay({serviceBindings};dataSetIds 有意不带 —
 * spec §7.3 导出是场景级)交给 store.exportJson 物化导出。方案来源 =
 * 开菜单时 listRunSchemes(draft.scenarioId)(V1 sidecar 读侧已下线);
 * 读侧失败/无方案 → 菜单只剩原三动作,默认导出不受影响(静默降级)。
 *
 * 建件遵循 UsersCard.test.ts 惯例:ElementPlus 插件 + attachTo
 * document.body,弹层走真实 teleport,以 document.querySelectorAll 检索、
 * 原生 .click() 触发(CaseComposer.run.test.ts 记录过 popper 组件与
 * teleport stub 叠加在 jsdom 递归更新爆表,故不用 teleport stub)。
 *
 * store mock 走 importOriginal 展开:保留真实 schemeToOverlay 参与
 * 断言(overlay 无多余键),而非 mock 自证。
 */
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ScenarioExportMenu from '../ScenarioExportMenu.vue'

/** 组件与测试共享的 mock store 单例(draft 可按测试覆写;组件只读
 *  draft.scenarioId — 方案列表已不经 draft 携带)。 */
const mockStore = vi.hoisted(() => ({
  draft: null as null | { scenarioId: string | null },
  exportJson: vi.fn().mockResolvedValue(undefined),
  exportYaml: vi.fn().mockResolvedValue(undefined),
  copyJson: vi.fn(),
}))

vi.mock('@/stores/scenario-draft', async (importOriginal) => {
  const real = await importOriginal<typeof import('@/stores/scenario-draft')>()
  return { ...real, useScenarioDraftStore: () => mockStore }
})

const listRunSchemesMock = vi.hoisted(() => vi.fn())
vi.mock('@/api/scenario-composer', async (importOriginal) => {
  const real = await importOriginal<typeof import('@/api/scenario-composer')>()
  return { ...real, listRunSchemes: listRunSchemesMock }
})

/** SchemeV2 形状(方案工作台 CRUD wire) */
const schemes = [
  { schemeId: 'rs-001', name: '冒烟-qa1', isDefault: false,
    dataSetSelection: [], injectionEntryIds: [],
    serviceBindings: { 'fin-service': { authAlias: 'qa1' } },
    stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null },
  { schemeId: 'rs-002', name: '回归-qa2', isDefault: false,
    dataSetSelection: [], injectionEntryIds: [],
    serviceBindings: { 'fin-service': { authAlias: 'qa2' } },
    stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null },
]

function mountMenu() {
  return mount(ScenarioExportMenu, {
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

/** 点开菜单(trigger 按钮 @click 触发 listRunSchemes),返回 teleport 到 body
 *  的下拉项 — flushPromises 等异步取数落定后再检索。 */
async function openMenu(w: ReturnType<typeof mountMenu>): Promise<HTMLElement[]> {
  await w.find('.se-trigger').trigger('click')
  await flushPromises()
  return [...document.querySelectorAll('.el-dropdown-menu__item')] as HTMLElement[]
}

beforeEach(() => {
  mockStore.exportJson.mockClear()
  mockStore.exportYaml.mockClear()
  mockStore.copyJson.mockClear()
  mockStore.draft = { scenarioId: 'sc-test' }
  listRunSchemesMock.mockReset()
})

afterEach(() => {
  // jsdom 不跑 transition,卸载时处于开态的下拉 popper 残留在 body —
  // 手工摘除,避免跨测试串到 document.querySelectorAll 的结果里。
  document.querySelectorAll('.el-dropdown__popper').forEach((el) => el.remove())
})

describe('ScenarioExportMenu — 按方案导出(新 CRUD 取数)', () => {
  it('开菜单取 listRunSchemes(scenarioId),方案子项走 exportJson(overlay)', async () => {
    listRunSchemesMock.mockResolvedValue(schemes)
    const w = mountMenu()
    const items = await openMenu(w)
    expect(listRunSchemesMock).toHaveBeenCalledWith('sc-test')
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

  it('overlay 只带 serviceBindings(dataSetIds 有意不带,导出是场景级)', async () => {
    listRunSchemesMock.mockResolvedValue(schemes)
    const w = mountMenu()
    const items = await openMenu(w)
    const item = items.find((i) => i.textContent!.includes('回归-qa2'))
    expect(item).toBeTruthy()
    item!.click()
    await flushPromises()
    const overlay = mockStore.exportJson.mock.calls[0][0]
    expect('dataSetIds' in overlay).toBe(false)
    expect(overlay.serviceBindings).toEqual({ 'fin-service': { authAlias: 'qa2' } })
    w.unmount()
  })

  it('无方案时菜单只剩原三动作,导出 JSON 零参调用(行为不变)', async () => {
    listRunSchemesMock.mockResolvedValue([])
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

  it('listRunSchemes 失败(非属主 403 等)静默降级 — 默认导出不受影响', async () => {
    listRunSchemesMock.mockRejectedValue(new Error('Request failed with status code 403'))
    const w = mountMenu()
    const items = await openMenu(w)
    expect(items).toHaveLength(3)
    expect(items.some((i) => i.textContent!.includes('按方案导出'))).toBe(false)
    items.find((i) => i.textContent!.includes('导出 JSON'))!.click()
    await flushPromises()
    expect(mockStore.exportJson).toHaveBeenCalledTimes(1)
    w.unmount()
  })
})
