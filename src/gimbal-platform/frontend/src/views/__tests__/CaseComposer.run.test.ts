/**
 * CaseComposer — Task 12 RunDialog 对接:
 * - openRunDialog 装配 lastRunOverlay(GET /executions?limit=1 只取 overlay
 *   三字段:envId / dataSetIds / serviceBindings,base_config 其余键不回填);
 * - confirm 新签名:serviceBindings 原样上送,退役键(prefix/mergePolicy/
 *   auths/injectCredentials)不出现在 RunRequest;
 * - stepTo=0 合法(0-based halt 索引,首步后停)不被 falsy 过滤;
 * - saveScheme → putRunSchemes 整表替换 + 草稿 store 回填。
 *
 * 建件/mock 结构抄 CaseComposer.poolrail.test.ts(vi.hoisted + 构造器 impl
 * 工厂 mock 防 vi.restoreAllMocks 清实现;scenario-composer 走 spyOn)。
 * 交互走真实 DOM(顶栏运行按钮 + RunDialog 控件),弹层 Teleport 以
 * stubs: { teleport: true } 收回到 wrapper 内(RunDialog 兄弟测试同款)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import CaseComposer from '@/views/CaseComposer.vue'
import * as api from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'
import { useScenarioDraftStore } from '@/stores/scenario-draft'

const mockRoute: { params: { scenarioId: string }; query: Record<string, string> } = {
  params: { scenarioId: 'sc-demo' },
  query: {},
}
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mockRoute,
    useRouter: () => ({ push: vi.fn(), replace: vi.fn().mockResolvedValue(undefined) }),
  }
})

// vi.hoisted:vi.mock 工厂提升到文件顶部,引用必须先行提升。config 里掺
// 杂 overlay 三字段以外的键(runId/nRuns/parallel/stepTo/injectedAuths),
// 证明装配只取三字段、base_config 不整体回填。
const LAST_RUN = vi.hoisted(() => ({
  id: 7,
  config: {
    envId: 'dev',
    dataSetIds: ['ds-1'],
    serviceBindings: { 'fin-service': { authAlias: 'qa1' } },
    runId: 'run-7',
    scenarioId: 'sc-demo',
    injectedAuths: ['qa1'],
    stepTo: 2,
    nRuns: 3,
    parallel: 2,
  },
}))
vi.mock('@/api/executions', () => ({
  // 构造器 impl(非 mockResolvedValue):beforeEach 的 vi.restoreAllMocks
  // 会清掉后者、保留前者 — poolrail GEN_ENTRY 同款坑。
  listExecutions: vi.fn(() => Promise.resolve({ items: [LAST_RUN], total: 1 })),
}))
vi.mock('@/api/constants', () => ({
  list: vi.fn(() => Promise.resolve([])),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(() => Promise.resolve([{ alias: 'qa1' }])),
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

/** 建件:getScenario 回样例场景(steps 引用 fin-service),envs 可注入 */
async function mountComposerWithDraft(opts: { envs?: { envId: string; name: string; baseUrl: string }[] } = {}) {
  if (opts.envs) vi.spyOn(api, 'listEnvs').mockResolvedValue(opts.envs)
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
  vi.restoreAllMocks()
  vi.spyOn(api, 'listEnvs').mockResolvedValue([])
  vi.spyOn(api, 'listDataSets').mockResolvedValue([])
})

describe('CaseComposer — RunDialog 对接(Task 12)', () => {
  it('上次运行只回填 overlay 三字段(base_config 其余键不回填)', async () => {
    const w = await mountComposerWithDraft()
    const dlg = await openRunDialog(w)

    expect(dlg.props('lastRunOverlay')).toEqual({
      envId: 'dev', dataSetIds: ['ds-1'],
      serviceBindings: { 'fin-service': { authAlias: 'qa1' } },
    })
    // 方案/服务引用装配:无已存方案;steps 引用的 service 去重上送
    expect(dlg.props('schemes')).toEqual([])
    expect(dlg.props('referencedServices')).toEqual(['fin-service'])
    w.unmount()
  })

  it('onRunConfirm 转发 serviceBindings,不含退役键', async () => {
    const runScenario = vi.fn().mockResolvedValue({ runId: 'r-1', executionId: 1 })
    vi.spyOn(api, 'runScenario').mockImplementation(runScenario)
    const w = await mountComposerWithDraft({
      envs: [{ envId: 'dev', name: 'dev', baseUrl: 'http://dev' }],
    })
    const dlg = await openRunDialog(w)

    // 折叠区默认 v-show 隐藏,select 仍可寻址(RunDialog.auths 同款)
    await dlg.find('.rd-bind-user').setValue('qa1')
    await dlg.find('[data-testid="run-confirm"]').trigger('click')
    await flushPromises()

    expect(runScenario).toHaveBeenCalledTimes(1)
    const body = runScenario.mock.calls[0][0]
    expect(body.scenarioId).toBe('sc-demo')
    expect(body.env).toEqual({ envId: 'dev', name: 'dev', baseUrl: 'http://dev' })
    expect(body.serviceBindings).toEqual({ 'fin-service': { authAlias: 'qa1' } })
    expect('prefix' in body || 'mergePolicy' in body || 'auths' in body
      || 'injectCredentials' in body).toBe(false)
    w.unmount()
  })

  it('stepTo=0 原样上送(0 是合法 halt 索引,不被 falsy 过滤)', async () => {
    const runScenario = vi.fn().mockResolvedValue({ runId: 'r-0', executionId: 2 })
    vi.spyOn(api, 'runScenario').mockImplementation(runScenario)
    const w = await mountComposerWithDraft({
      envs: [{ envId: 'dev', name: 'dev', baseUrl: 'http://dev' }],
    })
    const dlg = await openRunDialog(w)

    // stepCount=1:下拉含「运行全部(null)」与「第 1 步后停止(0)」
    await dlg.find('.adv-select').setValue('0')
    await dlg.find('[data-testid="run-confirm"]').trigger('click')
    await flushPromises()

    const body = runScenario.mock.calls[0][0]
    expect(body.stepTo).toBe(0)
    w.unmount()
  })

  it('saveScheme → putRunSchemes 整表替换 + 草稿 store 回填', async () => {
    const saved = [{ name: '冒烟', envId: 'dev', dataSetIds: [], serviceBindings: {} }]
    const putRunSchemes = vi.fn().mockResolvedValue(saved)
    vi.spyOn(api, 'putRunSchemes').mockImplementation(putRunSchemes)
    const w = await mountComposerWithDraft({
      envs: [{ envId: 'dev', name: 'dev', baseUrl: 'http://dev' }],
    })
    const dlg = await openRunDialog(w)

    await dlg.find('.rd-scheme-name').setValue('冒烟')
    await dlg.find('[data-testid="save-scheme"]').trigger('click')
    await flushPromises()

    expect(putRunSchemes).toHaveBeenCalledTimes(1)
    expect(putRunSchemes).toHaveBeenCalledWith('sc-demo', [expect.objectContaining({ name: '冒烟' })])
    // 落库返回值回填共享草稿(RunDialog schemes prop 数据源)
    const draft = useScenarioDraftStore().draft as unknown as {
      orchestration?: { runSchemes?: unknown[] }
    }
    expect(draft?.orchestration?.runSchemes).toEqual(saved)
    w.unmount()
  })
})
