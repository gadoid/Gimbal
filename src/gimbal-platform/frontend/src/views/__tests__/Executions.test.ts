/**
 * Executions.vue — V3 detail page (counters + recipe, no per-run UI).
 *
 * Verifies that:
 *  1. The four counter cards render from the detail snapshot.
 *  2. The config recipe (config_json) renders as a definition list
 *     (system keys reconciled/counterDrift are surfaced as alerts
 *     instead, recipe keys get Chinese labels).
 *  3. The stepTo pill renders as 1-based "执行到第 N 步".
 *  4. No V1 per-run surface (runs table / log panel / report dialog)
 *     is present.
 *  5. Cancel button: visible for non-terminal (queued/running) rows,
 *     calls cancelExecution then refreshes; hidden once terminal.
 *  6. started_at / finished_at render in the header.
 *  7. (T13) 行级明细已退役(2026-11-12):由报告分组表 + 实时日志/
 *     日志分析承接;?rows=failed 失败数字入口落「报告」tab。
 *     配方标签覆盖新键 serviceBindings/injectedAuths 且保留旧键 prefix。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import Executions from '@/views/Executions.vue'
import ExecutionsList from '@/views/ExecutionsList.vue'
import { getBatchSummary, listExecutions } from '@/api/executions'
import { useExecutionsStore } from '@/stores/executions'
import { cancelExecution, getScenarioSnapshot } from '@/api/executions'
import { previewPlateDraft } from '@/api/scenario-composer'
import type { ScenarioDraft } from '@/types/scenario-composer'
import type { Execution } from '@/api/executions'

vi.mock('@/api/executions', async (importOriginal) => {
  const orig = await importOriginal<typeof import('@/api/executions')>()
  return {
    ...orig,
    cancelExecution: vi.fn().mockResolvedValue({}),
    listExecutions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    // 行级明细已退役(2026-11-12):rows/artifact/events 消费面移至
    // 报告面板与日志分析页,本文件不再 mock。
    // 场景快照导出:默认无快照(存量行形态),快照用例按需覆写。
    getScenarioSnapshot: vi.fn().mockRejectedValue(new Error('no snapshot')),
    // B5 批次横幅:默认 404(无横幅),批次用例按需覆写
    getBatchSummary: vi.fn().mockRejectedValue(new Error('no batch')),
    // B4 报告 tab(默认视图):默认空报告,报告用例按需覆写
    getExecutionReport: vi.fn().mockResolvedValue({
      execution: { id: 1, scenarioId: 'sc_demo', scenarioName: '', status: 'done',
        kind: 'scenario', suiteId: null, batchId: null, startedAt: null,
        finishedAt: null, durationMs: null, totalRuns: 0, passed: 0, failed: 0, skipped: 0 },
      summary: { steps: 0, stepsPassed: 0, stepsFailed: 0, stepsOther: 0,
        assertions: 0, assertionsPassed: 0 },
      groups: [], failure: null, hasStepData: false,
    }),
  }
})

// 快照导出链:plate convert 在 api 层 mock(真实 convertDraftToExecutable
// 逻辑照跑),downloadFile 打点断言文件名与内容。
vi.mock('@/api/scenario-composer', async (importOriginal) => {
  const orig = await importOriginal<typeof import('@/api/scenario-composer')>()
  return {
    ...orig,
    previewPlateDraft: vi.fn().mockResolvedValue({
      ok: true, errors: [], converted: { kind: 'scenario', convertedBy: 'plate' },
    }),
  }
})

vi.mock('@/utils/download', () => ({
  downloadFile: vi.fn(),
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/executions/:id', component: { template: '<div/>' } },
      { path: '/executions', component: { template: '<div/>' } },
    ],
  })
}

const fakeDetail = {
  id: 1,
  scenario_id: 'sc_demo',
  status: 'done' as const,
  total_runs: 4,
  passed: 3,
  failed: 1,
  started_at: null,
  finished_at: null,
  has_scenario_snapshot: true,
  batch_id: null,
  consecutive_failures: 0,
  config: {
    runId: 'run-42',
    scenarioId: 'sc_demo',
    envId: 'env_dev',
    stepTo: 2,
    nRuns: 4,
    parallel: 2,
  },
} satisfies Execution

async function mountPage(id = 1, hash = '#detail') {
  const router = makeRouter()
  router.push(`/executions/${id}${hash}`)
  await router.isReady()
  const wrapper = mount(Executions, {
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

describe('Executions.vue — V3 detail page', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  // ── 实时日志独立 tab 域(2026-11-12 二改:伪 tab/展开收起退役)─────────
  it('实时日志为独立 tab:激活即挂载默认打印,切走即卸载断流(无展开/收起)', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)
    // 面板挂载即自连流 —— 拦截 fetch 免出网(jsdom 无服务;拒绝即走
    // 退避重连路径,卸载后 generation 闸兜底)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    const w = await mountPage()          // #detail 深链 → 明细 tab,日志面板未挂
    expect(w.find('[data-testid="logs-panel-mount"]').exists()).toBe(false)
    // 顺序契约:实时日志 / 执行明细 / 报告
    expect(w.findAll('[data-testid^="tab-"]').map((n) => n.text()))
      .toEqual(['实时日志', '执行明细', '报告'])
    // 激活实时日志 tab → 面板挂载(挂载即 tail,默认打印)
    await w.get('[data-testid="tab-logs"]').trigger('mousedown', { button: 0 })
    await flushPromises()
    expect(w.find('[data-testid="logs-panel-mount"]').exists()).toBe(true)
    // 切回报告 → 卸载断流(§8 连接预算由 tab 生命周期结构化保证)
    await w.get('[data-testid="tab-report"]').trigger('mousedown', { button: 0 })
    await flushPromises()
    expect(w.find('[data-testid="logs-panel-mount"]').exists()).toBe(false)
    // 再切回日志 → 重新挂载打印
    await w.get('[data-testid="tab-logs"]').trigger('mousedown', { button: 0 })
    await flushPromises()
    expect(w.find('[data-testid="logs-panel-mount"]').exists()).toBe(true)
    w.unmount()
    vi.unstubAllGlobals()
  })

  it('#logs 深链直达实时日志 tab', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    const w = await mountPage(1, '#logs')
    expect(w.find('[data-testid="logs-panel-mount"]').exists()).toBe(true)
    w.unmount()
    vi.unstubAllGlobals()
  })

  it('#report 深链直达报告(实时日志非默认时的直达路径)', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)
    const w = await mountPage(1, '#report')
    expect(w.find('[data-testid="exec-report"]').exists()).toBe(true)
    expect(w.find('[data-testid="logs-panel-mount"]').exists()).toBe(false)
    w.unmount()
  })

  it('手动刷新已退役:顶部不再渲染(恢复语义由 pollError 横幅「重新加载」承载)', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)
    const w = await mountPage()
    expect(w.text()).not.toContain('手动刷新')
    w.unmount()
  })

  it('renders counters from the detail snapshot', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)

    const wrapper = await mountPage()

    const values = wrapper.findAll('.counter-value').map((c) => c.text())
    expect(values).toEqual(['4', '3', '1', '0']) // total/passed/failed/未开始
    expect(wrapper.find('h1').text()).toContain('#1')

    wrapper.unmount()
  })

  it('renders the config recipe as a definition list', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)

    const wrapper = await mountPage()

    const recipe = wrapper.find('.recipe')
    expect(recipe.exists()).toBe(true)
    expect(recipe.text()).toContain('run-42')
    expect(recipe.text()).toContain('env_dev')

    wrapper.unmount()
  })

  it('renders the stepTo pill as 1-based step number', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)

    const wrapper = await mountPage()

    expect(wrapper.find('.step-to-pill').text()).toBe('执行到第 3 步')

    wrapper.unmount()
  })

  it('has no V1 per-run surface (runs table / log panel / report dialog)', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)

    const wrapper = await mountPage()

    expect(wrapper.find('.runs-table').exists()).toBe(false)
    expect(wrapper.find('.log-panel').exists()).toBe(false)
    expect(wrapper.find('.report-frame').exists()).toBe(false)
    // 行级明细已退役(2026-11-12):表与四按钮不再渲染
    expect(wrapper.text()).not.toContain('行级明细')
    expect(wrapper.find('.ex-table-row').exists()).toBe(false)

    wrapper.unmount()
  })
})

describe('Executions.vue — P1 detail upgrades', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const runningDetail = {
    ...fakeDetail,
    status: 'running' as const,
    started_at: '2026-08-26T01:02:03',
    finished_at: null,
    cancelable: true,
  } satisfies Execution

  it('running 单显示取消按钮;点击 → cancelExecution + 重新拉详情', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...runningDetail }
    const refetched = { ...runningDetail, status: 'canceled' as const }
    execStore.fetchDetail = vi.fn().mockResolvedValue(refetched)

    const wrapper = await mountPage()
    const btn = wrapper.findAll('button').find((b) => b.text() === '取消')
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()

    expect(cancelExecution).toHaveBeenCalledWith(1)
    expect(execStore.fetchDetail).toHaveBeenCalledWith(1)
    wrapper.unmount()
  })

  it('入站发起的执行显示「入站来源」(令牌 · 身份模式);JWT 执行不显示(webhook v4 §7.1)', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail, token_id: 3, identity_mode: 'personal', token_name: 'nightly',
                         client_ref: 'job-7' }
    const w1 = await mountPage()
    const origin = w1.find('[data-testid="inbound-origin"]')
    expect(origin.exists()).toBe(true)
    expect(origin.text()).toBe('令牌 nightly · 个人模式 · clientRef job-7')
    w1.unmount()
    execStore.detail = { ...fakeDetail }
    const w2 = await mountPage()
    expect(w2.find('[data-testid="inbound-origin"]').exists()).toBe(false)
    w2.unmount()
  })

  it('取消中:running + cancel_requested → 状态显示「取消中」、说明由 cancel_note 给、无取消按钮(单元级取消 P4)', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...runningDetail, cancelable: false, cancel_requested: true,
                         cancel_note: '已请求取消:当前单元跑完后停止,后续单元记为已取消' }
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('取消中')
    expect(wrapper.find('[data-testid="exec-cancel-note"]').exists()).toBe(false)
    const badge = wrapper.find('.status-tag.status-running')
    expect(badge.attributes('title')).toBe('已请求取消:当前单元跑完后停止,后续单元记为已取消')
    expect(wrapper.findAll('button').find((b) => b.text() === '取消')).toBeUndefined()
    wrapper.unmount()
  })

  it('终态 cancelIgnored → 系统告警条解释「点了取消却按真实结果收口」', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail,
                         cancel_note: '已请求取消,但当时所有单元均已启动、没有可停的单元,已按真实结果收口' }
    const wrapper = await mountPage()
    const alert = wrapper.find('[data-testid="exec-cancel-note"]')
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('没有可停的单元')
    wrapper.unmount()
  })

  it('running 但服务端 cancelable=false(graph 链)→ 不显示取消按钮(全量评估 #1)', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...runningDetail, cancelable: false }
    const wrapper = await mountPage()
    expect(wrapper.findAll('button').find((b) => b.text() === '取消')).toBeUndefined()
    wrapper.unmount()
  })

  it('终态单(done)不显示取消按钮', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)

    const wrapper = await mountPage()
    const btn = wrapper.findAll('button').find((b) => b.text() === '取消')
    expect(btn).toBeUndefined()
    wrapper.unmount()
  })

  it('header 渲染 started_at / finished_at', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = {
      ...fakeDetail,
      started_at: '2026-08-26T01:02:03',
      finished_at: '2026-08-26T01:03:04',
    }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)

    const wrapper = await mountPage()
    const p = wrapper.find('[data-testid="exec-meta"]').text()
    expect(p).toContain('01:02:03')
    expect(p).toContain('01:03:04')
    wrapper.unmount()
  })

  it('配方键渲染中文标签;系统键 reconciled/counterDrift 转 alert,不进 dl', async () => {
    const execStore = useExecutionsStore()
    const detail = {
      ...fakeDetail,
      config: {
        ...fakeDetail.config,
        reconciled: { at: '2026-08-26T00:00:00Z', reason: 'backend restarted mid-dispatch' },
        counterDrift: true,
      },
    } as unknown as Execution
    execStore.detail = detail
    execStore.fetchDetail = vi.fn().mockResolvedValue(detail)

    const wrapper = await mountPage()
    const dtTexts = wrapper.findAll('.recipe dt').map((d) => d.text())
    expect(dtTexts).toContain('运行ID')
    expect(dtTexts).toContain('环境')
    // 系统键不进配方 dl,也不再有英文原键
    expect(dtTexts).not.toContain('runId')
    expect(dtTexts).not.toContain('reconciled')
    expect(dtTexts).not.toContain('counterDrift')
    // counterDrift → 警告条;reconciled → 收敛说明条
    const alerts = wrapper.findAll('.sys-alert')   // 迁移后语义类(原 .el-alert)
    const alertText = alerts.map((a) => a.text()).join('\n')
    expect(alertText).toContain('计数器漂移')
    expect(alertText).toContain('重启')
    wrapper.unmount()
  })

  it('第四张计数卡是"未完成"语义(非"未开始")', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)

    const wrapper = await mountPage()
    const labels = wrapper.findAll('.counter-label').map((c) => c.text())
    expect(labels).toContain('未完成')
    expect(labels).not.toContain('未开始')
    wrapper.unmount()
  })
})

describe('Executions.vue — 配方标签迁移(T13 残留面)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('配方 chips:serviceBindings/injectedAuths 显示新标签,旧键 prefix 仍有人读得懂的标签', async () => {
    const execStore = useExecutionsStore()
    // 旧键(prefix)不在 Execution 接口类型里 — 历史记录的 config_json 仍含
    // 这些键,读侧按键驱动渲染,测试用窄转换构造。
    const detail = {
      ...fakeDetail,
      id: 8,
      config: {
        runId: 'run-8',
        scenarioId: 'sc_demo',
        envId: 'env_dev',
        serviceBindings: { 'fin-service': { alias: 'qa1' } },
        injectedAuths: ['qa1'],
        prefix: 'T-1',
      },
    } as unknown as Execution
    execStore.detail = detail
    execStore.fetchDetail = vi.fn().mockResolvedValue(detail)

    const w = await mountPage(8)
    const dtTexts = w.findAll('.recipe dt').map((d) => d.text())
    expect(dtTexts).toContain('服务绑定')        // 新键标签
    expect(dtTexts).toContain('注入凭证')        // 新键标签(injectedAuths)
    expect(dtTexts).toContain('提单号前缀')      // 旧键标签保留(历史记录可读)
    expect(w.text()).not.toContain('[object Object]')  // 对象值序列化可读
    w.unmount()
  })
})

describe('Executions.vue — 执行时场景快照导出', () => {
  // 注意:本文件第一个 describe 用 restoreAllMocks,会把 factory mock 的
  // mockResolvedValue 实现抹掉(单测隔离跑得通、全文件跑挂的那种序)——
  // 与 T13 describe 同款防御:实现一律 beforeEach 重建。
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(previewPlateDraft).mockResolvedValue({
      ok: true, errors: [], converted: { kind: 'scenario', convertedBy: 'plate' },
    })
  })

  // 快照只被透传(端点 → convert),fixture 无需完整 MetaView —
  // 窄转换构造(与上方旧配方键 detail 同款手法)。
  const snapshotDraft = {
    definition: {
      kind: 'scenario', scenarioId: 'sc_demo',
      meta: { scenarioId: 'sc_demo' },
      config: {}, resource: {}, steps: [],
    },
    orchestration: { steps: [], resourceMeta: {} },
  } as unknown as ScenarioDraft

  it('「导出场景」:拉执行时快照 → plate convert → 下载 exec 命名文件', async () => {
    vi.mocked(getScenarioSnapshot).mockResolvedValue(snapshotDraft)

    const execStore = useExecutionsStore()
    const detail7 = { ...fakeDetail, id: 7 } satisfies Execution
    execStore.detail = detail7
    execStore.fetchDetail = vi.fn().mockResolvedValue(detail7)

    const w = await mountPage(7)
    await w.find('[data-testid="exec-export-scenario"]').trigger('click')
    await flushPromises()

    expect(getScenarioSnapshot).toHaveBeenCalledWith(7)
    const { downloadFile } = await import('@/utils/download')
    expect(downloadFile).toHaveBeenCalledTimes(1)
    const [filename, content, mime] = vi.mocked(downloadFile).mock.calls[0]
    expect(filename).toContain('sc_demo-exec7-')
    expect(filename.endsWith('.json')).toBe(true)
    expect(mime).toBe('application/json')
    // 内容 = plate convert 归一化产物(mock converted),含执行时快照的 draft 键
    expect(content).toContain('convertedBy')
    w.unmount()
  })

  it('存量行无快照(has_scenario_snapshot=false)按钮置灰不可点', async () => {
    const execStore = useExecutionsStore()
    const legacy = { ...fakeDetail, id: 9, has_scenario_snapshot: false } satisfies Execution
    execStore.detail = legacy
    execStore.fetchDetail = vi.fn().mockResolvedValue(legacy)

    const w = await mountPage(9)
    const btn = w.find('[data-testid="exec-export-scenario"]')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('disabled')).toBeDefined()
    await btn.trigger('click')
    await flushPromises()
    expect(getScenarioSnapshot).not.toHaveBeenCalled()
    w.unmount()
  })
})

// ── 执行信息文案:标题改名 + 未配置项基线兜底 ──────────────────────
// 契约:① 「执行配方」标题改为「执行信息」;② 未配置项(空数组/空对象/
// null)不再显示 '(空)'/'—',改显示「场景本体」。(行级明细基线虚行
// 的同类兜底随行级明细退役,2026-11-12。)
describe('Executions.vue — 执行信息(标题 + 场景本体)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('标题为「执行信息」;空数组/空对象未配置项显示「场景本体」', async () => {
    const execStore = useExecutionsStore()
    const detail = {
      ...fakeDetail,
      id: 10,
      config: {
        runId: 'run-42',
        scenarioId: 'sc_demo',
        dataSetIds: [],          // 基线执行(D12:空数据集 = 一个隐式空覆盖行)
        serviceBindings: {},     // 无服务绑定
        injectedAuths: [],       // 无凭证注入
        stepTo: 2,
        nRuns: 4,
        parallel: 2,
      },
    } as unknown as Execution
    execStore.detail = detail
    execStore.fetchDetail = vi.fn().mockResolvedValue(detail)

    const w = await mountPage(10)

    expect(w.find('.recipe-title').text()).toBe('执行信息')
    const recipe = w.find('.recipe')
    expect(recipe.text()).toContain('场景本体')
    expect(recipe.text()).not.toContain('(空)')
    expect(recipe.text()).not.toContain('{}')
    w.unmount()
  })
})

describe('批次 4 原型修订项 — 失败数字直达失败用例', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('列表:failed>0 → 红色可点 → 跳详情并带 ?rows=failed;failed=0 纯文本', async () => {
    vi.mocked(listExecutions).mockResolvedValue({ items: [
      { id: 1, scenario_id: 'sc_a', status: 'done', passed: 2, failed: 2, total_runs: 4,
        started_at: '2026-09-17T10:00:00Z', finished_at: '2026-09-17T10:01:00Z' },
      { id: 2, scenario_id: 'sc_b', status: 'done', passed: 3, failed: 0, total_runs: 3,
        started_at: '2026-09-17T11:00:00Z', finished_at: '2026-09-17T11:01:00Z' },
    ] as never, total: 2, page: 1, pageSize: 200, failedTotal: 1 })
    const router = makeRouter()
    router.push('/executions')
    await router.isReady()
    const w = mount(ExecutionsList, { global: { plugins: [router] } })
    await flushPromises()

    // 时间列带日期(修订项另一条:实测已含)
    expect(w.text()).toContain('2026-09-17')

    // 失败计数取信封全口径:当前页两条都是 done(页内数=0),信封
    // failedTotal=1 —— 2026-10-21 修复前这里会显示「失败 0 条」
    expect(w.find('.filter-count').text()).toContain('共 2 条')
    expect(w.find('.filter-count').text()).toContain('失败 1 条')

    const failLink = w.find('[data-testid="exec-failed-1"]')
    expect(failLink.exists()).toBe(true)
    expect(w.find('[data-testid="exec-failed-2"]').exists()).toBe(false)  // 0 失败纯文本
    await failLink.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/executions/1?rows=failed')
    w.unmount()
  })

  it('详情:同路由换执行号(通知连点)→ 停旧轮询重新拉详情', async () => {
    // 2026-10-21 修复:/executions/12 → /executions/13 复用同一路由记录
    // 不重挂载 —— 此前只有 markRead 在发请求,页面纹丝不动。
    const execStore = useExecutionsStore()
    execStore.fetchDetail = vi.fn(async (id: number) => {
      const d = { ...fakeDetail, id } satisfies Execution
      execStore.detail = d
      return d
    })
    const router = makeRouter()
    router.push('/executions/12')
    await router.isReady()
    const w = mount(Executions, { global: { plugins: [router] } })
    await flushPromises()
    expect(execStore.fetchDetail).toHaveBeenCalledWith(12)
    expect(w.find('h1').text()).toContain('#12')

    await router.push('/executions/13')
    await flushPromises()
    expect(execStore.fetchDetail).toHaveBeenCalledWith(13)
    expect(w.find('h1').text()).toContain('#13')
    w.unmount()
  })
})

// ── W21 修订台账:当时修订 vs 重跑将使用,不一致提示 ────────────────
describe('Executions.vue — 修订台账 (W21)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  async function mountLedger(detail: Partial<Execution>) {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail, ...detail } as Execution
    execStore.fetchDetail = vi.fn().mockResolvedValue(execStore.detail)
    const w = await mountPage(1)
    await flushPromises()
    return w
  }

  it('台账行:一致时显示「一致」;当时未钉显示预览徽标', async () => {
    const w = await mountLedger({
      plate_pins: { fin: '1.0#1' },
      current_plate: { fin: '1.0#1' },
      m2_hash: '8bbb8d85ccce23a2fdd82f499a4530cf4ea930ff67574e484225f8f6867713ca',
    })
    const table = w.find('[data-testid="revision-ledger"]')
    expect(table.exists()).toBe(true)
    expect(table.text()).toContain('fin')
    expect(table.text()).toContain('1.0#1')
    expect(table.text()).toContain('一致')
    expect(table.text()).not.toContain('不一致')
    // m2 构建身份短显(12 位;在台账表下方的说明行,不在表内)
    expect(w.text()).toContain('8bbb8d85ccce')
    expect(w.text()).not.toContain('未记录')
  })

  it('不一致:重跑将使用不同修订 → 提示不可对比', async () => {
    const w = await mountLedger({
      plate_pins: { fin: '1.0#1' },
      current_plate: { fin: '1.0#2' },
    })
    const table = w.find('[data-testid="revision-ledger"]')
    expect(table.text()).toContain('不一致')
    expect(table.text()).toContain('重跑结果不可与本次对比')
  })

  it('B12 基线:integration 记录值 vs 声明值字面不等 → 误标「不一致」(预期变更点 b2-10b)', async () => {
    // 批0 特征化(实施计划 v1.1 §2 B12):现状 ledgerRows 逐字比对
    // (thenRev !== nowRev),integration@<标识> ≠ integration → 恒「不一致」。
    // b2-10b 落地(改调 types/plate.ts 记录域判定函数)时,本断言在同一
    // 提交翻转为:不字面比对、展示当时标识 +「第三方实时定义」标注。
    // 趋势签名(useScenarioRuns `${sys}#${pins[sys]}`)只拼接不分类,不受影响。
    const w = await mountLedger({
      plate_pins: { jira: 'integration@3f2a9c' },
      current_plate: { jira: 'integration' },
    })
    const table = w.find('[data-testid="revision-ledger"]')
    // 基线翻转:b2-10b —— integration 记录值不字面比对,标「第三方 · 实时定义」
    expect(table.text()).toContain('第三方 · 实时定义')
    expect(table.text()).not.toContain('不一致')
    expect(table.text()).toContain('integration@3f2a9c')  // 展示当时标识
  })

  it('当时未钉(预览执行)→ 未钉徽标 + m2 未记录;重跑列显示当前声明', async () => {
    const w = await mountLedger({
      plate_pins: null,
      current_plate: { fin: '1.0#1' },
      m2_hash: null,
    })
    const table = w.find('[data-testid="revision-ledger"]')
    expect(table.text()).toContain('未钉 · 预览')
    expect(table.text()).toContain('1.0#1')     // 重跑列 = 场景当前声明
    expect(table.text()).toContain('不一致')    // 预览 → 钉定 = 不可对比
    expect(w.text()).toContain('未记录(历史执行)')
  })

  it('无任何版本信息(老执行)→ 台账区不渲染', async () => {
    const w = await mountLedger({})
    expect(w.find('[data-testid="revision-ledger"]').exists()).toBe(false)
  })
})

describe('Executions.vue — B4 报告 tab', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认视图是「实时日志」(挂载即打印);「报告」「执行明细」按需挂载', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(execStore.detail)
    // 默认落地即挂日志面板(自连流)—— 拦截 fetch 免出网
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    const router = makeRouter()
    router.push('/executions/1')
    await router.isReady()
    const w = mount(Executions, { global: { plugins: [router] }, attachTo: document.body })
    await flushPromises()
    expect(w.find('[data-testid="logs-panel-mount"]').exists()).toBe(true)
    expect(w.find('[data-testid="exec-report"]').exists()).toBe(false)
    expect(w.text()).not.toContain('执行信息')
    // reka Tabs 在 mousedown 上切换
    await w.get('[data-testid="tab-detail"]').trigger('mousedown', { button: 0 })
    await flushPromises()
    expect(w.find('[data-testid="logs-panel-mount"]').exists()).toBe(false)
    expect(w.text()).toContain('执行信息')
    await w.get('[data-testid="tab-report"]').trigger('mousedown', { button: 0 })
    await flushPromises()
    expect(w.find('[data-testid="exec-report"]').exists()).toBe(true)
    w.unmount()
    vi.unstubAllGlobals()
  })

  it('?rows=failed 落「报告」tab(失败聚焦即失败用例清单;行级表已退役)', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail, id: 7 }
    execStore.fetchDetail = vi.fn().mockResolvedValue(execStore.detail)
    const router = makeRouter()
    router.push('/executions/7?rows=failed')
    await router.isReady()
    const w = mount(Executions, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.find('[data-testid="exec-report"]').exists()).toBe(true)
    expect(w.find('[data-testid="logs-panel-mount"]').exists()).toBe(false)
    w.unmount()
  })
})

describe('ExecutionsList — B5 批次汇总横幅', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('?batch_id= 深链:显示批次计数与用时;清除批次后横幅消失', async () => {
    vi.mocked(listExecutions).mockResolvedValue({
      items: [], total: 0, page: 1, pageSize: 10, failedTotal: 0 } as never)
    vi.mocked(getBatchSummary).mockResolvedValue({
      batchId: 'b-1', total: 3, counts: { done: 2, failed: 1 },
      startedAt: '2026-11-06T01:00:00Z', finishedAt: '2026-11-06T01:01:30Z',
      active: false, members: [],
    })
    const router = makeRouter()
    router.push('/executions?batch_id=b-1')
    await router.isReady()
    const w = mount(ExecutionsList, { global: { plugins: [router] } })
    await flushPromises()
    expect(getBatchSummary).toHaveBeenCalledWith('b-1')
    const banner = w.get('[data-testid="exec-batch-banner"]').text()
    expect(banner).toContain('共 3 条')
    expect(banner).toContain('完成 2')
    expect(banner).toContain('失败 1')
    expect(banner).toContain('用时 1m30s')

    await w.get('.batch-clear').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="exec-batch-banner"]').exists()).toBe(false)
    w.unmount()
  })
})
