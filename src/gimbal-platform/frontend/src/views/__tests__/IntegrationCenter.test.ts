/** IntegrationCenter — 集成页 P1:列表渲染/新建(服务端校验错误回显)/
 * 立即执行;平台凭证仅 admin 可见。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import IntegrationCenter from '@/views/IntegrationCenter.vue'
import * as api from '@/api/integration'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/integration', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/integration')>()
  return {
    ...actual,   // RUN_BADGE_TEXT / CHECK_TEXT / runAbnormalOf 用真值
    listIntegrationTasks: vi.fn(),
    createIntegrationTask: vi.fn(),
    deleteIntegrationTask: vi.fn(),
    runIntegrationTask: vi.fn(),
    listPlatformCredentials: vi.fn().mockResolvedValue([]),
    createPlatformCredential: vi.fn(),
    deletePlatformCredential: vi.fn(),
    integrationErr: vi.fn((e: unknown) => {
      const det = (e as { response?: { data?: { detail?: { message?: string } } } })
      ?.response?.data?.detail
      return det?.message || '错误'
    }),
  }
})
vi.mock('@/api/scenario-composer', () => ({
  listScenarioOptions: vi.fn().mockResolvedValue({
    items: [{ scenarioId: 'sc-probe', name: '平台探活' }], total: 1,
  }),
  listRunSchemes: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

function mkTask(over: Partial<api.IntegrationTaskItem> = {}): api.IntegrationTaskItem {
  return {
    id: 3, name: '下单服务保活', ownerId: 1, mine: true, canManage: true,
    visibility: 'public', identityMode: 'platform', targetType: 'scenario',
    scenarioId: 'sc-probe', suiteId: null, schemeId: null, targetSystem: '',
    triggerCron: '*/5 * * * *', cronText: '每 5 分钟', resultPolicy: 'on_change',
    cardTemplate: 'status', removed: false,
    instance: { state: 'idle', enabled: true,
      lastRunAt: '2026-10-10T01:00:00Z', lastError: '', pausedReason: '',
      nextRunAt: null, failStreak: 0,
      runStatus: 'ok', checkStatus: 'pass', checkMessage: '',
      checkChangedAt: null },
    ...over,
  }
}

async function mountPage(isAdmin = false) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/integrations', component: IntegrationCenter },
      { path: '/home', component: { template: '<div/>' } },
    ],
  })
  router.push('/integrations')
  await router.isReady()
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.currentUser = {
    id: 1, username: 't', display_name: '', role: isAdmin ? 'admin' : 'user',
    is_active: true, created_at: '', updated_at: '',
  } as never
  const w = mount(IntegrationCenter, {
    global: { plugins: [router, pinia], stubs: { RouterLink: true } },
  })
  await flushPromises()
  return w
}

describe('IntegrationCenter — 集成页(P1)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('列表渲染:功能/场景/周期/结果策略/最近执行 + 两列状态(检查结论/运行状态)', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([mkTask()])
    const w = await mountPage()
    const row = w.find('[data-testid="ig-row-3"]')
    expect(row.text()).toContain('下单服务保活')
    expect(row.text()).toContain('sc-probe')
    expect(row.text()).toContain('每 5 分钟')
    expect(row.text()).toContain('变化才写')
    expect(row.text()).toContain('检查通过')   // 检查结论列
    expect(row.text()).toContain('运行正常')   // 运行状态列
    // 表头两列
    const ths = w.findAll('thead th').map((h) => h.text())
    expect(ths).toContain('检查结论')
    expect(ths).toContain('运行状态')
    expect(ths).not.toContain('状态')
    w.unmount()
  })

  it('两列拆分:断言失败 ≠ 运行异常;运行异常时检查结论标「上次·」', async () => {
    // Jenkins 红了 + 断言了 result == FAILURE:检查不通过,运行正常
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([
      mkTask({ instance: { ...mkTask().instance!, runStatus: 'ok',
        checkStatus: 'fail', checkMessage: 'FAIL: expected SUCCESS eq FAILED' } }),
    ])
    let w = await mountPage()
    expect(w.find('[data-testid="ig-row-3"]').text()).toContain('检查不通过')
    expect(w.find('[data-testid="ig-row-3"]').text()).toContain('运行正常')
    w.unmount()

    // token 失效:运行异常(凭证失效),结论保留上次的并标「上次·」
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([
      mkTask({ instance: { ...mkTask().instance!, runStatus: 'transport',
        checkStatus: 'fail' } }),
    ])
    w = await mountPage()
    expect(w.find('[data-testid="ig-row-3"]').text()).toContain('网络异常')
    expect(w.find('[data-testid="ig-row-3"]').text()).toContain('上次·检查不通过')
    w.unmount()
  })

  it('立即执行回显两段式:运行状态 · 检查结论(§2.5)', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([mkTask()])
    vi.mocked(api.runIntegrationTask).mockResolvedValue({
      result: { status: 'failed', durationMs: 800, error: '' },
      instance: { ...mkTask().instance!,
        runStatus: 'ok', checkStatus: 'fail',
        checkMessage: '期望 SUCCESS 实际 FAILED' },
    } as never)
    const w = await mountPage()
    await w.find('[data-testid="ig-run-3"]').trigger('click')
    await flushPromises()
    const { toast } = await import('@/utils/toast')
    expect(toast.success).toHaveBeenCalledWith(
      expect.stringContaining('运行正常 · 检查不通过:期望 SUCCESS 实际 FAILED'))
    w.unmount()
  })

  it('新建:场景必选;服务端只读闸错误回显在弹层内', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([])
    const w = await mountPage()
    await w.find('[data-testid="ig-create"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="ig-form-scenario"]').exists()).toBe(true)

    // 空场景 → 前端校验
    await w.find('[data-testid="ig-form-name"]').setValue('探活')
    await w.find('[data-testid="ig-form-save"]').trigger('click')
    expect(w.find('[data-testid="ig-form-err"]').text()).toContain('必填')
    expect(api.createIntegrationTask).not.toHaveBeenCalled()

    // 服务端只读闸 → 弹层内回显
    vi.mocked(api.createIntegrationTask).mockRejectedValue({
      response: { data: { detail: {
        code: 'not_read_only', message: '平台模式要求全部步骤为只读: 步骤 0(POST)' } } },
    } as never)
    await w.find('[data-testid="ig-form-scenario"]').setValue('sc-probe')
    await w.find('[data-testid="ig-form-save"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="ig-form-err"]').text())
      .toContain('步骤 0(POST)')
    w.unmount()
  })

  it('平台凭证区仅 admin 渲染;普通用户无', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([])
    const user = await mountPage(false)
    expect(user.find('[data-testid="ig-creds"]').exists()).toBe(false)
    user.unmount()
    const admin = await mountPage(true)
    expect(admin.find('[data-testid="ig-creds"]').exists()).toBe(true)
    admin.unmount()
  })
})
