/** IntegrationDetail — 集成详情(webhook v4 §8;原型 IntegrationDetail × 9)。
 * 覆盖:头(模式/状态 pill + 操作)、暂停横幅按 §3.3 分型(token_revoked /
 * manual)、身份与令牌 dl、最近运行(按场景查执行)。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import IntegrationDetail from '@/views/IntegrationDetail.vue'
import * as api from '@/api/integration'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/integration', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/integration')>()
  return { ...actual,
    getIntegrationTask: vi.fn(),
    patchIntegrationTask: vi.fn(),
    runIntegrationTask: vi.fn(),
    deleteIntegrationTask: vi.fn(),
    pauseMySubscription: vi.fn(),
    resumeMySubscription: vi.fn(),
    integrationErr: vi.fn(() => '错误'),
  }
})
vi.mock('@/api/access-tokens', () => ({
  getAccessToken: vi.fn(),
}))
vi.mock('@/api/executions', () => ({
  listExecutions: vi.fn().mockResolvedValue({
    items: [
      { id: 4830, scenario_id: 'sc-w', status: 'done', started_at: '2026-11-05T01:00:00Z', finished_at: null },
      { id: 4799, scenario_id: 'sc-w', status: 'failed', started_at: '2026-11-04T07:00:00Z', finished_at: null },
    ], total: 2, page: 1, pageSize: 10, failedTotal: 1,
  }),
}))
vi.mock('@/utils/toast', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))

function mkTask(over: Partial<api.IntegrationTaskItem> = {}): api.IntegrationTaskItem {
  return {
    id: 20, name: '物流轨迹同步', ownerId: 5, mine: false, canManage: true,
    visibility: 'public', identityMode: 'personal', targetType: 'scenario',
    scenarioId: 'sc-w', suiteId: null, schemeId: null, targetSystem: '',
    triggerCron: '0 * * * *', cronText: '每小时', resultPolicy: 'latest',
    cardTemplate: 'status', removed: false,
    instance: { state: 'paused', enabled: true, lastRunAt: '2026-11-05T01:00:00Z',
      lastError: '', pausedReason: 'token_revoked', nextRunAt: null, failStreak: 0,
      runStatus: 'ok', checkStatus: 'pass', checkMessage: '', checkChangedAt: null },
    tokenId: 9, tokenName: 'agent-nightly',
    ...over,
  }
}

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/integrations/:taskId', component: IntegrationDetail },
      { path: '/integrations', component: { template: '<div/>' } },
    ],
  })
  router.push('/integrations/20')
  await router.isReady()
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.currentUser = {
    id: 1, username: 't', display_name: '', role: 'admin',
    is_active: true, created_at: '', updated_at: '',
  } as never
  const w = mount(IntegrationDetail, {
    attachTo: document.body,
    global: {
      plugins: [router, pinia],
      stubs: { RouterLink: { template: '<a><slot /></a>' } },
    },
  })
  await flushPromises()
  return w
}

describe('IntegrationDetail — 集成详情(原型对齐)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('头 + 暂停横幅(token_revoked:解绑主按钮 + 启动置灰)+ 身份与令牌 + 最近运行', async () => {
    vi.mocked(api.getIntegrationTask).mockResolvedValue(mkTask())
    const { getAccessToken } = await import('@/api/access-tokens')
    vi.mocked(getAccessToken).mockResolvedValue({
      id: 9, name: 'agent-nightly', tokenHint: 'ab12…9f3c', status: 'revoked',
      scopeCounts: { aliases: 2, auths: 2 }, taskCounts: { total: 1, unsatisfied: 0 },
      callbackUrl: 'https://agent.internal/gimbal/callback',
    } as never)
    const w = await mountPage()
    const txt = w.text()
    // 面包屑 + 标题 + pills
    expect(txt).toContain('物流轨迹同步')
    expect(txt).toContain('个人模式')
    expect(txt).toContain('已暂停')
    // 横幅(原型 token-revoked 变体文案)
    expect(txt).toContain('已暂停 · 所属令牌已吊销')
    expect(txt).toContain('吊销是终态，这个任务不能直接启动')
    // 身份与令牌
    expect(txt).toContain('身份与令牌')
    expect(txt).toContain('agent-nightly · gtk_ab12…9f3c')
    expect(txt).toContain('已吊销')
    expect(txt).toContain('https://agent.internal/gimbal/callback')
    expect(txt).toContain('sc-w')
    // 最近运行(executions 按场景)
    expect(txt).toContain('最近运行')
    expect(txt).toContain('#4830')
    expect(txt).toContain('通过')
    expect(txt).toContain('#4799')
    expect(txt).toContain('失败')
    // 操作:解绑入口(头部带 testid;横幅与身份区同文案按钮)与置灰启动
    expect(w.findAll('[data-testid="idtl-unbind"]').length).toBe(1)
    expect(w.text().match(/解绑令牌（转为我管理）/g)?.length).toBeGreaterThanOrEqual(2)
    const resume = w.find('[data-testid="idtl-resume"]')
    expect(resume.attributes('disabled')).toBeDefined()
    w.unmount()
  })

  it('manual(已解绑待启动):中性横幅 + 启动主按钮', async () => {
    vi.mocked(api.getIntegrationTask).mockResolvedValue(mkTask({
      tokenId: null, tokenName: null,
      instance: { ...mkTask().instance!, pausedReason: 'manual' },
    }))
    const w = await mountPage()
    expect(w.text()).toContain('已暂停 · 待启动')
    expect(w.text()).toContain('已解绑令牌，任务改由你的账号管理')
    expect(w.find('[data-testid="idtl-resume"]').text()).toBe('启动')
    // 无令牌 → 不渲染解绑入口
    expect(w.find('[data-testid="idtl-unbind"]').exists()).toBe(false)
    w.unmount()
  })
})
