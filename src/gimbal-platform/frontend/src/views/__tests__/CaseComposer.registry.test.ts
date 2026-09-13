/**
 * CaseComposer — registryAdd 落条目通路(spec v3 §5/Task 5):Canvas
 * emit('registryAdd', mark) → onRegistryAdd 落 registry.entries(path 直取
 * 标记载荷 + value 预填字段当前字面量)+ 显式保存调度(registry 不在
 * dirty watch 源 → 防抖自动 PUT 须携带 assertion_registry,标记不丢)。
 *
 * 终审 F2:loadScenario 的 GET /draft 失败(注册表未水化)→ 本地空
 * registry 不可信 — 保存前重试拉取合并;重试仍失败则中止保存,
 * 绝不带空 assertion_registry 整包 PUT(会把存量条目永久冲掉)。
 *
 * 骨架 = CaseComposer.vardemote.test.ts 的 mock 面(模块 mock 构造器 impl
 * + 真实 vue-router memory history);挂载直取 ?step=4 进 Canvas 步,
 * 断言落在 draft store 同步面与 updateScenario spy。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { nextTick } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ElementPlus from 'element-plus'
import CaseComposer from '@/views/CaseComposer.vue'
import CaseComposerCanvas from '@/components/composer/CaseComposerCanvas.vue'
import * as api from '@/api/scenario-composer'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
import type { Scenario } from '@/types/scenario-composer'

// 模块 mock(构造器 impl 防 vi.restoreAllMocks 清实现,vardemote 同款):
// CaseComposer onMounted 拉常量池 / 执行历史,Canvas 拉认证列表 — 静默化。
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(() => Promise.resolve([])),
}))
vi.mock('@/api/constants', () => ({
  list: vi.fn(() => Promise.resolve([])),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
// Canvas onMounted 旁路拉取(CaseComposerCanvas.test.ts mock 面同款):
// carry 值表 / 目录服务名 / 取数视图 — 挂载即触发,全部静默不碰网络。
vi.mock('@/api/carry', () => ({
  getDefaults: vi.fn(() => Promise.resolve({})),
  getBindings: vi.fn(() => Promise.resolve({})),
}))
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceNames: vi.fn(async () => []),
  loadCatalogSystemByService: vi.fn(async () => new Map()),
}))
vi.mock('@/api/query-views', () => ({
  fetchQueryViewIndex: vi.fn(async () => []),
  fetchQueryViewRows: vi.fn(),
}))

function sampleScenario(): Scenario {
  return {
    meta: {
      scenarioId: 'sc-demo',
      name: '订单创建 e2e',
      description: '',
      module: '订单',
      priority: 1,
      author: 'qa',
      owner: 'qa',
      tags: [],
      system: ['fin'],
      version: 'v0.1.0',
      expire: false,
      createTime: '2026-01-01T00:00:00Z',
    },
    steps: [{
      kind: 'step',
      description: 's',
      api: { kind: 'api', service: 'fin-service', method: 'POST', path: '/x', headers: {}, view_hints: {} },
      request: { kind: 'request', body: {} },
      strategy: [],
    }] as unknown as Scenario['steps'],
    // §4 fixture:base_url = 基线值(偏离 injection 默认取它)
    config: { vars: { base_url: 'http://x', exp_code: 200 } },
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: 1,
    tags: [],
  }
}

let router: Router
async function mountPage(path = '/composer/sc-demo?step=4') {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/composer/:scenarioId', component: CaseComposer },
      { path: '/scenarios', component: { template: '<div id="scen-list" />' } },
    ],
  })
  router.push(path)
  await router.isReady()
  const w = mount({ template: '<router-view />' }, {
    global: { plugins: [router, ElementPlus, createPinia()] },
    attachTo: document.body,
  })
  await flushPromises()
  return w
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(api, 'listDataSets').mockResolvedValue([])
  // loadScenario 二级取数(spec v2 §3 断言注册表):mock 掉防真实 XHR 悬挂
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({} as any)
  vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario())
  vi.spyOn(api, 'listStrategyKinds').mockResolvedValue([])
  // registryAdd 触发 dirty → 防抖自动 PUT;fake timers 推进 2.5s 后发,
  // spy 兜底保证任何时序下都不碰真实网络。
  vi.spyOn(api, 'updateScenario').mockResolvedValue(sampleScenario())
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
})
afterEach(() => {
  vi.useRealTimers()
})

describe('CaseComposer — registryAdd 落条目 + 保存调度(spec v3 §5)', () => {
  const MARK = { kind: 'inject' as const, stepIndex: 0, source: 'body' as const, jsonpath: '$.base_url', value: 'http://x' }

  it('registryAdd → registry.entries 落偏离条目(path/value 直取载荷)→ draft store 同步', async () => {
    const w = await mountPage()
    const canvas = w.findComponent(CaseComposerCanvas)
    expect(canvas.exists()).toBe(true)
    canvas.vm.$emit('registryAdd', MARK)
    await nextTick()
    await flushPromises()
    const reg = (useScenarioDraftStore().draft as any).assertion_registry
    expect(reg.entries).toHaveLength(1)
    expect(reg.entries[0].id).toMatch(/^inj-/)
    expect(reg.entries[0].name).toBe('$.base_url')
    expect(reg.entries[0].path).toEqual({ stepIndex: 0, source: 'body', jsonpath: '$.base_url' })
    expect(reg.entries[0].value).toBe('http://x')      // 字段当前字面量预填
    expect(reg.entries[0].asserts).toEqual([])
    w.unmount()
  })

  it('registryAdd 触发防抖自动保存 — PUT 携带 assertion_registry(v3 形状)', async () => {
    const w = await mountPage()
    ;(api.updateScenario as any).mockClear()   // 隔离挂载期噪音
    const canvas = w.findComponent(CaseComposerCanvas)
    canvas.vm.$emit('registryAdd', MARK)
    await nextTick()
    await flushPromises()
    expect(api.updateScenario).not.toHaveBeenCalled()   // 防抖未到不发
    vi.advanceTimersByTime(2500)
    await flushPromises()
    await flushPromises()
    expect(api.updateScenario).toHaveBeenCalledTimes(1)
    const draft = (api.updateScenario as any).mock.calls[0][1]
    expect(draft.assertion_registry.entries).toHaveLength(1)
    expect(draft.assertion_registry.entries[0].path).toEqual({
      stepIndex: 0, source: 'body', jsonpath: '$.base_url',
    })
    expect(draft.assertion_registry.entries[0].value).toBe('http://x')
    w.unmount()
  })
})

describe('CaseComposer — 存量空注册表形状归一(assertion_registry: {})', () => {
  it('draft 返回 {} 形状(旧场景经 pydantic default 补形)→ 切配置签正常渲染', async () => {
    // 真实后端形状:V2 之前保存的场景 payload 无该键,GET /draft 经
    // ScenarioDraft.model_validate 重铸 → assertion_registry 补成 {}
    // (无 entries,truthy)。修复前水化 ?? 只兜 null → registry.value={}
    // → 配置签分支求值 registry.entries.length 抛 TypeError → 父渲染
    // patch 中止 → 旧签内容残留(其余签不评估该 prop,故仅配置签切不进)。
    vi.mocked(api.getScenarioDraft).mockResolvedValue({
      definition: {},
      orchestration: { steps: [], resourceMeta: {} },
      assertion_registry: {},
    } as any)
    const w = await mountPage()   // ?step=4 → Canvas
    expect(w.findComponent(CaseComposerCanvas).exists()).toBe(true)
    await w.findAll('.stepper-inner .step')[2].trigger('click')   // → ③ 配置
    await flushPromises()
    expect(w.text()).toContain('时间策略')   // 配置签首卡渲染
    expect(w.text()).toContain('断言管理')   // 入口卡(spec v2 §7)
    w.unmount()
  })
})

describe('CaseComposer — 注册表水化失败防擦除(终审 F2)', () => {
  const MARK = { kind: 'inject' as const, stepIndex: 0, source: 'body' as const, jsonpath: '$.base_url', value: 'http://x' }

  /** 服务端存量注册表(用户精心维护的条目 — 擦除事故的受害面) */
  const SERVER_DRAFT = {
    definition: {},
    orchestration: { steps: [], resourceMeta: {} },
    assertion_registry: {
      entries: [{
        id: 'inj-server-1',
        name: '存量偏离',
        anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount', varName: 'amount' },
        injection: [{ varName: 'amount', value: '-1' }],
        asserts: [],
      }],
    },
  } as any

  it('GET /draft 加载失败 + 保存前重试仍失败 → 自动保存中止,不 PUT 空 assertion_registry', async () => {
    // 加载与重试全部失败(草稿端点持续不可达)
    vi.mocked(api.getScenarioDraft).mockRejectedValue(new Error('draft 503'))
    const w = await mountPage()
    ;(api.updateScenario as any).mockClear()
    const canvas = w.findComponent(CaseComposerCanvas)
    canvas.vm.$emit('registryAdd', MARK)
    await nextTick()
    await flushPromises()
    vi.advanceTimersByTime(2500)
    await flushPromises()
    await flushPromises()
    // 加载 1 次 + 保存前重试 1 次;重试失败 → 中止保存 — 绝不带未水化
    //(空/仅本地)registry 整包 PUT 冲掉服务端存量条目
    expect(api.getScenarioDraft).toHaveBeenCalledTimes(2)
    expect(api.updateScenario).not.toHaveBeenCalled()
    w.unmount()
  })

  it('重试成功 → 按 id 并集水化后 PUT(存量 + 失败窗口内本地新增);水化后不再重拉', async () => {
    // 加载瞬时失败,保存前重试恢复并带回存量注册表
    vi.mocked(api.getScenarioDraft)
      .mockRejectedValueOnce(new Error('transient'))
      .mockResolvedValue(SERVER_DRAFT)
    const w = await mountPage()
    ;(api.updateScenario as any).mockClear()
    const canvas = w.findComponent(CaseComposerCanvas)
    canvas.vm.$emit('registryAdd', MARK)   // 失败窗口内本地新增(偏离 1)
    await nextTick()
    await flushPromises()
    vi.advanceTimersByTime(2500)
    await flushPromises()
    await flushPromises()
    expect(api.updateScenario).toHaveBeenCalledTimes(1)
    const entries = (api.updateScenario as any).mock.calls[0][1].assertion_registry.entries
    // 并集:服务端存量在前,本地新增在后(按 id 不重不丢)
    expect(entries).toHaveLength(2)
    expect(entries[0].id).toBe('inj-server-1')
    expect(entries[1].name).toBe('$.base_url')

    // 水化完成后:后续自动保存不再重拉 /draft(registryHydrated 已置位)
    canvas.vm.$emit('registryAdd', MARK)
    await nextTick()
    await flushPromises()
    vi.advanceTimersByTime(2500)
    await flushPromises()
    await flushPromises()
    expect(api.updateScenario).toHaveBeenCalledTimes(2)
    expect(api.getScenarioDraft).toHaveBeenCalledTimes(2)
    w.unmount()
  })
})

