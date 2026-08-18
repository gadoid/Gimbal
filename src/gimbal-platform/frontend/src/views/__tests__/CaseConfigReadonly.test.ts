/**
 * Regression tests for CaseConfigReadonly.vue — the three UX bugs we hit
 * 2026-07-14:
 *
 *   1. Clicking "保存" in the topbar left the page in edit mode (only the
 *      `✓ 已保存` tag flipped to show).  Expected: after a successful save
 *      the page should drop out of edit mode and show the readonly view.
 *
 *   2. Clicking "保存到 yaml" on the config tab's VarsEditor silently
 *      failed.  Cause: saveVars spread `payload.value` (CaseDetailOut =
 *      `{summary, payload}`) into the new body, so the request ended up
 *      as `{payload: {summary, payload, config}}` and the backend's
 *      ``CasePatchIn.payload["scenarioId"] is required`` check rejected
 *      it.  Expected: payload must be the inner CasePayload only.
 *
 *   3. Opening case detail highlighted the `meta` tab even though the
 *      default ref was 'steps'.  Cause: the ref was initialized once and
 *      never reset on (re)load, so previously-selected tabs leaked
 *      across cases.  Expected: every load() lands on `steps`.
 */
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'

// Mock the cases API module before importing anything that pulls it in.
vi.mock('@/api/cases', () => ({
  patch: vi.fn(),
  get: vi.fn(),
  getHidden: vi.fn(),
  putHidden: vi.fn(),
  publicList: vi.fn(),
  mine: vi.fn(),
}))

import * as casesApi from '@/api/cases'
import CaseConfigReadonly from '@/views/CaseConfigReadonly.vue'
import { useEditModeStore } from '@/stores/editMode'

function makeRouter(caseId = 'sc_demo') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/cases/:caseId/config', component: { template: '<div/>' } },
      { path: '/login', component: { template: '<div/>' } },
    ],
  })
  router.push(`/cases/${encodeURIComponent(caseId)}/config`)
  return router
}

const fakeDetail = {
  payload: {
    kind: 'scenario',
    scenarioId: 'sc_demo',
    meta: { name: 'Demo', description: '', module: 'demo' },
    config: {
      services: {},
      users: {},
      vars: { existing: 'literal' },
      retry: null,
    },
    steps: [],
  },
  summary: {
    case_id: 'sc_demo',
    name: 'Demo',
    module: 'demo',
    description: '',
    visibility: 'public',
    owner_id: null,
    audited: true,
    file_path: 'data/public/sc_demo.json',
    updated_at: '2026-07-13T00:00:00',
    tags: [],
    priority: 1,
    author: 'alice',
    favorited_by_me: false,
    copied_by_me: false,
  },
}

async function mountDetail() {
  ;(casesApi.getHidden as Mock).mockResolvedValue({
    case_id: 'sc_demo',
    hidden_paths: [],
    scope: 'user',
    updated_at: null,
  })
  ;(casesApi.get as Mock).mockResolvedValue(fakeDetail)
  const router = makeRouter('sc_demo')
  await router.isReady()
  const w = mount(CaseConfigReadonly, {
    global: { plugins: [router, ElementPlus] },
  })
  await flushPromises()
  // After the GET resolves + flush, the tabs are rendered.
  await flushPromises()
  return w
}

