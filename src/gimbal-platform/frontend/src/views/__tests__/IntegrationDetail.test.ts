/** IntegrationDetail — 集成详情(webhook v4 §8;原型 IntegrationDetail × 9)。
 * 覆盖:头(模式/状态 pill + 操作)、暂停横幅按 §3.3 分型(token_revoked /
 * manual)、身份与令牌 dl、最近运行(实例快照:定时运行不落执行记录,
 * 不再按场景查执行历史)、令牌处置入口按 tokenKind 分流。 */
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
vi.mock('@/utils/toast', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))

function mkTask(over: Partial<api.IntegrationTaskItem> = {}): api.IntegrationTaskItem {
  return {
    id: 20, name: '物流轨迹同步', ownerId: 5, mine: false, canManage: true,
    visibility: 'public', targetType: 'scenario',
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
      // RouterLink 桩把 to 透出为 href,便于断言令牌入口的分流
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
  })
  await flushPromises()
  return w
}

describe('IntegrationDetail — 集成详情(原型对齐)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('头 + 暂停横幅(token_revoked:解绑主按钮 + 启动置灰)+ 身份与令牌 + 最近运行(实例快照)', async () => {
    vi.mocked(api.getIntegrationTask).mockResolvedValue(mkTask({
      instance: { ...mkTask().instance!, runStatus: 'ok', lastError: '' },
    }))
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
    // 最近运行 = 实例快照(不再按场景查执行历史 → 无 #id 行)
    expect(txt).toContain('最近运行')
    expect(txt).toContain('上次运行')
    expect(txt).toContain('运行状态')
    expect(txt).toContain('运行正常')
    expect(txt).not.toContain('#4830')
    // runStatus = ok → 不渲染错误行
    expect(txt).not.toContain('错误信息')
    // 操作:解绑入口(头部带 testid;横幅与身份区同文案按钮)与置灰启动
    expect(w.findAll('[data-testid="idtl-unbind"]').length).toBe(1)
    expect(w.text().match(/解绑令牌（转为我管理）/g)?.length).toBeGreaterThanOrEqual(2)
    const resume = w.find('[data-testid="idtl-resume"]')
    expect(resume.attributes('disabled')).toBeDefined()
    w.unmount()
  })

  it('最近运行:运行异常时投影 runStatus 人话 + lastError', async () => {
    vi.mocked(api.getIntegrationTask).mockResolvedValue(mkTask({
      instance: { ...mkTask().instance!, pausedReason: '', state: 'idle',
                  runStatus: 'auth', lastError: '凭证 gerrit-bot 认证失败(401)' },
    }))
    const w = await mountPage()
    expect(w.text()).toContain('凭证失效')
    expect(w.text()).toContain('错误信息')
    expect(w.text()).toContain('凭证 gerrit-bot 认证失败(401)')
    w.unmount()
  })

  it('最近运行:从未运行 → 还未运行过,状态 —', async () => {
    vi.mocked(api.getIntegrationTask).mockResolvedValue(mkTask({
      instance: { ...mkTask().instance!, pausedReason: '', state: 'idle',
                  lastRunAt: null, runStatus: '' },
    }))
    const w = await mountPage()
    expect(w.text()).toContain('还未运行过')
    expect(w.text()).not.toContain('运行正常')
    w.unmount()
  })

  it('manual:横幅优先实例 lastError,缺省回通用文案(不再固定「已解绑令牌」)', async () => {
    vi.mocked(api.getIntegrationTask).mockResolvedValueOnce(mkTask({
      tokenId: null, tokenName: null,
      instance: { ...mkTask().instance!, pausedReason: 'manual',
                  lastError: '属主账号已删除,任务待平台接管' },
    }))
    const w1 = await mountPage()
    expect(w1.text()).toContain('已暂停 · 待启动')
    expect(w1.text()).toContain('属主账号已删除,任务待平台接管')
    w1.unmount()

    vi.mocked(api.getIntegrationTask).mockResolvedValueOnce(mkTask({
      tokenId: null, tokenName: null,
      instance: { ...mkTask().instance!, pausedReason: 'manual', lastError: '' },
    }))
    const w2 = await mountPage()
    expect(w2.text()).toContain('任务已手动暂停。确认无误后启动。')
    expect(w2.find('[data-testid="idtl-resume"]').text()).toBe('启动')
    // 无令牌 → 不渲染解绑入口
    expect(w2.find('[data-testid="idtl-unbind"]').exists()).toBe(false)
    w2.unmount()
  })

  it('令牌处置入口恒指个人设置(authz C1:平台令牌面退役)', async () => {
    // 个人令牌 + token_expired:去续期指向 /profile/tokens
    vi.mocked(api.getIntegrationTask).mockResolvedValueOnce(mkTask({
      tokenKind: 'personal',
      instance: { ...mkTask().instance!, pausedReason: 'token_expired' },
    }))
    const w1 = await mountPage()
    expect(w1.text()).toContain('已暂停 · 所属令牌已到期')
    const renew1 = w1.findAll('a').find((a) => a.text() === '去续期')
    expect(renew1?.attributes('href')).toBe('/profile/tokens')
    w1.unmount()

    // 个人令牌 + token_invalidated:去重新生成仍指 /profile/tokens
    vi.mocked(api.getIntegrationTask).mockResolvedValueOnce(mkTask({
      tokenKind: 'personal',
      instance: { ...mkTask().instance!, pausedReason: 'token_invalidated' },
    }))
    const w2 = await mountPage()
    const regen = w2.findAll('a').find((a) => a.text() === '去重新生成')
    expect(regen?.attributes('href')).toBe('/profile/tokens')
    w2.unmount()
  })
})
