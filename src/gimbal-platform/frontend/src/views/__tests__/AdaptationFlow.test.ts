import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import AdaptationFlow from '@/views/AdaptationFlow.vue'

vi.mock('@/api/adaptationFlow', () => ({
  fetchStaleScenarios: vi.fn().mockResolvedValue([]),
  compareRevisions: vi.fn().mockResolvedValue({
    from: 'working', to: '1.0#3',
    added: ['endpoint.fin.a.new'],
    removed: [],
    changed: { 'endpoint.fin.a.b': { type: 'endpoint', parts: { binding: {} } } },
  }),
  saveCheck: vi.fn().mockResolvedValue({ ok: true }),
  submitAdaptation: vi.fn().mockResolvedValue({
    success: true, scenario_id: 'sc-1', save_mode: 'direct',
  }),
}))

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div/>' } },
    { path: '/adaptations/new', component: AdaptationFlow },
  ],
})

function mountPage() {
  return mount(AdaptationFlow, {
    global: { plugins: [router, createPinia()] },
  })
}

describe('AdaptationFlow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('renders 4-step indicator with step 1 active', () => {
    const w = mountPage()
    expect(w.findAll('.af-step')).toHaveLength(4)
    expect(w.find('.af-step.active').text()).toContain('选择')
  })

  it('step 1 has scenario ID and target revision inputs', () => {
    const w = mountPage()
    expect(w.find('[data-testid="adapt-scenario-id"]').exists()).toBe(true)
    expect(w.find('[data-testid="adapt-target-revision"]').exists()).toBe(true)
  })

  it('compare button disabled when fields empty', () => {
    const w = mountPage()
    const btn = w.find('[data-testid="adapt-next-compare"]')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('fills fields and compares → shows diff items', async () => {
    const w = mountPage()
    await w.find('[data-testid="adapt-scenario-id"]').setValue('fin-test-1')
    await w.find('[data-testid="adapt-target-revision"]').setValue('1.0#3')
    const btn = w.find('[data-testid="adapt-next-compare"]')
    expect(btn.attributes('disabled')).toBeUndefined()
    await btn.trigger('click')
    await flushPromises()
    expect(w.findAll('.diff-item').length).toBeGreaterThan(0)
  })

  it('save check passes → shows direct save and copy buttons', async () => {
    const w = mountPage()
    // 直接设置内部状态到 step 3
    const vm = w.vm as unknown as Record<string, unknown>
    vm.step = 3
    vm.checkResult = { ok: true }
    vm.checking = false
    await w.vm.$nextTick()
    expect(w.find('[data-testid="check-ok"]').exists()).toBe(true)
    expect(w.find('[data-testid="adapt-save-direct"]').exists()).toBe(true)
    expect(w.find('[data-testid="adapt-save-copy"]').exists()).toBe(true)
  })

  it('save check fails → shows error and hint', async () => {
    const w = mountPage()
    const vm = w.vm as unknown as Record<string, unknown>
    vm.step = 3
    vm.checkResult = { ok: false, error: 'ENDPOINT_NOT_IN_RELEASE' }
    vm.checking = false
    await w.vm.$nextTick()
    expect(w.find('[data-testid="check-fail"]').exists()).toBe(true)
    expect(w.text()).toContain('ENDPOINT_NOT_IN_RELEASE')
  })
})