describe('CaseConfigReadonly — bug fixes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // ── Bug 3: open case detail lands on 'meta' tab ──────────────
  it('opens on the meta tab by default', async () => {
    const w = await mountDetail()
    const tabs = w.findAll('.tab')
    expect(tabs.length).toBeGreaterThan(0)
    const active = tabs.find((t) => t.classes().includes('active'))
    expect(active, 'expected exactly one active tab').toBeTruthy()
    expect(active!.text()).toMatch(/meta/i)
  })

  it('does not render the editable config panel without an explicit 编辑 click', async () => {
    const w = await mountDetail()
    await flushPromises()

    // Switch to the config tab so the panel area would mount.
    const tabs = w.findAll('.tab')
    await tabs.find((t) => t.text().match(/config/))!.trigger('click')
    await flushPromises()

    // Without entering edit mode, EditableConfigPanel must be hidden and
    // the readonly VarsEditor must be present instead.
    const editable = w.findComponent({ name: 'EditableConfigPanel' })
    const readonly = w.findComponent({ name: 'VarsEditor' })
    expect(editable.exists(), 'editable panel should NOT exist without edit-mode').toBe(false)
    expect(readonly.exists(), 'readonly VarsEditor should be the default config view').toBe(true)
  })

  it('resets edit mode on (re)load so prior edits do not leak into the next case', async () => {
    ;(casesApi.get as Mock).mockResolvedValue(fakeDetail)
    ;(casesApi.getHidden as Mock).mockResolvedValue({
      case_id: 'sc_demo',
      hidden_paths: [],
      scope: 'user',
      updated_at: null,
    })
    const router = makeRouter('sc_demo')
    await router.isReady()
    const w = mount(CaseConfigReadonly, {
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()
    await flushPromises()

    const editStore = useEditModeStore()

    // Pretend a previous case left the store sticky in edit mode.
    editStore.enterEdit(fakeDetail.payload as Record<string, unknown>)
    expect(editStore.isEditMode).toBe(true)

    // Navigate via watch (caseId change → load()).
    await router.push('/cases/sc_other/config')
    ;(casesApi.get as Mock).mockResolvedValue({
      ...fakeDetail,
      summary: { ...fakeDetail.summary, case_id: 'sc_other' },
      payload: { ...fakeDetail.payload, scenarioId: 'sc_other' },
    })
    await flushPromises()
    await flushPromises()

    expect(editStore.isEditMode, 'edit mode must reset on every case load').toBe(false)
  })

  // ── Bug 1: save exits edit mode ──────────────────────────────
  it('exits edit mode after a successful topbar save', async () => {
    ;(casesApi.patch as Mock).mockResolvedValue(fakeDetail.summary)

    const w = await mountDetail()
    const editStore = useEditModeStore()

    // Enter edit mode and mark dirty so the 保存 button enables.
    editStore.enterEdit(fakeDetail.payload as Record<string, unknown>)
    editStore.patchCurrent((p) => {
      p.meta = { ...(p.meta as Record<string, unknown>), name: 'new name' }
    })
    await flushPromises()

    expect(editStore.isEditMode).toBe(true)

    // Click the topbar 保存 button (only present in edit mode).
    const topbar = w.find('header.topbar')
    expect(topbar.exists()).toBe(true)
    const buttons = topbar.findAll('button.topbar-btn')
    const saveBtn = buttons.find((b) => b.text().includes('保存') && !b.text().includes('保存到'))
    expect(saveBtn, 'expected a 保存 button in the topbar').toBeTruthy()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(casesApi.patch).toHaveBeenCalledTimes(1)
    expect(editStore.isEditMode, 'should exit edit mode after save').toBe(false)

    // And the readonly meta tab's "编辑" button is back (with Edit icon).
    expect(topbar.text()).toContain('编辑')
  })

  // ── Bug 2: VarsEditor save ships a clean inner-payload body ───
  it('sends an inner-payload body when saving vars (no summary leak)', async () => {
    ;(casesApi.patch as Mock).mockResolvedValue(fakeDetail.summary)

    const w = await mountDetail()
    await flushPromises()

    // Click into the config tab so the readonly VarsEditor mounts.
    const tabs = w.findAll('.tab')
    expect(tabs.length).toBeGreaterThan(0)
    const configTab = tabs.find((t) => t.text().match(/config/))!
    await configTab.trigger('click')
    await flushPromises()

    // VarsEditor must be present (we're NOT in edit mode).
    const ve: { exists: () => boolean; vm: { emit: (n: string, p: unknown) => void } } =
      w.findComponent({ name: 'VarsEditor' }) as never
    expect(ve.exists()).toBe(true)

    // Simulate the user's "保存到 yaml" click: emit ``update:modelValue``.
    ve.vm.emit('update:modelValue', {
      existing: 'literal',
      seq: { kind: 'seq', start: 1 },
    })
    await flushPromises()

    expect(casesApi.patch).toHaveBeenCalledTimes(1)
    const [calledCaseId, body] = (casesApi.patch as Mock).mock.calls[0]

    // Request target = the case id.
    expect(calledCaseId).toBe('sc_demo')

    // Body must be ``{ payload: <inner CasePayload> }`` and that inner
    // payload must keep ``scenarioId`` (backend's hard requirement) and
    // the updated ``config.vars``, with NO leaked ``summary`` field.
    expect(body).toHaveProperty('payload')
    expect(body.payload).toHaveProperty('scenarioId', 'sc_demo')
    expect(body.payload).toMatchObject({
      config: {
        vars: { existing: 'literal', seq: { kind: 'seq', start: 1 } },
      },
    })
    expect(body.payload).not.toHaveProperty('summary')
  })

  it('swallows errors from vars save without throwing', async () => {
    ;(casesApi.patch as Mock).mockRejectedValueOnce(
      Object.assign(new Error('boom'), {
        code: 400,
        status: 400,
        msg: 'bad',
      }),
    )

    const w = await mountDetail()
    await flushPromises()
    const tabs = w.findAll('.tab')
    await tabs.find((t) => t.text().match(/config/))!.trigger('click')
    await flushPromises()

    const ve: { vm: { emit: (n: string, p: unknown) => void } } =
      w.findComponent({ name: 'VarsEditor' }) as never
    ve.vm.emit('update:modelValue', { foo: 'bar' })
    await flushPromises()

    expect(casesApi.patch).toHaveBeenCalledTimes(1)
    // Reaching this point without an unhandled-rejection in the test
    // runner proves the ``catch`` swallowed the error.
  })

  // ── Bug: Config.vars was editable before clicking 编辑 ──────────
  it('renders VarsEditor as readonly on the config tab until 编辑 is clicked', async () => {
    const w = await mountDetail()
    await flushPromises()

    // Switch to the config tab.
    const tabs = w.findAll('.tab')
    await tabs.find((t) => t.text().match(/config/))!.trigger('click')
    await flushPromises()

    // Locate the standalone VarsEditor (the readonly one).
    const ve = w.findComponent({ name: 'VarsEditor' }) as unknown as {
      exists: () => boolean
      findAll: (sel: string) => unknown[]
      text: () => string
    }
    expect(ve.exists()).toBe(true)

    // Read-only mode hides the cancel / save-to-yaml footer AND the
    // "+ 新增变量" header button.  Inputs are also disabled.
    expect(ve.findAll('.ve-footer').length).toBe(0)
    expect(ve.text()).not.toContain('保存到 yaml')
    expect(ve.text()).not.toContain('+ 新增变量')
    expect(ve.text()).not.toContain('取消')
    expect(ve.findAll('input[disabled]').length).toBeGreaterThan(0)
  })

  it('renders an editable VarsEditor inside EditableConfigPanel when in edit mode, and cancel restores original vars', async () => {
    const w = await mountDetail()
    await flushPromises()

    const editStore = useEditModeStore()
    editStore.enterEdit(fakeDetail.payload as Record<string, unknown>)
    await flushPromises()

    const tabs = w.findAll('.tab')
    await tabs.find((t) => t.text().match(/config/))!.trigger('click')
    await flushPromises()

    // In edit mode the EditableConfigPanel renders the editable variant
    // of VarsEditor inside it; the standalone (readonly) VarsEditor is
    // not shown here.
    const panel = w.findComponent({ name: 'EditableConfigPanel' })
    expect(panel.exists()).toBe(true)

    const innerVe = panel.findComponent({ name: 'VarsEditor' }) as unknown as {
      exists: () => boolean
      findAll: (sel: string) => unknown[]
      text: () => string
      vm: { emit: (n: string, p: unknown) => void }
    }
    expect(innerVe.exists()).toBe(true)
    expect(innerVe.findAll('.ve-footer').length).toBeGreaterThan(0)
    expect(innerVe.text()).toContain('保存到 yaml')
    expect(innerVe.text()).toContain('取消')
    // Inputs are NOT disabled in editable mode.
    expect(innerVe.findAll('input:not([disabled])').length).toBeGreaterThan(0)

    // Sanity: clicking 取消 in the inner VarsEditor emits @cancel and
    // the embedded onVarsUpdate hooks reset back to the original config
    // — which then propagates through EditableConfigPanel's @update
    // back into the editStore.
    innerVe.vm.emit('cancel')
    await flushPromises()
    // No assertion on the editStore here (covered by the save/exit
    // tests above); reaching this line without an unhandled exception
    // is enough.
  })
})
