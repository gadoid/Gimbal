/**
 * ScenarioExportMenu — 按方案导出(spec §8;阶段④:方案列表迁新 CRUD;
 * 2026-09-22 起形态与场景库行菜单同款:方案平铺为子菜单项)。
 *
 * 方案子项把方案的 overlay({serviceBindings};dataSetIds 有意不带 —
 * spec §7.3 导出是场景级)交给 store.exportJson 物化导出。方案来源 =
 * 开菜单时 listRunSchemes(draft.scenarioId)(V1 sidecar 读侧已下线);
 * 读侧失败/无方案 → 子菜单落「该场景暂无方案」置灰,默认导出不受影响
 * (静默降级)。
 *
 * 建件遵循 UsersCard.test.ts 惯例:ElementPlus 插件 + attachTo
 * document.body,弹层走真实 teleport,以 document.querySelectorAll 检索、
 * 原生 .click() 触发(CaseComposer.run.test.ts 记录过 popper 组件与
 * teleport stub 叠加在 jsdom 递归更新爆表,故不用 teleport stub)。
 * 子菜单同样真实驱动:点 SubTrigger 展开,再检索 teleport 到 body 的
 * 子项 — 与用户手势同路径。
 *
 * store mock 走 importOriginal 展开:保留真实 schemeToOverlay 参与
 * 断言(overlay 无多余键),而非 mock 自证。
 */
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
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
  { schemeId: 'rs-002', name: '同名方案', isDefault: false,
    dataSetSelection: [], injectionEntryIds: [],
    serviceBindings: { 'fin-service': { authAlias: 'qa2' } },
    stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null },
  { schemeId: 'rs-003', name: '同名方案', isDefault: false,
    dataSetSelection: [], injectionEntryIds: [],
    serviceBindings: { 'fin-service': { authAlias: 'qa3' } },
    stepTo: null, nRuns: 2, parallel: 3, plugins: null, logSub: null },
]

function mountMenu() {
  return mount(ScenarioExportMenu, {
    global: {},
    attachTo: document.body,
  })
}

/** 点开菜单(trigger 按钮 @click 触发 listRunSchemes),返回 teleport 到 body
 *  的下拉项 — flushPromises 等异步取数落定后再检索。 */
async function openMenu(w: ReturnType<typeof mountMenu>): Promise<HTMLElement[]> {
  await w.find('.se-trigger').trigger('click')
  await flushPromises()
  return [...document.querySelectorAll('[role=menuitem]')] as HTMLElement[]
}

/** 展开按方案导出子菜单(主菜单须已开),返回子项(teleport 到 body)。 */
async function openSchemeSub(): Promise<HTMLElement[]> {
  const subTrigger = [...document.querySelectorAll('[data-testid="export-sub-trigger"]')]
    .find((el): el is HTMLElement => el instanceof HTMLElement)
  if (!subTrigger) throw new Error('按方案导出子菜单触发器不在文档中')
  subTrigger.click()
  await flushPromises()
  return [...document.querySelectorAll('[data-testid^="export-scheme-"]')] as HTMLElement[]
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
  document.body.innerHTML = ''
})

describe('ScenarioExportMenu — 按方案导出(新 CRUD 取数)', () => {
  it('开菜单取 listRunSchemes(scenarioId),子菜单项走 exportJson(overlay)', async () => {
    listRunSchemesMock.mockResolvedValue(schemes)
    const w = mountMenu()
    const items = await openMenu(w)
    expect(listRunSchemesMock).toHaveBeenCalledWith('sc-test')
    // 原三动作仍在(svg 图标让 textContent 带空白,用 includes 断言)
    expect(items.some((i) => i.textContent!.includes('导出 JSON'))).toBe(true)
    // 方案在子菜单里(主菜单只有三动作 + 子菜单触发器,不因方案多而拉长)
    expect(items.filter((i) => i.textContent!.includes('冒烟-qa1'))).toHaveLength(0)

    const subItems = await openSchemeSub()
    const item = subItems.find((i) => i.dataset.testid === 'export-scheme-rs-001')
    expect(item).toBeTruthy()
    item!.click()
    await flushPromises()
    expect(mockStore.exportJson).toHaveBeenCalledTimes(1)
    expect(mockStore.exportJson).toHaveBeenCalledWith({
      serviceBindings: { 'fin-service': { authAlias: 'qa1' } } })
    w.unmount()
  })

  it('overlay 只带 serviceBindings(dataSetIds 有意不带,导出是场景级);同名方案以 schemeId 区分', async () => {
    listRunSchemesMock.mockResolvedValue(schemes)
    const w = mountMenu()
    await openMenu(w)
    const subItems = await openSchemeSub()
    // 同名方案两个都在,以 schemeId 为键(点 rs-003 拿 qa3,不串到 rs-002)
    expect(subItems.map((i) => i.dataset.testid)).toEqual(
      expect.arrayContaining(['export-scheme-rs-002', 'export-scheme-rs-003']))
    subItems.find((i) => i.dataset.testid === 'export-scheme-rs-003')!.click()
    await flushPromises()
    const overlay = mockStore.exportJson.mock.calls[0][0]
    expect('dataSetIds' in overlay).toBe(false)
    expect(overlay.serviceBindings).toEqual({ 'fin-service': { authAlias: 'qa3' } })
    w.unmount()
  })

  it('无方案 → 子菜单落「该场景暂无方案」,导出 JSON 零参调用(行为不变)', async () => {
    listRunSchemesMock.mockResolvedValue([])
    const w = mountMenu()
    const items = await openMenu(w)
    // 主菜单:三动作 + 子菜单触发器;子菜单本体给置灰说明而不是消失
    expect(items).toHaveLength(4)
    expect(items.some((i) => i.textContent!.includes('按方案导出'))).toBe(true)

    const subItems = await openSchemeSub()
    expect(subItems).toHaveLength(0)
    const emptyHint = [...document.querySelectorAll('[role=menuitem]')]
      .find((i) => i.textContent!.includes('该场景暂无方案'))
    expect(emptyHint).toBeTruthy()

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
    await openSchemeSub()
    const emptyHint = [...document.querySelectorAll('[role=menuitem]')]
      .find((i) => i.textContent!.includes('该场景暂无方案'))
    expect(emptyHint).toBeTruthy()
    items.find((i) => i.textContent!.includes('导出 JSON'))!.click()
    await flushPromises()
    expect(mockStore.exportJson).toHaveBeenCalledTimes(1)
    w.unmount()
  })
})
