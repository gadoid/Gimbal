/**
 * RunPanelHost — 运行面板宿主(spec v3 §6):两个执行入口共用的装配层。
 * - RH-1 自取数装配:getScenario + getScenarioDraft + listDataSets → RunDialog
 *   挂载,assertionEntries/deadEntryIds(含 legacy)透传
 * - RH-2 confirm → runScenario(dataSetIds 派生 + dataSetSelection 权威键)
 *   → 跳执行详情
 * - RH-3 saveScheme → putRunSchemes(scenarioId, 整表)
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
  orchestration: { steps: [{ name: '下单', enabled: true }, { name: '查单', enabled: true }], resourceMeta: {}, runSchemes: [] },
  assertion_registry: REG,
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(api, 'getScenario').mockResolvedValue(
    { meta: { scenarioId: 'sc-host', name: 'host' }, steps: DEF.steps, stepCount: 2 } as any)
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(DRAFT as any)
  vi.spyOn(api, 'listDataSets').mockResolvedValue([
    { datasetId: 'ds-1', scenarioId: 'sc-host', name: 'A', rowCount: 2, preview: [] }] as any)
  vi.spyOn(api, 'runScenario').mockResolvedValue({ runId: 'r-1', executionId: 7 } as any)
  vi.spyOn(api, 'putRunSchemes').mockResolvedValue([] as any)
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

it('RH-1: 自取数装配 — RunDialog 挂载 + 条目/死条目透传(legacy 入 deadEntryIds)', async () => {
  const w = await mountHost()
  const dlg = w.findComponent(RunDialog)
  expect(dlg.exists()).toBe(true)
  expect(dlg.props('assertionEntries')).toHaveLength(2)
  expect(dlg.props('deadEntryIds')).toEqual(['inj-old'])   // legacy 恒死(判据 = surface.deadIds ← registryIssues 的 legacy-entry)
  expect(dlg.props('preset')).toBeNull()
  expect(dlg.props('serviceRows')).toEqual([{ service: 'fin.test', declaredUrl: 'http://fin' }])
  expect(dlg.props('stepOrchestrationNames')).toEqual(['下单', '查单'])
  w.unmount()
})

it('RH-2: confirm → runScenario 携带 dataSetSelection 权威键 → 跳执行详情', async () => {
  const w = await mountHost({
    preset: { dataSetSelection: [{ datasetId: 'ds-1', rowIndexes: [1] }], injectionEntryIds: ['inj-live'] },
  })
  const dlg = w.findComponent(RunDialog)
  expect(dlg.props('preset')).toEqual({
    dataSetSelection: [{ datasetId: 'ds-1', rowIndexes: [1] }],
    injectionEntryIds: ['inj-live'],
  })
  dlg.vm.$emit('confirm', [{ datasetId: 'ds-1', rowIndexes: [1] }], { injectionEntryIds: ['inj-live'] })
  await flushPromises()
  expect(api.runScenario).toHaveBeenCalledTimes(1)
  const body = vi.mocked(api.runScenario).mock.calls[0][0] as any
  expect(body.scenarioId).toBe('sc-host')
  expect(body.dataSetIds).toEqual(['ds-1'])
  expect(body.dataSetSelection).toEqual([{ datasetId: 'ds-1', rowIndexes: [1] }])
  expect(body.injectionEntryIds).toEqual(['inj-live'])
  expect(w.emitted('close')).toBeTruthy()
  expect(pushMock.push).toHaveBeenCalledWith(executionUrl(7))
  w.unmount()
})

it('RH-2b: 空选 confirm → 省略 dataSetSelection 键 + dataSetIds 空数组', async () => {
  // 无数据集(基线运行)是合法路径:权威键 dataSetSelection 不下送
  // (spec v3 §4 空选 = 基线),兼容键 dataSetIds 仍送空数组。
  vi.mocked(api.listDataSets).mockResolvedValue([])
  const w = await mountHost()
  await w.findAll('button').find((b) => b.text().includes('发起运行'))!.trigger('click')
  await flushPromises()
  expect(api.runScenario).toHaveBeenCalledTimes(1)
  const body = vi.mocked(api.runScenario).mock.calls[0][0] as any
  expect(body.dataSetIds).toEqual([])
  expect('dataSetSelection' in body).toBe(false)
  w.unmount()
})

it('RH-3: saveScheme → putRunSchemes(scenarioId, 整表含新方案)', async () => {
  const w = await mountHost()
  const scheme = { name: '回归', dataSetIds: [], dataSetSelection: [], injectionEntryIds: ['inj-live'], serviceBindings: {} }
  w.findComponent(RunDialog).vm.$emit('saveScheme', scheme)
  await flushPromises()
  expect(api.putRunSchemes).toHaveBeenCalledWith('sc-host', [scheme])
  w.unmount()
})

it('RH-4: 契约面在途(冷启动)→ preset 锚在 carry 声明的条目不被判死/丢预勾;落定后仍勾上', async () => {
  // 复现入口:本宿主自取数后才挂 RunDialog,`/full` 与挂载同 tick 才发起
  // ⇒ 首判定只有 body 面。若把「尚未判定」当「判死」:preset 的 carry 条目
  // 被静默滤掉,而契约回来后 preset prop 不变、RunDialog 的 watch 不重跑
  // → 预勾永不重放;同一个窗口里它还先渲染成「悬空 — 不可选」再翻活。
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

  const w = await mountHost({ preset: { injectionEntryIds: ['inj-carry', 'inj-old'] } })
  const dlg = w.findComponent(RunDialog)
  expect(api.getFullEndpoint).toHaveBeenCalledWith('ep-carry')
  // 前提:宿主此刻的判定只跑过 body 面 —— carry 条目只被契约面托着,属
  // 「仅因契约未定而判死」⇒ 掩空决策上移后在 pending 期间**不进** deadEntryIds
  // (此前是 deadEntryIds 照旧带上、由 RunDialog 整体掩空 —— 那会连
  // step-oob/legacy 一起放行,RH-6 钉住该缺陷)
  expect(dlg.props('deadEntryIds')).not.toContain('inj-carry')
  expect(dlg.props('contractPending')).toBe(true)
  // pending:尚未判定 ≠ 判死 → 不标悬空、不禁选、预勾保留
  const boxOf = () => dlg.findAll('.rd-injection .el-checkbox')
    .find((b) => b.text().includes('carry 偏离'))!
  expect(boxOf().find('input').attributes('disabled')).toBeUndefined()
  expect(boxOf().text()).not.toContain('悬空')
  // 旧版条目是形状判,与契约面无关:pending 期间**仍**禁选、预勾仍被滤掉
  // (悬空被掩空成不过滤时,legacy 若不显式排除会勾成 disabled 的卡死态)
  const legacyBox = dlg.findAll('.rd-injection .el-checkbox')
    .find((b) => b.text().includes('旧版条目'))!
  expect(legacyBox.find('input').attributes('disabled')).toBeDefined()
  expect((dlg.vm as any).injectionIds).toEqual(['inj-carry'])

  // 契约落定:精确命中 carry 声明 → 判活;预勾仍在(收窄只删判死的)
  resolveFull({ id: 'ep-carry', request: { declarations: [
    { name: 'customer_id', path: '$.customer_id', state: 'carry', required: true }] },
    declared_surface: ['$', '$.customer_id'] })
  await flushPromises()
  expect(dlg.props('contractPending')).toBe(false)
  expect(dlg.props('deadEntryIds')).not.toContain('inj-carry')   // 由死转活
  expect(boxOf().find('input').attributes('disabled')).toBeUndefined()
  expect((dlg.vm as any).injectionIds).toEqual(['inj-carry'])    // 预勾未被丢
  w.unmount()
})

it('RH-6: 契约 pending 期间 — intrinsic 死条目仍禁选,contractDependent 不标死', async () => {
  // 修 C 的可观察面:此前 RunDialog 在 contractPending 期间把 deadIds **整体**
  // 掩空 ⇒ 连不依赖判定面的死因(step-oob / legacy)也失去禁选,窗口内能勾上
  // 真悬空条目并下发(后端 skip,对话框照旧承诺)。判据分组上移到宿主后:
  // intrinsic 恒禁选,只有 contractDependent 在 pending 期间不标死。
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
  expect(dlg.props('contractPending')).toBe(true)
  const boxes = dlg.findAll('.rd-injection .el-checkbox')
  expect(boxes[0].find('input').attributes('disabled')).toBeDefined()   // step-oob:intrinsic ⇒ 仍禁选
  expect(boxes[0].text()).toContain('悬空')
  expect(boxes[1].find('input').attributes('disabled')).toBeUndefined() // 契约依赖 ⇒ pending 期间不禁选
  release({ id: 'ep-h', request: { declarations: [] }, declared_surface: ['$'] })  // 契约落定后收窄
  await flushPromises()
  expect(w.findComponent(RunDialog).findAll('.rd-injection .el-checkbox')[1]
    .find('input').attributes('disabled')).toBeDefined()
  w.unmount()
})

it('RH-5: 契约落定后补一次收窄(只删不增)+ 用户手动勾选不被覆盖', async () => {
  // pending 期间条目一律不禁选 ⇒ 用户可以勾上一个**落定后才判死**的条目。
  // 留着它就是 disabled + 「悬空 — 不可选」却仍被 confirm 下送 / dispatch
  // 静默 skip 的卡死态 ⇒ 落定后收窄一次;仍在判活的(含用户手动勾选)不动。
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

  const w = await mountHost({ preset: { injectionEntryIds: ['inj-ghost'] } })
  const dlg = w.findComponent(RunDialog)
  expect(dlg.props('contractPending')).toBe(true)
  expect((dlg.vm as any).injectionIds).toEqual(['inj-ghost'])    // pending:不过滤,先勾上

  // 只落定其中一步 → 仍在途,不收窄
  deferred['ep-1']({ id: 'ep-1', request: { declarations: [] } })
  await flushPromises()
  expect(dlg.props('contractPending')).toBe(true)
  expect((dlg.vm as any).injectionIds).toEqual(['inj-ghost'])

  // 用户在 pending 窗口里手动勾上一条判活的条目
  ;(dlg.vm as any).injectionIds = ['inj-ghost', 'inj-live']
  await flushPromises()

  // 契约全部落定 → 收窄一次:判死的移出,手动勾的活条目原样保留
  deferred['ep-2']({ id: 'ep-2', request: { declarations: [] } })
  await flushPromises()
  expect(dlg.props('contractPending')).toBe(false)
  expect(dlg.props('deadEntryIds')).toContain('inj-ghost')       // 落定后确实判死
  expect((dlg.vm as any).injectionIds).toEqual(['inj-live'])
  w.unmount()
})

it('RH-4: 契约降级 → 运行对话框里给出提示 + 重试入口;重试成功即恢复(症状现场必须看得见)', async () => {
  // 这条 known-issue 的症状是「条目灰着、点不动」,而那正是发生在**这个对话框**里:
  // 提示与重试入口若只留在编辑器/画布,用户在症状现场看到的仍是"不知道为什么"。
  const draft = JSON.parse(JSON.stringify(DRAFT))
  draft.definition.steps[0].api = { headers: {}, view_hints: { endpoint_id: 'ep-host' } }
  draft.assertion_registry = { entries: [
    { id: 'inj-c', name: '契约依赖',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_x' }, value: 1, asserts: [] }] }
  vi.mocked(api.getScenarioDraft).mockResolvedValue(draft as any)
  const net = vi.spyOn(api, 'getFullEndpoint')
    .mockRejectedValueOnce(new Error('plate down'))          // 挂载那一次失败
    .mockResolvedValue({                                     // 重试时 plate 已恢复
      id: 'ep-host',
      request: { declarations: [
        { name: 'carry_x', path: '$.carry_x', state: 'carry', required: true, description: '' }] },
      declared_surface: ['$', '$.carry_x'],
    } as any)

  const w = await mountHost()
  const dlg = w.findComponent(RunDialog)
  // 降级姿势的可观测后果:只被契约托着的条目被从严判死 ⇒ 对话框里不可勾选
  expect(dlg.props('contractDegraded')).toBe(true)
  expect(dlg.props('deadEntryIds')).toEqual(['inj-c'])
  const notice = dlg.find('.surface-notice')
  expect(notice.exists()).toBe(true)
  expect(notice.text()).toContain('契约取数失败')

  // 重试入口:窗口内的**显式**动作也真发(不受负缓存约束)
  await notice.find('.surface-notice-retry').trigger('click')
  await flushPromises()
  expect(net).toHaveBeenCalledTimes(2)                     // ← 点出来的那次取数
  expect(dlg.props('contractDegraded')).toBe(false)        // 恢复 ⇒ 提示消失
  expect(dlg.props('deadEntryIds')).toEqual([])            // 条目由死转活(可勾选)
  w.unmount()
})
