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
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import Executions from '@/views/Executions.vue'
import { useExecutionsStore } from '@/stores/executions'
import { cancelExecution } from '@/api/executions'
import type { Execution } from '@/api/executions'

vi.mock('@/api/executions', async (importOriginal) => {
  const orig = await importOriginal<typeof import('@/api/executions')>()
  return { ...orig, cancelExecution: vi.fn().mockResolvedValue(undefined) }
})

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
  config: {
    runId: 'run-42',
    scenarioId: 'sc_demo',
    envId: 'env_dev',
    stepTo: 2,
    nRuns: 4,
    parallel: 2,
  },
} satisfies Execution

async function mountPage() {
  const router = makeRouter()
  router.push('/executions/1')
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
