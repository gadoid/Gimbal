/**
 * Executions.vue — focus on the inline log panel behaviour.
 *
 * Verifies that:
 *  1. Clicking the row's "查看日志" button opens the inline panel
 *     (NOT a dialog).
 *  2. Clicking the same button again collapses it.
 *  3. Switching to a different run's button opens that run's panel.
 *  4. The panel is rendered as a sibling of the runs table, not
 *     inside an el-dialog overlay.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import Executions from '@/views/Executions.vue'
import { useExecutionsStore } from '@/stores/executions'
import { useAuthStore } from '@/stores/auth'
import * as executionsApi from '@/api/executions'

// Stub the SSE stream so opening a log doesn't actually hit the backend.
// Returns a terminal ``end`` event on the very first ``next()`` call so
// the drain loop cleanly breaks — avoids the reconnect cascade that
// would otherwise leave pending promises after unmount.  Also stubs
// ``getRunLog`` (the legacy fallback) so the ``finally`` block in
// ``drainStreamInBackground`` returns immediately.
vi.mock('@/api/executions', async (importOriginal) => {
  const actual = await importOriginal<typeof executionsApi>()
  return {
    ...actual,
    openRunLogStream: vi.fn().mockImplementation(async () => ({
      next: vi.fn().mockResolvedValue({ kind: 'end', exit_code: 0 } as never),
      lastSeq: vi.fn().mockReturnValue(0),
      close: vi.fn(),
    })),
    getRunLog: vi.fn().mockResolvedValue(''),
  }
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
  case_id: 'demo-case',
  status: 'done' as const,
  total_runs: 2,
  passed: 1,
  failed: 1,
  started_at: null,
  finished_at: null,
  config: {},
  runs: [
    {
      id: 11,
      idx: 1,
      status: 'passed' as const,
      exit_code: 0,
      report_path: null,
      started_at: null,
      finished_at: null,
      duration_ms: 1200,
    },
    {
      id: 12,
      idx: 2,
      status: 'failed' as const,
      exit_code: 2,
      report_path: null,
      started_at: null,
      finished_at: null,
      duration_ms: 800,
    },
  ],
}

describe('Executions.vue — inline log panel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('opens an inline panel (not a dialog) when "查看日志" is clicked', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = fakeDetail as never
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail as never)

    const auth = useAuthStore()
    auth.accessToken = 'token'

    const router = makeRouter()
    router.push('/executions/1')
    await router.isReady()

    const wrapper = mount(Executions, {
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()

    // Before click: no inline panel mounted.
    expect(wrapper.find('.log-panel').exists()).toBe(false)

    // Find the first run's "查看日志" button.  ``el-button`` with link
    // renders as a <button> with the text inside; query by text.
    const buttons = wrapper.findAll('button').filter((b) => b.text().includes('查看日志'))
    expect(buttons.length).toBeGreaterThanOrEqual(2)
    await buttons[0].trigger('click')
    await flushPromises()

    // After click: inline panel appears, NO log dialog overlay.
    expect(wrapper.find('.log-panel').exists()).toBe(true)
    expect(wrapper.find('.el-dialog__wrapper').exists()).toBe(false)

    wrapper.unmount()
  })

  it('collapses the panel when the same run button is clicked twice', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = fakeDetail as never
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail as never)

    const auth = useAuthStore()
    auth.accessToken = 'token'

    const router = makeRouter()
    router.push('/executions/1')
    await router.isReady()

    const wrapper = mount(Executions, {
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()

    const buttons = wrapper.findAll('button').filter((b) => b.text().includes('查看日志'))
    await buttons[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('.log-panel').exists()).toBe(true)

    // The button text should now be "收起日志" for that row.
    const buttonAfterOpen = wrapper
      .findAll('button')
      .filter((b) => b.text().includes('收起日志'))
    expect(buttonAfterOpen.length).toBeGreaterThanOrEqual(1)

    // Click again → collapse.
    await buttonAfterOpen[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('.log-panel').exists()).toBe(false)

    wrapper.unmount()
  })

  it('switches the panel to a different run when its button is clicked', async () => {
    const execStore = useExecutionsStore()
    execStore.detail = fakeDetail as never
    execStore.fetchDetail = vi.fn().mockResolvedValue(fakeDetail as never)

    const auth = useAuthStore()
    auth.accessToken = 'token'

    const router = makeRouter()
    router.push('/executions/1')
    await router.isReady()

    const wrapper = mount(Executions, {
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()

    const openButtons = wrapper.findAll('button').filter((b) => b.text().includes('查看日志'))
    // Click run 1's button.
    await openButtons[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('.log-panel-id').text()).toContain('run #1')

    // Click run 2's button — the panel should now show run #2.
    const stillOpen = wrapper
      .findAll('button')
      .filter((b) => b.text().includes('查看日志'))
    await stillOpen[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('.log-panel-id').text()).toContain('run #2')

    wrapper.unmount()
  })
})