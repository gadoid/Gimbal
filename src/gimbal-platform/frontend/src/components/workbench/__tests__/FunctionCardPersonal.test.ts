/** FunctionCard — 个人侧 W2/W3:未订阅订阅入口 / 待确认与本人暂停
 * 恢复入口 / 凭证角标跳转「我的凭证」定位缺失别名。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import FunctionCard from '@/components/workbench/FunctionCard.vue'
import {
  cardSizeKey, workbenchCardDefKey, type WorkbenchCardDef,
} from '../registry'
import * as api from '@/api/integration'

vi.mock('@/api/integration', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/integration')>()
  return {
    ...actual,
    fetchFunctionCards: vi.fn(),
    runIntegrationTask: vi.fn(),
    resumeMySubscription: vi.fn(),
    pauseMySubscription: vi.fn(),
    subscribeIntegrationTask: vi.fn(),
    fetchSubscriptionSummary: vi.fn(),
    integrationErr: vi.fn((e: unknown) => String(e)),
  }
})
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const DEF: WorkbenchCardDef = {
  id: 'fn:9', title: '个人功能', accent: 'gold',
  component: () => Promise.resolve(FunctionCard),
}

const push = vi.fn()

async function mkRouter(): Promise<Router> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/auths', component: { template: '<div/>' } },
    ],
  })
  router.push('/')
  await router.isReady()
  router.push = push as never   // 断言用:捕获跳转
  return router
}

function mountCard(
  data: Partial<api.FunctionCardData> = {},
  router: Router,
  size: 'S' | 'M' | 'L' = 'M',
) {
  vi.mocked(api.fetchFunctionCards).mockResolvedValue([
    { id: 'fn:9', name: '我的待办', cronText: '每 5 分钟',
      identityMode: 'personal', ...data },
  ] as never)
  return mount(FunctionCard, {
    global: {
      plugins: [router],
      provide: {
        [workbenchCardDefKey]: ref(DEF),
        [cardSizeKey]: ref<'S' | 'M' | 'L'>(size),
      },
      stubs: { RouterLink: true },
    },
  })
}

describe('FunctionCard — 个人侧订阅/自管面(W2/W3)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('未订阅的个人卡:订阅确认入口;确认后订阅接口被调', async () => {
    vi.mocked(api.fetchSubscriptionSummary).mockResolvedValue({
      fingerprint: 'fp', steps: [], authAliases: [], baseUrls: {},
      datasetName: null, cron: '*/5 * * * *',
    })
    vi.mocked(api.subscribeIntegrationTask).mockResolvedValue({} as never)
    const w = mountCard({ state: 'none' }, await mkRouter())
    await flushPromises()
    expect(w.find('[data-testid="fn-card-fn:9-unsub"]').exists()).toBe(true)
    await w.find('[data-testid="fn-card-fn:9-subscribe"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="sub-dialog"]').exists()).toBe(true)
    await w.find('[data-testid="sub-confirm"]').trigger('click')
    await flushPromises()
    expect(api.subscribeIntegrationTask).toHaveBeenCalledWith(9, 'fp')
    w.unmount()
  })

  it('待确认(内容已变更):重新确认入口;本人暂停:恢复入口', async () => {
    vi.mocked(api.fetchSubscriptionSummary).mockResolvedValue({
      fingerprint: 'fp', steps: [], authAliases: [], baseUrls: {},
      datasetName: null, cron: '*/5 * * * *',
    })
    const w = mountCard({ state: 'paused', pausedReason: 'template_changed' }, await mkRouter())
    await flushPromises()
    expect(w.find('[data-testid="fn-card-fn:9-gate"]').text())
      .toContain('模板内容已变更')
    await w.find('[data-testid="fn-card-fn:9-reconfirm"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="sub-dialog"]').exists()).toBe(true)
    w.unmount()

    const m = mountCard({ state: 'paused', pausedReason: 'manual' }, await mkRouter())
    await flushPromises()
    expect(m.find('[data-testid="fn-card-fn:9-gate"]').text()).toContain('已由你暂停')
    vi.mocked(api.resumeMySubscription).mockResolvedValue({} as never)
    await m.find('[data-testid="fn-card-fn:9-resume"]').trigger('click')
    await flushPromises()
    expect(api.resumeMySubscription).toHaveBeenCalledWith(9)
    m.unmount()
  })

  it('W3 凭证角标可点 → 跳「我的凭证」并带缺失别名定位', async () => {
    const w = mountCard({
      state: 'paused', pausedReason: 'missing_credential',
      missingCredentials: ['gitlab'],
    }, await mkRouter())
    await flushPromises()
    expect(w.find('[data-testid="fn-card-fn:9-badge"]').text())
      .toContain('缺凭证')
    await w.find('[data-testid="fn-card-fn:9-badge"]').trigger('click')
    expect(push).toHaveBeenCalledWith({
      path: '/auths', query: { q: 'gitlab' },
    })
    w.unmount()
  })

  it('W4 连续失败自动暂停:启动门面(次数)+ 启动即恢复', async () => {
    vi.mocked(api.resumeMySubscription).mockResolvedValue({} as never)
    const w = mountCard({
      state: 'paused', pausedReason: 'fail_streak', failStreak: 5,
    }, await mkRouter())
    await flushPromises()
    expect(w.find('[data-testid="fn-card-fn:9-gate"]').text())
      .toContain('连续失败 5 次')
    await w.find('[data-testid="fn-card-fn:9-restart"]').trigger('click')
    await flushPromises()
    expect(api.resumeMySubscription).toHaveBeenCalledWith(9)
    w.unmount()
  })

  it('W4 平台卡 fail_streak 门面:管理者出「启动」,普通用户只读', async () => {
    vi.mocked(api.resumeMySubscription).mockResolvedValue({} as never)
    const a = mountCard({
      state: 'paused', pausedReason: 'fail_streak', failStreak: 5,
      identityMode: 'platform', canManage: true,
    }, await mkRouter())
    await flushPromises()
    expect(a.find('[data-testid="fn-card-fn:9-gate"]').text())
      .toContain('自动暂停')
    await a.find('[data-testid="fn-card-fn:9-restart"]').trigger('click')
    await flushPromises()
    expect(api.resumeMySubscription).toHaveBeenCalledWith(9)
    a.unmount()

    const u = mountCard({
      state: 'paused', pausedReason: 'fail_streak', failStreak: 5,
      identityMode: 'platform',
    }, await mkRouter())
    await flushPromises()
    expect(u.find('[data-testid="fn-card-fn:9-restart"]').exists())
      .toBe(false)
    u.unmount()
  })

  it('W4 L 档在跑的个人卡:「暂停」入口(平台模式不出)', async () => {
    vi.mocked(api.pauseMySubscription).mockResolvedValue({} as never)
    const w = mountCard({ state: 'idle' }, await mkRouter(), 'L')
    await flushPromises()
    const btn = w.find('[data-testid="fn-card-fn:9-pause"]')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    await flushPromises()
    expect(api.pauseMySubscription).toHaveBeenCalledWith(9)
    w.unmount()

    const p = mountCard(
      { state: 'idle', identityMode: 'platform' }, await mkRouter(), 'L')
    await flushPromises()
    expect(p.find('[data-testid="fn-card-fn:9-pause"]').exists()).toBe(false)
    p.unmount()
  })
})
