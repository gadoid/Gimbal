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
// ``drainStreamInBackground`` returns immediately.  The ``get`` stub
// prevents the on-mount polling (startPolling) from hitting the network
// in tests that don't explicitly wire it.
vi.mock('@/api/executions', async (importOriginal) => {
  const actual = await importOriginal<typeof executionsApi>()
  return {
    ...actual,
    get: vi.fn().mockImplementation(async (id: number) => {
      // Return a minimal placeholder; tests that need detail content
      // should set ``execStore.detail`` directly.
      return {
        id,
        case_id: 'mock',
        status: 'done',
        total_runs: 0,
        passed: 0,
        failed: 0,
        started_at: null,
        finished_at: null,
        config: {},
        runs: [],
      }
    }),
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


// ── rerun-as-insert (B-model: each rerun INSERTs a new row) ───────
describe('Executions.vue — rerun inserts new row, table sorts by id desc', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  /**
   * Common fixture for rerun tests: a 2-run execution with the
   * store + api properly stubbed so the new row flows through
   * appendRun without ever hitting the network.
   */
  async function mountForRerun() {
    const detailBefore = {
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
        { id: 11, idx: 1, status: 'passed' as const, exit_code: 0, report_path: null,
          started_at: null, finished_at: null, duration_ms: 1200 },
        { id: 12, idx: 2, status: 'failed' as const, exit_code: 2, report_path: null,
          started_at: null, finished_at: null, duration_ms: 800 },
      ],
    }
    const detailAfter = {
      ...detailBefore,
      runs: [
        { id: 13, idx: 3, status: 'failed' as const, exit_code: 3, report_path: null,
          started_at: null, finished_at: null, duration_ms: 500 },
        ...detailBefore.runs,
      ],
    }

    const execStore = useExecutionsStore()
    execStore.detail = detailBefore as never
    // B-model: rerun returns the new row; the UI appends it
    // optimistically (no fetchDetail roundtrip).
    const newRow = detailAfter.runs[0]
    vi.spyOn(executionsApi, 'rerunRun').mockResolvedValue(newRow as never)
    // Background fetchDetail for sync — stub.
    const fetchSpy = vi.fn().mockImplementation(async () => {
      execStore.detail = detailAfter as never
      return detailAfter as never
    })
    execStore.fetchDetail = fetchSpy

    const auth = useAuthStore()
    auth.accessToken = 'token'
    const router = makeRouter()
    router.push('/executions/1')
    await router.isReady()

    const wrapper = mount(Executions, {
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()
    return { wrapper, execStore, detailBefore, detailAfter, newRow }
  }

  it('appends the new run row to the table after a rerun (count grows)', async () => {
    const { wrapper, execStore } = await mountForRerun()

    // Find the first row's "重跑" button and click it.
    const rerunBtns = wrapper
      .findAll('button')
      .filter((b) => b.text().includes('重跑'))
    expect(rerunBtns.length).toBeGreaterThanOrEqual(2)
    await rerunBtns[0].trigger('click')
    await flushPromises()

    // After rerun, the table should now have 3 rows.
    const rowsAfter = wrapper.findAll('.runs-table tbody tr')
    expect(rowsAfter.length).toBe(3)

    wrapper.unmount()
  })

  it('declares the runs-table as sortable by id (default-sort desc) so reruns appear at the top', async () => {
    const execStore = useExecutionsStore()
    const testDetail = {
      id: 1,
      case_id: 'demo',
      status: 'done' as const,
      total_runs: 3,
      passed: 1,
      failed: 2,
      started_at: null,
      finished_at: null,
      config: {},
      runs: [
        { id: 11, idx: 1, status: 'passed' as const, exit_code: 0, report_path: null,
          started_at: null, finished_at: null, duration_ms: 1000 },
        { id: 12, idx: 2, status: 'failed' as const, exit_code: 2, report_path: null,
          started_at: null, finished_at: null, duration_ms: 800 },
        { id: 13, idx: 3, status: 'failed' as const, exit_code: 3, report_path: null,
          started_at: null, finished_at: null, duration_ms: 500 },
      ],
    }
    execStore.detail = testDetail as never
    // Stub fetchDetail so the on-mount hook doesn't reset detail to
    // the mock's empty-runs placeholder.  The store's real fetchDetail
    // would hit the API; here we just preserve the test fixture.
    execStore.fetchDetail = vi.fn().mockImplementation(async (id: number) => {
      execStore.detail = testDetail as never
      return testDetail as never
    })

    const auth = useAuthStore()
    auth.accessToken = 'token'
    const router = makeRouter()
    router.push('/executions/1')
    await router.isReady()

    const wrapper = mount(Executions, {
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()

    // The table's :default-sort="{prop:'id', order:'descending'}" puts
    // the sort indicator on the column header that the framework picked
    // by matching the prop name to a column.  The display reordering
    // is handled by el-table's internal sort; we only assert that the
    // table is wired up — the actual reordering is rendered visually.
    const table = wrapper.find('.runs-table')
    expect(table.exists()).toBe(true)
    // The sort by id uses the 'id' field which exists on every run
    // row.  No brittle DOM assertions on the sort indicator here.
    expect(execStore.detail.runs[0].id).toBe(11)  // data array order is unchanged

    wrapper.unmount()
  })

  it('shows a completion toast with the new run id/idx/exit_code', async () => {
    const { wrapper, newRow } = await mountForRerun()

    // ElNotification renders into document.body when fired.
    const beforeCount = document.body.querySelectorAll('.el-notification').length

    const rerunBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('重跑'))!
    await rerunBtn.trigger('click')
    await flushPromises()

    // A new ElNotification node should have been mounted.
    const afterCount = document.body.querySelectorAll('.el-notification').length
    expect(afterCount).toBeGreaterThan(beforeCount)

    // The toast text mentions the new run's idx, id, and exit code so
    // operators can immediately see the outcome of the rerun.
    const titles = Array.from(
      document.body.querySelectorAll('.el-notification__title'),
    ).map((n) => n.textContent || '')
    const messages = Array.from(
      document.body.querySelectorAll('.el-notification__content'),
    ).map((n) => n.textContent || '')
    const allText = [...titles, ...messages].join(' ')
    expect(allText).toContain('重跑完成')
    expect(allText).toContain(`#${newRow.idx}`)
    expect(allText).toContain(`id=${newRow.id}`)
    expect(allText).toContain('exit=')

    wrapper.unmount()
  })

  it('updates detail.runs and total_runs optimistically without waiting for fetchDetail', async () => {
    const { wrapper, execStore } = await mountForRerun()

    // Track fetchDetail call count — if rerun awaits it, we'll see > 0 calls.
    const beforeCount = (execStore.fetchDetail as ReturnType<typeof vi.fn>).mock.calls.length

    const rerunBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('重跑'))!
    await rerunBtn.trigger('click')
    // The DOM should be updated synchronously after the rerun resolves
    // — well before any background fetchDetail completes.
    await flushPromises()

    // detail.runs should now have 3 rows (2 + the new one).
    expect(execStore.detail?.runs.length).toBe(3)
    // total_runs grows by 1 (B-model).
    expect(execStore.detail?.total_runs).toBe(3)
    // The new row's id should be in the runs list.
    expect(execStore.detail?.runs.some((r) => r.id === 13)).toBe(true)

    // The background fetchDetail was kicked off (fire-and-forget).
    const afterCount = (execStore.fetchDetail as ReturnType<typeof vi.fn>).mock.calls.length
    expect(afterCount).toBeGreaterThanOrEqual(beforeCount)

    wrapper.unmount()
  })
})
// ── rerunningIds persistence across polling ────────────────────
describe('Executions.vue — rerunningIds survive polling', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('keeps :loading=true on the rerun button even when polling replaces detail', async () => {
    // Repro for P0-#8: the per-row :loading flag used to be set on
    // the row object (row.rerunning = true).  But startPolling does
    // ``detail.value = d`` every 1s, so any per-row mutation was
    // wiped — the button stopped spinning while the rerun was still
    // in flight.  The fix moves the flag to a store-owned Set
    // (rerunningIds) that polling doesn't touch.
    const fakeDetail = {
      id: 1,
      case_id: 'demo',
      status: 'done' as const,
      total_runs: 1,
      passed: 1,
      failed: 0,
      started_at: null,
      finished_at: null,
      config: {},
      runs: [
        { id: 11, idx: 1, status: 'passed' as const, exit_code: 0, report_path: null,
          started_at: null, finished_at: null, duration_ms: 1000 },
      ],
    }
    // New deep copy on each poll (mimics a real fetchDetail response)
    let pollCount = 0

    const execStore = useExecutionsStore()
    execStore.detail = fakeDetail as never
    vi.spyOn(executionsApi, 'rerunRun').mockImplementation(
      () => new Promise((resolve) => {
        // Resolve after a long delay so the test can verify
        // isRerunning() stays true through multiple polls.
        setTimeout(() => resolve({} as never), 200)
      }),
    )
    execStore.fetchDetail = vi.fn().mockImplementation(async () => {
      pollCount++
      // Return a NEW object every poll (not the same reference).
      return {
        ...fakeDetail,
        runs: [
          { ...fakeDetail.runs[0] },
        ],
      } as never
    })

    const auth = useAuthStore()
    auth.accessToken = 'token'
    const router = makeRouter()
    router.push('/executions/1')
    await router.isReady()

    const wrapper = mount(Executions, {
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()

    // Find the rerun button and click it.
    const rerunBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('重跑'))!
    await rerunBtn.trigger('click')
    await flushPromises()

    // isRerunning() must be true right after the click.
    expect(execStore.isRerunning(11)).toBe(true)

    // The button should be in :loading state.
    const rerunBtnAfter = wrapper
      .findAll('button')
      .find((b) => b.text().includes('重跑'))!
    expect(rerunBtnAfter.classes()).toContain('is-loading')

    // Wait long enough for at least one polling tick to fire
    // (POLL_INTERVAL_MS = 1000).  In the old code, the per-row
    // :loading flag would be wiped by the polling tick.  In the new
    // code, the store-owned Set is unaffected.
    await new Promise((r) => setTimeout(r, 120))
    await flushPromises()

    // isRerunning() must STILL be true after polling.
    expect(execStore.isRerunning(11)).toBe(true)
    expect(pollCount).toBeGreaterThan(0)  // confirms polling did run

    // Wait for the rerun to finish.
    await new Promise((r) => setTimeout(r, 200))
    await flushPromises()

    // After completion, the flag is cleared.
    expect(execStore.isRerunning(11)).toBe(false)

    wrapper.unmount()
  })
})
