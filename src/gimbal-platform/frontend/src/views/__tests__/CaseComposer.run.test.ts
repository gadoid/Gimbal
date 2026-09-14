/**
 * CaseComposer — RunDialog v2 对接(方案工作台阶段③):
 * - 打开/关闭/confirm 主链路:schemes 直连 listRunSchemes(V2,default 置顶),
 *   lastRunOverlay/preset/契约 props 退役(整块删除);confirm 溯源带
 *   schemeId/schemeName(Task 1);
 * - serviceRows = 声明 ∪ 引用并集(steps 引用未声明 → declaredUrl null);
 * - confirm 新签名:serviceBindings 原样上送,RunRequest 无 env,退役键
 *   (prefix/mergePolicy/auths/injectCredentials)不出现;
 * - stepTo=0 合法(0-based halt 索引,首步后停)不被 falsy 过滤;
 * - saveAsScheme → createRunScheme POST + 重取 listRunSchemes 整表替换;
 * - 深链 ?runScheme=rs-xxx → 打开弹窗并预选,query 即清(防刷新重复弹)。
 *
 * 建件/mock 结构抄 CaseComposer.poolrail.test.ts(vi.hoisted + 构造器 impl
 * 工厂 mock 防 vi.restoreAllMocks 清实现;scenario-composer 走 spyOn)。
 * 交互走真实 DOM(顶栏运行按钮 + RunDialog 控件),弹层 Teleport 以
 * stubs: { teleport: true } 收回到 wrapper 内(RunDialog 兄弟测试同款)。
 */
import { afterEach, describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import CaseComposer from '@/views/CaseComposer.vue'
import * as api from '@/api/scenario-composer'
import type { SchemeV2 } from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'
import { _resetEndpointFullCacheForTest } from '@/composables/useEndpointFull'

const mockRoute: { params: { scenarioId: string }; query: Record<string, string> } = {
  params: { scenarioId: 'sc-demo' },
  query: {},
}
const routerMock = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn().mockResolvedValue(undefined),
}))
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mockRoute,
    useRouter: () => routerMock,
  }
})

vi.mock('@/api/constants', () => ({
  list: vi.fn(() => Promise.resolve([])),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(() => Promise.resolve([{ alias: 'qa1' }])),
}))

/** V2 fixture:listRunSchemes 保证 default 置顶 */
const DEFAULT_SCHEME: SchemeV2 = {
  schemeId: 'rs-dft', name: '默认方案', isDefault: true,
  dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
  stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
}
const SCHEME_B: SchemeV2 = {
  schemeId: 'rs-002', name: '冒烟', isDefault: false,
  dataSetSelection: [{ datasetId: 'ds-1', rowIndexes: [0] }],
  injectionEntryIds: [], serviceBindings: { 'fin-service': { authAlias: 'qa1' } },
  stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
}

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
    steps: [{ api: { service: 'fin-service', method: 'POST', path: '/x' } }] as Scenario['steps'],
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: 1,
    tags: [],
  }
}

function mountPage() {
  // teleport stub 把 RunDialog 弹层收回到 wrapper 内(find 可达)。ElementPlus
  // 的 popper 组件(ScenarioExportMenu 的 el-dropdown、Meta 的 el-select)
  // 与 teleport stub 叠加会在 jsdom 下递归更新爆表 — 与本对接无关,一并 stub。
  return mount(CaseComposer, {
    global: {
      plugins: [ElementPlus, createPinia()],
      stubs: { teleport: true, ScenarioExportMenu: true, CaseComposerMeta: true },
    },
  })
}

/** 建件:getScenario 回样例场景(steps 引用 fin-service,config 未声明 service) */
async function mountComposerWithDraft() {
  vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario())
  const w = mountPage()
  await flushPromises()
  return w
}

/** 打开运行弹层(顶栏「运行」按钮 — canRun: scenario 已载入 + steps>0) */
async function openRunDialog(w: ReturnType<typeof mount>) {
  const runBtn = w.find('header .primary-btn')
  expect(runBtn.attributes('disabled')).toBeUndefined()
  await runBtn.trigger('click')
  await flushPromises()
  const dlg = w.findComponent({ name: 'RunDialog' })
  expect(dlg.exists()).toBe(true)
  return dlg
}

beforeEach(() => {
  mockRoute.query = {}
  routerMock.push.mockReset()
  routerMock.replace.mockClear()
  vi.restoreAllMocks()
  vi.spyOn(api, 'listDataSets').mockResolvedValue([])
  vi.spyOn(api, 'listRunSchemes').mockResolvedValue([DEFAULT_SCHEME, SCHEME_B])
  vi.spyOn(api, 'createRunScheme').mockResolvedValue(
    { ...SCHEME_B, schemeId: 'rs-new', name: '回归集' } as any)
})

