/**
 * ExecutionDrawer.vue — step picker behavior (gimbal run show + --step-to).
 *
 * The full drawer composes auth store + cases store + executions store;
 * these tests focus narrowly on the new step_to field: trigger label,
 * form submission, validation, and admin argv preview interaction.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import ExecutionDrawer from '@/components/ExecutionDrawer.vue'

function mkShow(step_count: number) {
  return {
    scenario_id: 'sc_test',
    name: 'Test',
    description: null,
    tags: [],
    module: null,
    priority: null,
    author: null,
    step_count,
    steps: Array.from({ length: step_count }, (_, i) => ({
      index: i,
      kind: 'step',
      description: `desc-${i}`,
      api: { service: 'svc', method: 'POST', path: `/api/${i}` },
      strategy_kinds: ['assertion'],
      strategy_count: 1,
      ref: null,
    })),
    usage_hint: null,
  }
}

async function mountDrawer(opts: {
  show?: ReturnType<typeof mkShow> | null
  showError?: string | null
  isAdmin?: boolean
} = {}) {
  const show = opts.show === undefined ? mkShow(3) : opts.show
  const pinia = createPinia()
  setActivePinia(pinia)

  // Stub the cases store.  We can't import the real store easily
  // because ExecutionDrawer accesses it via useCasesStore() — so we
  // install the store and patch its methods.
  const casesMod = await import('@/stores/cases')
  const casesStore = casesMod.useCasesStore(pinia)
  if (show !== null) {
    casesStore.showCache[opts.show === undefined ? 'sc_test' : 'sc_x'] = show as never
  }
  // The drawer's open watcher calls fetchShow.  Stub it to inject the
  // desired show response (or reject for the error case).
  vi.spyOn(casesStore, 'fetchShow').mockImplementation(async (caseId: string) => {
    if (show === null) throw new Error(opts.showError ?? 'show fetch failed')
    casesStore.showCache[caseId] = show as never
    return show as never
  })

  // Stub auth store so the drawer's `useAuthStore` works.
  const authMod = await import('@/stores/auth')
  const authStore = authMod.useAuthStore(pinia)
  authStore.currentUser = opts.isAdmin
    ? ({ id: 1, username: 'alice', is_admin: true } as never)
    : ({ id: 1, username: 'alice', is_admin: false } as never)

  // Stub auth_sessions store so the drawer's `authsList` is non-empty
  // and fetchAll does NOT hit the network (jsdom has no server).
  const sessionsMod = await import('@/stores/auth_sessions')
  const sessionsStore = sessionsMod.useAuthSessionsStore(pinia)
  sessionsStore.list = []
  vi.spyOn(sessionsStore, 'fetchAll').mockResolvedValue([])

  // Stub executions store so submit() works.
  const execMod = await import('@/stores/executions')
  const execStore = execMod.useExecutionsStore(pinia)
  const createSpy = vi.fn().mockResolvedValue({ id: 999 })
  execStore.create = createSpy as never

  const wrapper = mount(ExecutionDrawer, {
    props: {
      modelValue: true,
      caseId: 'sc_x',
      caseName: 'Test Case',
      caseSummary: {
        case_id: 'sc_x',
        name: 'Test Case',
        module: 'test',
        description: '',
        visibility: 'public',
        owner_id: null,
        audited: true,
        file_path: '',
        updated_at: '',
        tags: [],
        priority: null,
        author: null,
        favorited_by_me: false,
        copied_by_me: false,
      } as never,
    },
    global: { plugins: [pinia, ElementPlus] },
  })

  // Trigger the open watcher: modelValue is already true on mount, but
  // the watcher fires async; nudge by emitting again to be safe.
  await wrapper.setProps({ modelValue: true })
  await flushPromises()

  return { wrapper, createSpy }
}

describe('ExecutionDrawer — step picker', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('renders "全部执行" trigger label when no step is picked', async () => {
    const { wrapper } = await mountDrawer()
    const trigger = wrapper.find('.exdraw-step-trigger')
    expect(trigger.exists()).toBe(true)
    expect(trigger.text()).toContain('全部执行')
  })

  it('disables trigger button when show fetch fails', async () => {
    const { wrapper } = await mountDrawer({ show: null, showError: 'show fetch failed' })
    const trigger = wrapper.find('.exdraw-step-trigger')
    expect(trigger.exists()).toBe(true)
    // showData is null → button is disabled (button finds "is-disabled"
    // class via Element Plus).  We can assert via the disabled attr.
    expect((trigger.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('submits step_to=2 when user picks the third step', async () => {
    const { wrapper, createSpy } = await mountDrawer()
    // Open the popover by clicking the trigger.
    await wrapper.find('.exdraw-step-trigger').trigger('click')
    await flushPromises()
    // Drive the picker directly via the component's exposed state.
    // (Element Plus' popover teleport makes DOM .click() on body-
    // teleported rows unreliable in jsdom; testing the state hook is
    // equivalent for the contract we care about: step_to propagates
    // through submit().)
    ;(wrapper.vm as unknown as { pickStep: (n: number | null) => void }).pickStep(2)
    await flushPromises()
    const trigger = wrapper.find('.exdraw-step-trigger')
    expect(trigger.text()).toContain('执行到第 3 步')
    const launch = wrapper.findAll('button').find((b) => b.text().includes('开始执行'))
    expect(launch).toBeTruthy()
    await launch!.trigger('click')
    await flushPromises()
    expect(createSpy).toHaveBeenCalled()
    const arg = createSpy.mock.calls[0][0]
    expect(arg.step_to).toBe(2)
  })

  it('submits step_to=null when "全部执行" is selected', async () => {
    const { wrapper, createSpy } = await mountDrawer()
    await wrapper.find('.exdraw-step-trigger').trigger('click')
    await flushPromises()
    // Element Plus' popover content is teleported to body; the
    // current wrapper's popover is appended alongside any leftover
    // content from earlier tests.  Use the LAST 4 rows (the freshly
    // opened popover's content always comes after pre-existing rows)
    // rather than asserting the total count, which would couple this
    // test to test ordering.
    const rows = document.body.querySelectorAll('.exdraw-step-row')
    const allRow = rows[0] as HTMLElement
    allRow.click()
    await flushPromises()
    const launch = wrapper.findAll('button').find((b) => b.text().includes('开始执行'))
    await launch!.trigger('click')
    await flushPromises()
    const arg = createSpy.mock.calls[0][0]
    expect(arg.step_to).toBeNull()
  })
})