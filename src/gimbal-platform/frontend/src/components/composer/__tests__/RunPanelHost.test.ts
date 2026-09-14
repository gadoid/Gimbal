/**
 * RunPanelHost — 运行面板宿主(方案工作台阶段③):两个执行入口共用的装配层。
 * - RH-1 自取数装配:getScenario + getScenarioDraft + listDataSets +
 *   listRunSchemes(V2,default 置顶)→ RunDialog 挂载,assertionEntries/
 *   deadEntryIds(含 legacy)透传
 * - RH-2 confirm → runScenario(dataSetIds 派生 + dataSetSelection 权威键 +
 *   schemeId/schemeName 溯源)→ 跳执行详情
 * - RH-2b 默认方案基线 confirm → 空选省略权威键,溯源带默认方案
 * - RH-3 saveAsScheme → createRunScheme(POST,name 断言)→ 重取 listRunSchemes
 * - RH-4/5/6 契约面掩空/收窄:deadEntryIds 是 RunDialog v2 自建方案失效判定的
 *   输入(injectionEntryIds 悬空 → 方案「失效 · 不可跑」)— pending 不判死、
 *   intrinsic 恒死、落定后收窄
 * - RH-7 契约降级 → 从严判定(只被契约托着的条目进 deadEntryIds)
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const pushMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock.push }),
  useRoute: () => ({ params: { scenarioId: 'sc-host' } }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))
vi.mock('@/api/auth_sessions', () => ({ list: async () => [{ alias: 'owner-1' }] }))

import * as api from '@/api/scenario-composer'
import type { SchemeV2 } from '@/api/scenario-composer'
import RunPanelHost from '@/components/composer/RunPanelHost.vue'
import RunDialog from '@/components/composer/RunDialog.vue'
import { executionUrl } from '@/utils/links'

const DEF = {
  kind: 'scenario', scenarioId: 'sc-host', meta: { name: 'host' },
  config: { vars: { amount: 100 }, services: { 'fin.test': 'http://fin' }, users: {} },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} },
      request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '0' }] },
    { kind: 'step', description: '查单', api: { headers: {} },
      request: { kind: 'request', body: {} }, strategy: [] },
  ],
}
const REG = {
  entries: [
    { id: 'inj-live', name: '金额为负',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: -1, asserts: [] },
    { id: 'inj-old', name: '旧版条目',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, injection: [], asserts: [] },
  ],
}
const DRAFT = {
  definition: DEF,
  orchestration: { steps: [{ name: '下单', enabled: true }, { name: '查单', enabled: true }], resourceMeta: {} },
  assertion_registry: REG,
}

/** V2 fixture:listRunSchemes 保证 default 置顶(宿主直连新 CRUD,不经 draft) */
const DEFAULT_SCHEME: SchemeV2 = {
  schemeId: 'rs-dft', name: '默认方案', isDefault: true,
  dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
  stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(api, 'getScenario').mockResolvedValue(
    { meta: { scenarioId: 'sc-host', name: 'host' }, steps: DEF.steps, stepCount: 2 } as any)
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(DRAFT as any)
  vi.spyOn(api, 'listDataSets').mockResolvedValue([
    { datasetId: 'ds-1', scenarioId: 'sc-host', name: 'A', rowCount: 2, preview: [] }] as any)
  vi.spyOn(api, 'listRunSchemes').mockResolvedValue([DEFAULT_SCHEME] as any)
  vi.spyOn(api, 'createRunScheme').mockResolvedValue(
    { ...DEFAULT_SCHEME, schemeId: 'rs-new', name: '回归', isDefault: false } as any)
  vi.spyOn(api, 'runScenario').mockResolvedValue({ runId: 'r-1', executionId: 7 } as any)
  pushMock.push.mockReset()
})
afterEach(() => { vi.restoreAllMocks() })

