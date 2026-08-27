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
 *  7. (T13) 行级明细:展开拉取 rows 渲染行级表格,engine-log 工件
 *     按需可读;rows 为空(预部署/认证快速失败)显示空态;
 *     配方标签覆盖新键 serviceBindings/injectedAuths 且保留旧键 prefix。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import Executions from '@/views/Executions.vue'
import { useExecutionsStore } from '@/stores/executions'
import { cancelExecution, getExecutionRows, getCaseArtifact, getScenarioSnapshot } from '@/api/executions'
import { previewPlateDraft } from '@/api/scenario-composer'
import type { ScenarioDraft } from '@/types/scenario-composer'
import type { Execution } from '@/api/executions'

vi.mock('@/api/executions', async (importOriginal) => {
  const orig = await importOriginal<typeof import('@/api/executions')>()
  return {
    ...orig,
    cancelExecution: vi.fn().mockResolvedValue(undefined),
    // T13 行级可观测:rows/artifact 默认空实现,各用例按需 mockResolvedValue。
    getExecutionRows: vi.fn().mockResolvedValue({ items: [] }),
    getCaseArtifact: vi.fn().mockResolvedValue(''),
    // 场景快照导出:默认无快照(存量行形态),快照用例按需覆写。
    getScenarioSnapshot: vi.fn().mockRejectedValue(new Error('no snapshot')),
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
  config: {
    runId: 'run-42',
    scenarioId: 'sc_demo',
    envId: 'env_dev',
    stepTo: 2,
    nRuns: 4,
    parallel: 2,
  },
} satisfies Execution

async function mountPage(id = 1) {
  const router = makeRouter()
  router.push(`/executions/${id}`)
  await router.isReady()
  const wrapper = mount(Executions, {
    global: { plugins: [router, ElementPlus] },
  })
  await flushPromises()
  return wrapper
}

describe('Executions.vue — V3 detail page', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders counters from the detail snapshot', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = { ...fakeDetail }
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail)

    const wrapper = await mountPage()

    const values = wrapper.findAll('.counter-value').map((c) => c.text())
    expect(values).toEqual(['4', '3', '1', '0']) // total/passed/failed/未开始
    expect(wrapper.find('h2').text()).toContain('#1')

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
    const p = wrapper.find('.page-header p').text()
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
    const alerts = wrapper.findAll('.el-alert')
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

describe('Executions.vue — T13 行级明细 + 配方标签迁移', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('行级表格:拉取 rows 并渲染;展开可读 engine-log', async () => {
    vi.mocked(getExecutionRows).mockResolvedValue({ items: [
      { seq: 0, datasetId: null, rowIndex: 0, rep: 0, status: 'passed',
        caseDir: 'case-000-baseline-r0-n0', startedAt: 't1', finishedAt: 't2' },
      { seq: 1, datasetId: 'ds-1', rowIndex: 0, rep: 0, status: 'failed',
        caseDir: 'case-001-ds-1-r0-n0', startedAt: 't1', finishedAt: 't3' } ] })
    vi.mocked(getCaseArtifact).mockResolvedValue('engine says hi')

    const execStore = useExecutionsStore()
    const detail7 = { ...fakeDetail, id: 7 } satisfies Execution
    execStore.detail = detail7
    execStore.fetchDetail = vi.fn().mockResolvedValue(detail7)

    const w = await mountPage(7)
    await w.find('[data-testid="exec-row-7"]').trigger('click')   // 展开执行 7 的行级表格
    await flushPromises()

    expect(getExecutionRows).toHaveBeenCalledWith(7)
    expect(w.findAll('.ex-table-row')).toHaveLength(2)
    expect(w.text()).toContain('ds-1')

    await w.find('[data-testid="row-artifact-1-engine-log"]').trigger('click')
    await flushPromises()
    expect(getCaseArtifact).toHaveBeenCalledWith(7, 'case-001-ds-1-r0-n0', 'engine-log')
    expect(w.text()).toContain('engine says hi')
    w.unmount()
  })

  it('工件可收起:点击引擎日志展开,再点收起,又点重新展开并重拉', async () => {
    vi.mocked(getExecutionRows).mockResolvedValue({ items: [
      { seq: 0, datasetId: null, rowIndex: 0, rep: 0, status: 'passed',
        caseDir: 'case-000-baseline-r0-n0', startedAt: 't1', finishedAt: 't2' } ] })
    vi.mocked(getCaseArtifact).mockResolvedValue('engine says hi')

    const execStore = useExecutionsStore()
    const detail7 = { ...fakeDetail, id: 7 } satisfies Execution
    execStore.detail = detail7
    execStore.fetchDetail = vi.fn().mockResolvedValue(detail7)

    const w = await mountPage(7)
    await w.find('[data-testid="exec-row-7"]').trigger('click')
    await flushPromises()

    const btn = w.find('[data-testid="row-artifact-0-engine-log"]')
    await btn.trigger('click')            // 第一次点:展开
    await flushPromises()
    expect(w.text()).toContain('engine says hi')

    await btn.trigger('click')            // 第二次点:收起
    await flushPromises()
    expect(w.text()).not.toContain('engine says hi')

    await btn.trigger('click')            // 第三次点:重新展开(重拉最新)
    await flushPromises()
    expect(w.text()).toContain('engine says hi')
    // 展开 + 重展各拉一次;收起不拉。
    expect(getCaseArtifact).toHaveBeenCalledTimes(2)
    w.unmount()
  })

  it('工件可收起:步骤明细同样支持展开/收起', async () => {
    vi.mocked(getExecutionRows).mockResolvedValue({ items: [
      { seq: 0, datasetId: null, rowIndex: 0, rep: 0, status: 'passed',
        caseDir: 'case-000-baseline-r0-n0', startedAt: 't1', finishedAt: 't2' } ] })
    vi.mocked(getCaseArtifact).mockResolvedValue('{"launchStatus":"ok"}')

    const execStore = useExecutionsStore()
    const detail7 = { ...fakeDetail, id: 7 } satisfies Execution
    execStore.detail = detail7
    execStore.fetchDetail = vi.fn().mockResolvedValue(detail7)

    const w = await mountPage(7)
    await w.find('[data-testid="exec-row-7"]').trigger('click')
    await flushPromises()

    const btn = w.find('[data-testid="row-artifact-0-result"]')
    await btn.trigger('click')
    await flushPromises()
    expect(w.text()).toContain('launchStatus')

    await btn.trigger('click')
    await flushPromises()
    expect(w.text()).not.toContain('launchStatus')
    w.unmount()
  })

  it('行级数据为空(预部署/认证快速失败)显示空态而非报错', async () => {
    vi.mocked(getExecutionRows).mockResolvedValue({ items: [] })

    const execStore = useExecutionsStore()
    const detail7 = { ...fakeDetail, id: 7 } satisfies Execution
    execStore.detail = detail7
    execStore.fetchDetail = vi.fn().mockResolvedValue(detail7)

    const w = await mountPage(7)
    await w.find('[data-testid="exec-row-7"]').trigger('click')
    await flushPromises()

    expect(w.findAll('.ex-table-row')).toHaveLength(0)
    expect(w.text()).toContain('无行级数据')
    w.unmount()
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
        serviceBindings: { 'fin-service': { authAlias: 'qa1' } },
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
