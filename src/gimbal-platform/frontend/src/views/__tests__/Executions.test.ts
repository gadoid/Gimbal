/**
 * Executions.vue — V3 detail page (counters + recipe, no per-run UI).
 *
 * Verifies that:
 *  1. The four counter cards render from the detail snapshot.
 *  2. The config recipe (config_json) renders as a definition list.
 *  3. The stepTo pill renders as 1-based "执行到第 N 步".
 *  4. No V1 per-run surface (runs table / log panel / report dialog)
 *     is present.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import Executions from '@/views/Executions.vue'
import { useExecutionsStore } from '@/stores/executions'
import type { Execution } from '@/api/executions'

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