describe('CaseComposer — RunDialog v2 对接(阶段③)', () => {
  it('打开弹窗装配:schemes 直连 listRunSchemes(V2 default 置顶)+ serviceRows 并集;overlay 已退役', async () => {
    const w = await mountComposerWithDraft()
    const dlg = await openRunDialog(w)

    expect(api.listRunSchemes).toHaveBeenCalledWith('sc-demo')
    expect(dlg.props('schemes')).toEqual([DEFAULT_SCHEME, SCHEME_B])
    expect(dlg.props('initialSchemeId')).toBeNull()        // 非深链入口
    // 方案/绑定行装配:steps 引用未声明的 service → declaredUrl null
    //(RunDialog 标红可救燃)
    expect(dlg.props('serviceRows')).toEqual([
      { service: 'fin-service', declaredUrl: null },
    ])
    w.unmount()
  })

  it('onRunConfirm 转发 serviceBindings + 溯源两键,无 env、不含退役键', async () => {
    const runScenario = vi.fn().mockResolvedValue({ runId: 'r-1', executionId: 1 })
    vi.spyOn(api, 'runScenario').mockImplementation(runScenario)
    const w = await mountComposerWithDraft()
    const dlg = await openRunDialog(w)

    // 默认方案态绑定行平铺(不折叠),select 直接可寻址
    await dlg.find('.rd-bind-user').setValue('qa1')
    await dlg.find('[data-testid="run-confirm"]').trigger('click')
    await flushPromises()

    expect(runScenario).toHaveBeenCalledTimes(1)
    const body = runScenario.mock.calls[0][0]
    expect(body.scenarioId).toBe('sc-demo')
    expect(body.schemeId).toBe('rs-dft')                  // 溯源:默认方案两态都带
    expect(body.schemeName).toBe('默认方案')
    expect('env' in body).toBe(false)
    expect(body.serviceBindings).toEqual({ 'fin-service': { authAlias: 'qa1' } })
    expect('prefix' in body || 'mergePolicy' in body || 'auths' in body
      || 'injectCredentials' in body).toBe(false)
    w.unmount()
  })

  it('stepTo=0 原样上送(0 是合法 halt 索引,不被 falsy 过滤)', async () => {
    const runScenario = vi.fn().mockResolvedValue({ runId: 'r-0', executionId: 2 })
    vi.spyOn(api, 'runScenario').mockImplementation(runScenario)
    const w = await mountComposerWithDraft()
    const dlg = await openRunDialog(w)

    // stepCount=1:下拉含「运行全部(null)」与「第 1 步后停止(0)」
    await dlg.find('.adv-select').setValue('0')
    await dlg.find('[data-testid="run-confirm"]').trigger('click')
    await flushPromises()

    const body = runScenario.mock.calls[0][0]
    expect(body.stepTo).toBe(0)
    w.unmount()
  })

  it('契约面在途 → 契约依赖条目不进 deadEntryIds;落定后收窄判死(与 RunPanelHost 同款掩空)', async () => {
    // deadEntryIds 是 RunDialog v2 自建方案失效判定的输入:契约未回填时
    // 不得把「尚未判定」当「判死」(否则锚定该条目的方案误报失效)。
    // 本页 draft 通常先就绪,但首访/慢 plate 下 /full 仍在飞 — 信号必须照样送达。
    const { _resetEndpointFullCacheForTest } = await import('@/composables/useEndpointFull')
    _resetEndpointFullCacheForTest()
    const sc = sampleScenario()
    ;(sc.steps[0] as { api: Record<string, unknown> }).api = {
      service: 'fin-service', method: 'POST', path: '/x',
      view_hints: { endpoint_id: 'ep-cc' },
    }
    vi.spyOn(api, 'getScenario').mockResolvedValue(sc)
    // 在途面 = 「被条目引用到的端点」(useInjectableSurface 的唯一消费面):
    // 无条目引用则该端点不影响任何死判定,也就无所谓在途 —— 锚一条契约
    // 依赖条目(路径 body 里没有,只能靠声明面活)把 ep-cc 带进判定面。
    vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({
      assertion_registry: { entries: [
        { id: 'inj-carry', name: 'carry 偏离',
          path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_x' }, value: 1, asserts: [] },
      ] },
    } as any)
    let resolveFull!: (v: unknown) => void
    vi.spyOn(api, 'getFullEndpoint')
      .mockReturnValue(new Promise((res) => { resolveFull = res }) as any)

    const w = mountPage()
    await flushPromises()
    const dlg = await openRunDialog(w)
    expect(api.getFullEndpoint).toHaveBeenCalledWith('ep-cc')
    // 在途:契约依赖条目不判死(掩空决策上移到宿主 —— deadEntryIds 里没有它)
    expect(dlg.props('deadEntryIds')).not.toContain('inj-carry')
    resolveFull({ id: 'ep-cc', request: { declarations: [] } })
    await flushPromises()
    expect(dlg.props('deadEntryIds')).toContain('inj-carry')  // 落定后确实判死
    w.unmount()
  })

  it('saveAsScheme → createRunScheme POST + 重取 listRunSchemes 整表替换', async () => {
    const created: SchemeV2 = { ...SCHEME_B, schemeId: 'rs-new', name: '回归集' }
    vi.mocked(api.listRunSchemes)
      .mockResolvedValueOnce([DEFAULT_SCHEME, SCHEME_B])
      .mockResolvedValueOnce([DEFAULT_SCHEME, SCHEME_B, created])
    vi.mocked(api.createRunScheme).mockResolvedValue(created)
    const w = await mountComposerWithDraft()
    const dlg = await openRunDialog(w)

    await dlg.find('[data-testid="scheme-name-input"]').setValue('回归集')
    await dlg.find('[data-testid="save-as-scheme"]').trigger('click')
    await flushPromises()

    expect(api.createRunScheme).toHaveBeenCalledTimes(1)
    expect(api.createRunScheme).toHaveBeenCalledWith('sc-demo',
      expect.objectContaining({ name: '回归集', dataSetSelection: [] }))
    // 另存成功后重取(整表替换 → RunDialog 收到含新方案的 V2 列表)
    expect(api.listRunSchemes).toHaveBeenCalledTimes(2)
    expect(dlg.props('schemes')).toEqual([DEFAULT_SCHEME, SCHEME_B, created])
    w.unmount()
  })

  it('深链 ?runScheme=rs-002 → 自动打开运行弹窗并预选该方案,query 即清', async () => {
    mockRoute.query = { runScheme: 'rs-002' }
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario())
    // 深链块在 loadScenario 完成后执行 — draft 必须落定(真实 axios 会挂起
    // 整个 onMounted 链,深链永不触发)。
    vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({
      assertion_registry: { entries: [] },
    } as any)
    const w = mountPage()
    await flushPromises()

    const dlg = w.findComponent({ name: 'RunDialog' })
    expect(dlg.exists()).toBe(true)                          // 深链自动开窗(无需点「运行」)
    expect(dlg.props('initialSchemeId')).toBe('rs-002')      // 预选传入
    // schemes 到达后 watch 重跑 → 预选落位(非默认 chip active)
    expect(dlg.find('[data-testid="scheme-chip-rs-002"]').classes()).toContain('active')
    // 读取后清 query(防刷新重复弹)
    expect(routerMock.replace).toHaveBeenCalledWith(expect.objectContaining({
      query: expect.objectContaining({ runScheme: undefined }),
    }))
    w.unmount()
  })
})

