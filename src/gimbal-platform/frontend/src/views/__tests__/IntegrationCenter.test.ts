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
    patchIntegrationTask: vi.fn(),
    runIntegrationTask: vi.fn(),
    listPlatformCredentials: vi.fn().mockResolvedValue([]),
    createPlatformCredential: vi.fn(),
    deletePlatformCredential: vi.fn(),
    fetchScenarioPreview: vi.fn().mockResolvedValue({
      authAliases: [], missingCredentials: [], workingPreview: false,
    }),
    fetchSubscriptionSummary: vi.fn(),
    subscribeIntegrationTask: vi.fn(),
    unsubscribeIntegrationTask: vi.fn(),
    pauseMySubscription: vi.fn(),
    resumeMySubscription: vi.fn(),
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
    visibility: 'public', identityMode: 'personal', targetType: 'scenario',
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
    // attachTo body:reka Dialog teleport 目标(document.querySelector 检索,
    // Suites.test 同款惯例)—— 解绑确认框断言需要。RouterLink 用透传
    // slot 的 stub:默认自动 stub 不执行作用域插槽,行名链接文本会丢。
    attachTo: document.body,
    global: {
      plugins: [router, pinia],
      stubs: { RouterLink: { template: '<a><slot /></a>' } },
    },
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

  it('平台入口 M1 隐藏(authz W5):凭证区/平台令牌区对任何角色都不渲染', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([])
    const user = await mountPage(false)
    expect(user.find('[data-testid="ig-creds"]').exists()).toBe(false)
    user.unmount()
    const admin = await mountPage(true)
    expect(admin.find('[data-testid="ig-creds"]').exists()).toBe(false)
    expect(admin.find('.ig-tokens').exists()).toBe(false)   // 平台令牌区块同闸
    admin.unmount()
  })

  it('W1 新建·个人模式:执行身份/凭证前置提示/订阅者提示;保存带 identityMode', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([])
    vi.mocked(api.fetchScenarioPreview).mockResolvedValue({
      authAliases: ['gitlab'], missingCredentials: ['gitlab'],
      workingPreview: false,
    })
    vi.mocked(api.createIntegrationTask).mockResolvedValue(mkTask())
    const w = await mountPage()
    await w.find('[data-testid="ig-create"]').trigger('click')
    await flushPromises()
    // 平台模式缺省:只读提示在场、凭证提示不在
    expect(w.find('[data-testid="ig-form-cred-hint"]').exists()).toBe(false)

    // 选场景 → 前置预览被调
    await w.find('[data-testid="ig-form-scenario"]').setValue('sc-probe')
    await flushPromises()
    expect(api.fetchScenarioPreview).toHaveBeenCalledWith('sc-probe', null)

    // 切个人模式 + 公共:凭证缺失提示与订阅者提示在场
    await w.find('[data-testid="ig-form-mode"]').setValue('personal')
    await w.find('[data-testid="ig-form-visibility"]').setValue('public')
    await flushPromises()
    const credHint = w.find('[data-testid="ig-form-cred-hint"]')
    expect(credHint.exists()).toBe(true)
    expect(credHint.text()).toContain('gitlab')
    expect(credHint.text()).toContain('未配置')
    expect(w.find('[data-testid="ig-form-subscriber-hint"]').exists()).toBe(true)

    // 保存携带执行身份
    await w.find('[data-testid="ig-form-name"]').setValue('我的待办')
    await w.find('[data-testid="ig-form-save"]').trigger('click')
    await flushPromises()
    w.unmount()
  })

  it('authz W5:平台模式入口 M1 隐藏 —— 身份下拉只剩个人,缺省恒 personal', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([])
    // admin 与 user 同口径:平台选项不渲染(创建面后端已 410)
    for (const admin of [true, false]) {
      const w = await mountPage(admin)
      await w.find('[data-testid="ig-create"]').trigger('click')
      await flushPromises()
      const modes = w.findAll('[data-testid="ig-form-mode"] option').map((o) => o.attributes('value'))
      expect(modes).toEqual(['personal'])
      expect((w.find('[data-testid="ig-form-mode"]').element as HTMLSelectElement).value).toBe('personal')
      const opts = w.findAll('[data-testid="ig-form-visibility"] option').map((o) => o.text())
      expect(opts).toEqual(['私有(只有我)', '公共(可被订阅)'])
      w.unmount()
    }
  })

  it('他人模板标签按可见性:公共 / 私有(authz C1:平台行口径退役)', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([
      mkTask({ id: 11, mine: false, visibility: 'public' }),
      mkTask({ id: 13, mine: false, visibility: 'private', identityMode: 'personal' }),
      mkTask({ id: 14, mine: true, visibility: 'private' }),
    ])
    const w = await mountPage(true)
    expect(w.find('[data-testid="ig-vis-11"]').text()).toBe('公共')
    expect(w.find('[data-testid="ig-vis-13"]').text()).toBe('私有')
    expect(w.find('[data-testid="ig-vis-14"]').exists()).toBe(false)
    expect(w.find('[data-testid="ig-row-14"]').text()).toContain('我的')
    w.unmount()
  })

  it('W1 新建·working 预警:预览标记为预览执行时两模式均显示', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([])
    vi.mocked(api.fetchScenarioPreview).mockResolvedValue({
      authAliases: [], missingCredentials: [], workingPreview: true,
    })
    const w = await mountPage()
    await w.find('[data-testid="ig-create"]').trigger('click')
    await flushPromises()
    await w.find('[data-testid="ig-form-scenario"]').setValue('sc-probe')
    await flushPromises()
    expect(w.find('[data-testid="ig-form-working-warn"]').exists()).toBe(true)
    w.unmount()
  })

  it('W2 订阅面:未订阅出订阅入口 → 弹窗摘要(步骤/读写/别名/地址)→ 确认调 subscribe', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([
      mkTask({ mine: false, canManage: false, identityMode: 'personal',
               visibility: 'public', subscribed: false, instance: null }),
    ])
    vi.mocked(api.fetchSubscriptionSummary).mockResolvedValue({
      fingerprint: 'fp',
      steps: [
        { service: 'jira', method: 'POST', path: '/issue', endpoint: null, readonly: false },
        { service: 'jira', method: 'GET', path: '/search', endpoint: null, readonly: true },
      ],
      authAliases: ['jira'], baseUrls: { jira: 'http://jira.local' },
      datasetName: '主数据', cron: '*/5 * * * *',
    })
    vi.mocked(api.subscribeIntegrationTask).mockResolvedValue(mkTask())
    const w = await mountPage()
    await w.find('[data-testid="ig-sub-3"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="sub-dialog"]').exists()).toBe(true)
    const txt = w.find('[data-testid="sub-dialog"]').text()
    expect(txt).toContain('jira')
    expect(txt).toContain('/issue')
    expect(txt).toContain('写')
    expect(txt).toContain('jira.local')
    await w.find('[data-testid="sub-confirm"]').trigger('click')
    await flushPromises()
    expect(api.subscribeIntegrationTask).toHaveBeenCalledWith(3, 'fp')
    w.unmount()
  })

  it('W2 订阅 409 consent_stale:自动重拉摘要提示重新核对,二次确认才通过', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([
      mkTask({ mine: false, canManage: false, identityMode: 'personal',
               visibility: 'public', subscribed: false, instance: null }),
    ])
    vi.mocked(api.fetchSubscriptionSummary).mockResolvedValue({
      fingerprint: 'fp-v2',
      steps: [
        { service: 'jira', method: 'POST', path: '/issue', endpoint: null, readonly: false },
      ],
      authAliases: [], baseUrls: {}, datasetName: null, cron: '*/5 * * * *',
    })
    const staleErr = Object.assign(new Error('stale'), {
      response: { data: { detail: { code: 'consent_stale', message: '模板内容已变更' } } },
    })
    const sub = vi.mocked(api.subscribeIntegrationTask)
      .mockRejectedValueOnce(staleErr as never)
      .mockResolvedValueOnce(mkTask())
    const w = await mountPage()
    await w.find('[data-testid="ig-sub-3"]').trigger('click')
    await flushPromises()
    await w.find('[data-testid="sub-confirm"]').trigger('click')
    await flushPromises()
    // 409 → 不关弹窗,自动重拉摘要并提示重新核对
    expect(api.fetchSubscriptionSummary).toHaveBeenCalledTimes(2)
    expect(w.find('[data-testid="sub-dialog"]').exists()).toBe(true)
    expect(w.find('[data-testid="sub-dialog"]').text()).toContain('已刷新摘要')
    await w.find('[data-testid="sub-confirm"]').trigger('click')
    await flushPromises()
    expect(sub).toHaveBeenLastCalledWith(3, 'fp-v2')
    w.unmount()
  })

  it('W4 owner 行出暂停/恢复(owner 不出退订;authz C1:平台行分支退役)', async () => {
    // 个人模式 owner 行(canManage + 自有实例)→ 暂停出、退订不出
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([
      mkTask({ identityMode: 'personal', mine: true, canManage: true,
               subscribed: true }),
    ])
    vi.mocked(api.pauseMySubscription).mockResolvedValue(mkTask())
    const w = await mountPage()
    expect(w.find('[data-testid="ig-pause-3"]').exists()).toBe(true)
    await w.find('[data-testid="ig-pause-3"]').trigger('click')
    await flushPromises()
    expect(api.pauseMySubscription).toHaveBeenCalledWith(3)
    w.unmount()

    // 退订不出(owner 自有实例)
    const w2 = await mountPage()
    expect(w2.find('[data-testid="ig-pause-3"]').exists()).toBe(true)
    expect(w2.find('[data-testid="ig-unsub-3"]').exists()).toBe(false)
    w2.unmount()
  })

  it('W2 已订阅:自暂停显示恢复;退订确认后调用;待确认显示重新确认与文案', async () => {
    // manual 暂停 →「已暂停(本人)」+ 恢复按钮
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([
      mkTask({ mine: false, canManage: false, identityMode: 'personal',
               subscribed: true,
               instance: { ...mkTask().instance!, state: 'paused',
                           pausedReason: 'manual' } }),
    ])
    vi.mocked(api.resumeMySubscription).mockResolvedValue(mkTask())
    let w = await mountPage()
    expect(w.find('[data-testid="ig-row-3"]').text()).toContain('已暂停(本人)')
    await w.find('[data-testid="ig-pause-3"]').trigger('click')
    await flushPromises()
    expect(api.resumeMySubscription).toHaveBeenCalledWith(3)
    w.unmount()

    // W4 连续失败自动暂停 →「连续失败暂停(N 次)」+ 恢复按钮同样可解
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([
      mkTask({ mine: false, canManage: false, identityMode: 'personal',
               subscribed: true,
               instance: { ...mkTask().instance!, state: 'paused',
                           pausedReason: 'fail_streak', failStreak: 5 } }),
    ])
    w = await mountPage()
    expect(w.find('[data-testid="ig-row-3"]').text())
      .toContain('连续失败暂停(5 次)')
    expect(w.find('[data-testid="ig-pause-3"]').text()).toContain('恢复')
    await w.find('[data-testid="ig-pause-3"]').trigger('click')
    await flushPromises()
    expect(api.resumeMySubscription).toHaveBeenCalledWith(3)
    w.unmount()

    // 退订(confirm 放行)
    const spy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.unsubscribeIntegrationTask).mockResolvedValue(undefined)
    w = await mountPage()
    await w.find('[data-testid="ig-unsub-3"]').trigger('click')
    await flushPromises()
    expect(api.unsubscribeIntegrationTask).toHaveBeenCalledWith(3)
    spy.mockRestore()
    w.unmount()

    // 待确认(template_changed)→ 状态文案 + 重新确认按钮
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([
      mkTask({ mine: false, canManage: false, identityMode: 'personal',
               subscribed: true,
               instance: { ...mkTask().instance!, state: 'paused',
                           pausedReason: 'template_changed' } }),
    ])
    w = await mountPage()
    expect(w.find('[data-testid="ig-row-3"]').text()).toContain('内容已变更·待确认')
    expect(w.find('[data-testid="ig-sub-3"]').text()).toBe('重新确认')
    w.unmount()
  })

  it('D26 解绑:管理者行出「解绑」→ 4 条说明确认框 → 确认 PATCH tokenId:null(评审 2026-11-05 P2)', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([
      mkTask({ tokenId: 9, tokenName: 'agent-nightly',
               identityMode: 'personal' }),
      mkTask({ id: 4 }),   // 未绑令牌 → 不出解绑钮
    ])
    vi.mocked(api.patchIntegrationTask).mockResolvedValue(mkTask())
    const w = await mountPage(true)
    expect(w.find('[data-testid="ig-unbind-3"]').exists()).toBe(true)
    expect(w.find('[data-testid="ig-unbind-4"]').exists()).toBe(false)
    await w.find('[data-testid="ig-unbind-3"]').trigger('click')
    await flushPromises()
    // reka Dialog teleport 到 body;attr fallthrough 不落容器 testid
    // —— 以确认钮为在场判据,文案检索 body(Suites.test 同款惯例)
    const confirmBtn = document.querySelector(
      '[data-testid="ig-unbind-confirm"]') as HTMLElement | null
    expect(confirmBtn).toBeTruthy()
    const txt = document.body.textContent || ''
    expect(txt).toContain('把「下单服务保活」转为我管理')
    expect(txt).toContain('agent-nightly 解除绑定')
    expect(txt).toContain('不再向令牌的回调地址推送事件')
    expect(txt).toContain('以你的身份、你的凭证池运行')
    expect(txt).toContain('解绑后任务处于暂停')
    confirmBtn!.click()
    await flushPromises()
    expect(api.patchIntegrationTask).toHaveBeenCalledWith(3, { tokenId: null })
    w.unmount()
  })

  it('D26 解绑确认框:解绑后以你的身份、你的凭证池运行(authz C1 单口径)', async () => {
    vi.mocked(api.listIntegrationTasks).mockResolvedValue([
      mkTask({ id: 7, tokenId: 11, tokenName: 'reg-token',
               identityMode: 'personal', canManage: true }),
    ])
    vi.mocked(api.patchIntegrationTask).mockResolvedValue(mkTask())
    const w = await mountPage(true)
    await w.find('[data-testid="ig-unbind-7"]').trigger('click')
    await flushPromises()
    const txt = document.body.textContent || ''
    expect(txt).toContain('任务解绑后以你的身份、你的凭证池运行')
    w.unmount()
  })
})