/** 断言条目区/配置签共用的 fixture:步骤 0 的 request.body 带 $.amount 叶子
 *  (path 可解析),注册表三条 = 可解析 / 越界 / 旧版。 */
const TD_ENTRIES = [
  { id: 'inj-alive', name: '可解析',
    path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: 1, asserts: [] },
  { id: 'inj-oob', name: '越界',
    path: { stepIndex: 9, source: 'body', jsonpath: '$.x' }, value: 1, asserts: [] },
  { id: 'inj-old', name: '旧版',
    anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, injection: [], asserts: [] },
]
function mockBodyScenarioOnce() {
  const scen = sampleScenario()
  ;(scen.steps[0] as any).request = { kind: 'request', body: { amount: 100 } }
  vi.mocked(api.getScenario).mockResolvedValue(scen)
}

describe('CaseComposer — 响应侧标记落**草稿**条目(判定 ①②③④)', () => {
  const RESP_MARK = { kind: 'assert' as const, stepIndex: 0, target: '$.response_body.code' }

  it('kind=assert → 注入地址空 / value 空 / asserts[0] 为**追加式** exists', async () => {
    const w = await mountPage()
    const canvas = w.findComponent(CaseComposerCanvas)
    canvas.vm.$emit('registryAdd', RESP_MARK)
    await nextTick()
    await flushPromises()
    const reg = (useScenarioDraftStore().draft as any).assertion_registry
    expect(reg.entries).toHaveLength(1)
    const e = reg.entries[0]
    expect(e.id).toMatch(/^inj-/)
    expect(e.name).toBe('$.response_body.code')
    // 草稿:注入地址留空 —— 用户到断言管理补齐后该条目才在运行期生效
    expect(e.path).toEqual({ stepIndex: 0, source: 'body', jsonpath: '' })
    expect(e.value).toBe('')
    // mode 必须 append:override 的语义是「覆写既有断言(匹配键=步骤+target)」,
    // 而新建的断言没有可覆写对象 —— 前端判 override-no-match,后端 override
    // 分支找不到匹配就什么都不做,等于这条断言永不生效。
    expect(e.asserts).toEqual([
      { stepIndex: 0, target: '$.response_body.code', operator: 'exists', expected: '', mode: 'append' },
    ])
    w.unmount()
  })
})