describe('CaseComposer — 契约降级(阶段二 Task 8 → 阶段③ v2 消费面)', () => {
  afterEach(() => { _resetEndpointFullCacheForTest() })

  it('降级 → 从严判定:只被契约托着的条目进 deadEntryIds(锚定方案判失效)', async () => {
    // 失败也是答案:声明面退回 body 面 ⇒ 此刻 path-unresolvable 即真死,
    // 锚定该条目的自建方案在运行弹层里判「配置已失效 — 不可运行」。
    _resetEndpointFullCacheForTest()
    const sc = sampleScenario()
    sc.steps = [{
      kind: 'step', description: 's',
      api: {
        kind: 'api', service: 'fin-service', method: 'POST', path: '/x',
        headers: {}, view_hints: { endpoint_id: 'ep-cp' },
      },
      request: { kind: 'request', body: {} }, strategy: [],
    }] as Scenario['steps']
    vi.spyOn(api, 'getScenario').mockResolvedValue(sc)
    vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({
      assertion_registry: { entries: [
        { id: 'inj-c', name: '契约依赖',
          path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_x' }, value: 1, asserts: [] }] },
    } as any)
    vi.spyOn(api, 'getFullEndpoint').mockRejectedValue(new Error('plate down'))

    const w = mountPage()
    await flushPromises()
    const dlg = await openRunDialog(w)
    expect(dlg.props('deadEntryIds')).toEqual(['inj-c'])    // 从严判定 ⇒ 锚定方案不可跑
    w.unmount()
  })
})