async function mountHost(props: Record<string, unknown> = {}) {
  const w = mount(RunPanelHost, {
    props: { scenarioId: 'sc-host', ...props } as any,
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
  await flushPromises()
  return w
}

it('RH-1: 自取数装配 — schemes V2(default 置顶)+ 条目/死条目透传(legacy 入 deadEntryIds)', async () => {
  const w = await mountHost()
  const dlg = w.findComponent(RunDialog)
  expect(dlg.exists()).toBe(true)
  expect(api.listRunSchemes).toHaveBeenCalledWith('sc-host')
  expect(dlg.props('schemes')).toEqual([DEFAULT_SCHEME])   // V2 形状(含 schemeId/isDefault)
  expect(dlg.props('initialSchemeId')).toBeNull()          // 本宿主无深链来源
  expect(dlg.props('assertionEntries')).toHaveLength(2)
  expect(dlg.props('deadEntryIds')).toEqual(['inj-old'])   // legacy 恒死(判据 = surface.deadIds ← registryIssues 的 legacy-entry)
  expect(dlg.props('serviceRows')).toEqual([{ service: 'fin.test', declaredUrl: 'http://fin' }])
  expect(dlg.props('stepOrchestrationNames')).toEqual(['下单', '查单'])
  w.unmount()
})

it('RH-2: confirm → runScenario 携带 dataSetSelection 权威键 + schemeId/schemeName 溯源 → 跳执行详情', async () => {
  const w = await mountHost()
  const dlg = w.findComponent(RunDialog)
  dlg.vm.$emit('confirm', [{ datasetId: 'ds-1', rowIndexes: [1] }], {
    schemeId: 'rs-a', schemeName: '冒烟', injectionEntryIds: ['inj-live'],
  })
  await flushPromises()
  expect(api.runScenario).toHaveBeenCalledTimes(1)
  const body = vi.mocked(api.runScenario).mock.calls[0][0] as any
  expect(body.scenarioId).toBe('sc-host')
  expect(body.schemeId).toBe('rs-a')        // 溯源两键透传(Task 1 后端已接受)
  expect(body.schemeName).toBe('冒烟')
  expect(body.dataSetIds).toEqual(['ds-1'])
  expect(body.dataSetSelection).toEqual([{ datasetId: 'ds-1', rowIndexes: [1] }])
  expect(body.injectionEntryIds).toEqual(['inj-live'])
  expect(w.emitted('close')).toBeTruthy()
  expect(pushMock.push).toHaveBeenCalledWith(executionUrl(7))
  w.unmount()
})

it('RH-2b: 空选 confirm(默认方案基线)→ 省略 dataSetSelection 键 + 溯源带默认方案', async () => {
  // 无数据集(基线运行)是合法路径:权威键 dataSetSelection 不下送
  // (空选 = 基线),兼容键 dataSetIds 仍送空数组;溯源两键恒带。
  vi.mocked(api.listDataSets).mockResolvedValue([])
  const w = await mountHost()
  await w.findAll('button').find((b) => b.text().includes('发起运行'))!.trigger('click')
  await flushPromises()
  expect(api.runScenario).toHaveBeenCalledTimes(1)
  const body = vi.mocked(api.runScenario).mock.calls[0][0] as any
  expect(body.dataSetIds).toEqual([])
  expect('dataSetSelection' in body).toBe(false)
  expect(body.schemeId).toBe('rs-dft')     // 默认方案也有真实 schemeId(v2)
  expect(body.schemeName).toBe('默认方案')
  w.unmount()
})

it('RH-3: saveAsScheme → createRunScheme POST(name 断言)→ 重取 schemes 整表替换', async () => {
  const w = await mountHost()
  const callsBefore = vi.mocked(api.listRunSchemes).mock.calls.length
  const body = {
    name: '回归', dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
    stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
  }
  w.findComponent(RunDialog).vm.$emit('saveAsScheme', body)
  await flushPromises()
  expect(api.createRunScheme).toHaveBeenCalledWith('sc-host', body)
  // 另存成功后重取(整表替换 → RunDialog schemes watch 重置默认态绑定 = 已知 deferred 行为)
  expect(api.listRunSchemes).toHaveBeenCalledTimes(callsBefore + 1)
  w.unmount()
})

it('RH-4: 契约面在途(冷启动)→ 契约依赖条目不被判死(掩空);legacy 恒死;落定后仍活', async () => {
  // 消费面(v2):deadEntryIds 是 RunDialog 自建方案失效判定的输入 —
  // 若把「尚未判定」当「判死」,锚定该条目的自建方案会误报「配置已失效 —
  // 不可运行」。本宿主自取数后才挂 RunDialog,`/full` 与挂载同 tick 才发起
  // ⇒ 首判定只有 body 面,正是 pending 窗口。
  const { _resetEndpointFullCacheForTest } = await import('@/composables/useEndpointFull')
  _resetEndpointFullCacheForTest()

  const withEid = structuredClone(DRAFT) as any
  withEid.definition.steps[0].api = { headers: {}, view_hints: { endpoint_id: 'ep-carry' } }
  withEid.assertion_registry = { entries: [
    ...REG.entries,
    { id: 'inj-carry', name: 'carry 偏离',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.customer_id' }, value: 261, asserts: [] },
  ] }
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(withEid)

  // 契约取数延迟 resolve:挂载后仍在飞(pending 窗口)
  let resolveFull!: (v: unknown) => void
  const pendingFull = new Promise((res) => { resolveFull = res })
  vi.spyOn(api, 'getFullEndpoint').mockReturnValue(pendingFull as any)

  const w = await mountHost()
  const dlg = w.findComponent(RunDialog)
  expect(api.getFullEndpoint).toHaveBeenCalledWith('ep-carry')
  // pending:尚未判定 ≠ 判死 ⇒ 掩空决策上移后在 pending 期间不进 deadEntryIds
  expect(dlg.props('deadEntryIds')).not.toContain('inj-carry')
  // 旧版条目是形状判(intrinsic),与契约面无关:pending 期间仍恒死
  expect(dlg.props('deadEntryIds')).toContain('inj-old')

  // 契约落定:精确命中 carry 声明 → 判活(由死转活不发生,维持不判死)
  resolveFull({ id: 'ep-carry', request: { declarations: [
    { name: 'customer_id', path: '$.customer_id', state: 'carry', required: true }] },
    declared_surface: ['$', '$.customer_id'] })
  await flushPromises()
  expect(dlg.props('deadEntryIds')).not.toContain('inj-carry')
  w.unmount()
})

it('RH-6: 契约 pending 期间 — intrinsic(step-oob)恒在 deadEntryIds,contractDependent 不判死;落定后并入', async () => {
  // 分组语义(阶段③ 消费面 = 自建方案失效判定):intrinsic 死因不依赖判定面,
  // pending 期间也不放行(否则锚定越界条目的方案在窗口内可跑);contractDependent
  // 只在契约落定后并入(可能变活)。
  const { _resetEndpointFullCacheForTest } = await import('@/composables/useEndpointFull')
  _resetEndpointFullCacheForTest()

  let release: (v: any) => void = () => {}
  vi.spyOn(api, 'getFullEndpoint').mockReturnValue(new Promise((res) => { release = res }) as any)
  vi.spyOn(api, 'getScenario').mockResolvedValue({ meta: { scenarioId: 'sc-h', name: 'h' }, steps: [], stepCount: 1 } as any)
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({
    definition: { kind: 'scenario', scenarioId: 'sc-h', meta: { name: 'h' }, config: {},
      steps: [{ kind: 'step', api: { kind: 'api', service: 's', method: 'POST', path: '/p', headers: {},
        view_hints: { endpoint_id: 'ep-h' } }, request: { kind: 'request', body: {} }, strategy: [] }] },
    orchestration: { steps: [], resourceMeta: {} },
    assertion_registry: { entries: [
      { id: 'inj-oob', name: '越界', path: { stepIndex: 9, source: 'body', jsonpath: '$.x' }, value: 1, asserts: [] },
      { id: 'inj-carry', name: '契约依赖', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_x' }, value: 1, asserts: [] },
    ] },
  } as any)
  const w = await mountHost()
  await flushPromises()                  // /full 仍挂起 ⇒ pending 为真
  const dlg = w.findComponent(RunDialog)
  const dead = dlg.props('deadEntryIds') as string[]
  expect(dead).toContain('inj-oob')        // step-oob:intrinsic ⇒ 恒死
  expect(dead).not.toContain('inj-carry')  // 契约依赖 ⇒ pending 期间不判死
  release({ id: 'ep-h', request: { declarations: [] }, declared_surface: ['$'] })  // 契约落定后收窄
  await flushPromises()
  expect(w.findComponent(RunDialog).props('deadEntryIds')).toContain('inj-carry')
  w.unmount()
})

it('RH-5: 契约落定后收窄(只删不增)— 拼错锚点的条目落定后进 deadEntryIds', async () => {
  // pending 期间契约依赖条目不判死 ⇒ 方案暂不失效;落定后仍无声明支撑的
  // (锚点拼写错)此时才进 deadEntryIds — 收窄只删不增,判活的不动。
  const { _resetEndpointFullCacheForTest } = await import('@/composables/useEndpointFull')
  _resetEndpointFullCacheForTest()

  const twoEid = structuredClone(DRAFT) as any
  twoEid.definition.steps[0].api = { headers: {}, view_hints: { endpoint_id: 'ep-1' } }
  twoEid.definition.steps[1].api = { headers: {}, view_hints: { endpoint_id: 'ep-2' } }
  twoEid.assertion_registry = { entries: [
    ...REG.entries,
    { id: 'inj-ghost', name: '拼写错的锚点',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.ghost' }, value: 1, asserts: [] },
    // 条目锚在步骤 1:在途面 = 「被条目引用到的端点」(useInjectableSurface),
    // 无此条目则 ep-2 不进判定面,「只落定一步仍在途」这一档无法成立。
    { id: 'inj-s1', name: '第二步条目',
      path: { stepIndex: 1, source: 'body', jsonpath: '$.s1' }, value: 1, asserts: [] },
  ] }
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(twoEid)

  const deferred: Record<string, (v: unknown) => void> = {}
  vi.spyOn(api, 'getFullEndpoint').mockImplementation((id: string) =>
    new Promise((res) => { deferred[id] = res }) as any)

  const w = await mountHost()
  const dlg = w.findComponent(RunDialog)
  expect(dlg.props('deadEntryIds')).not.toContain('inj-ghost')   // pending:不过滤,先不判死

  // 只落定其中一步 → 仍在途,不收窄
  deferred['ep-1']({ id: 'ep-1', request: { declarations: [] } })
  await flushPromises()
  expect(dlg.props('deadEntryIds')).not.toContain('inj-ghost')

  // 契约全部落定 → 收窄一次:判死的进入,判活的(inj-live)不动
  deferred['ep-2']({ id: 'ep-2', request: { declarations: [] } })
  await flushPromises()
  const dead = dlg.props('deadEntryIds') as string[]
  expect(dead).toContain('inj-ghost')                            // 落定后确实判死
  expect(dead).not.toContain('inj-live')
  w.unmount()
})

it('RH-7: 契约降级 → 从严判定:只被契约托着的条目进 deadEntryIds(自建方案失效判定从严)', async () => {
  // 降级的可观测后果(v2):失败也是答案 — 声明面退回 body 面,此刻
  // path-unresolvable 即真死 ⇒ 锚定该条目的自建方案判「失效 · 不可跑」。
  const draft = JSON.parse(JSON.stringify(DRAFT))
  draft.definition.steps[0].api = { headers: {}, view_hints: { endpoint_id: 'ep-host' } }
  draft.assertion_registry = { entries: [
    { id: 'inj-c', name: '契约依赖',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_x' }, value: 1, asserts: [] }] }
  vi.mocked(api.getScenarioDraft).mockResolvedValue(draft as any)
  vi.spyOn(api, 'getFullEndpoint').mockRejectedValue(new Error('plate down'))

  const w = await mountHost()
  const dlg = w.findComponent(RunDialog)
  expect(dlg.props('deadEntryIds')).toEqual(['inj-c'])   // 从严判定 ⇒ 锚定方案不可跑
  w.unmount()
})