describe('CaseComposer — deadEntryIds 计算(裁定 10:CaseComposer 侧无他测覆盖)', () => {
  it('步骤树 + 注册表投影:越界/旧版判死,可解析条目不判死', async () => {
    // RunPanelHost 的同款计算由 RH-* 锁定;CaseComposer 的这份副本此前无测试 —
    // 回归会让运行面板整片灰掉且注入静默不可选,而全套测试仍绿。
    mockBodyScenarioOnce()
    vi.mocked(api.getScenarioDraft).mockResolvedValue({
      definition: { steps: sampleScenario().steps },
      orchestration: { steps: [], resourceMeta: {} },
      assertion_registry: { entries: TD_ENTRIES },
    } as any)
    const w = await mountPage()
    const page = w.findComponent(CaseComposer)
    expect((page.vm as any).deadEntryIds).toEqual(['inj-oob', 'inj-old'])
    w.unmount()
  })
})

describe('CaseComposer — 配置签「加入本次执行」预勾运行面板(裁定 13)', () => {
  it('onRunEntry(id) → runPreset = {injectionEntryIds: [id]} 且运行面板打开', async () => {
    mockBodyScenarioOnce()
    vi.mocked(api.getScenarioDraft).mockResolvedValue({
      definition: { steps: sampleScenario().steps },
      orchestration: { steps: [], resourceMeta: {} },
      assertion_registry: { entries: TD_ENTRIES },
    } as any)
    // ?step=3 → ③ 配置签(断言管理纯展示列表在此)
    const w = await mountPage('/composer/sc-demo?step=3')
    const page = w.findComponent(CaseComposer)
    expect((page.vm as any).runPreset).toBeNull()
    expect((page.vm as any).runDialogOpen).toBe(false)
    await w.find('.are-run').trigger('click')
    await flushPromises()
    expect((page.vm as any).runPreset).toEqual({ injectionEntryIds: ['inj-alive'] })
    expect((page.vm as any).runDialogOpen).toBe(true)
    w.unmount()
  })
})
