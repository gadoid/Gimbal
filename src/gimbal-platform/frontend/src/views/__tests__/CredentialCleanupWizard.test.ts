/**
 * CredentialCleanupWizard.vue — 凭证清账向导(阶段 3):
 * - 盘点渲染:未登记引用(单源提取器口径由后端保证,前端只呈现)、
 *   明文快照行(referencedKeys 徽标)、就绪面板(三面清零 → 绿灯);
 * - 登记条目:createAlias(aliasName=distinct 名)→ 重盘点;
 * - 清空快照:属主本人 → 草稿读 → users={} → 保存链 PUT;非属主 →
 *   「属主执行」+ 深链(W3 admin 无旁路,向导不代刀)。
 * api 全 mock — 不碰网络。ListPage 骨架 + pinia(auth store 直插态)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import CredentialCleanupWizard from '@/views/CredentialCleanupWizard.vue'
import { fetchCleanupSurvey } from '@/api/admin'
import { createAlias } from '@/api/service-aliases'
import { getScenarioDraft, updateScenario } from '@/api/scenario-composer'
import { confirmAction } from '@/utils/confirmAction'
import { toast } from '@/utils/toast'
import type { CleanupSurvey } from '@/api/admin'

vi.mock('@/api/admin', () => ({ fetchCleanupSurvey: vi.fn() }))
vi.mock('@/api/service-aliases', () => ({ createAlias: vi.fn() }))
vi.mock('@/api/scenario-composer', () => ({
  getScenarioDraft: vi.fn(),
  updateScenario: vi.fn(),
}))
// 清空确认闸(默认放行;取消分支单测内翻转)
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn().mockResolvedValue(true),
}))
// toast 单例由 ToastHost 渲染 — 测试一律 mock 本模块(模块规范)
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))
// 当前操作人 = codfish2(快照属主判定用)
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    currentUser: { id: 2, username: 'codfish2', display_name: 'codfish2', role: 'admin' },
  }),
}))

function survey(partial: Partial<CleanupSurvey>): CleanupSurvey {
  return {
    gateMode: 'audit', registrySize: 36,
    unregistered: [], snapshots: [], bindings: [],
    ...partial,
  }
}

const SB_ROWS = [
  { scenarioId: 'sc-seed-1', name: '种子一', owner: 'gimbal', projectId: null, refs: ['sb'] },
  { scenarioId: 'sc-seed-2', name: '种子二', owner: 'gimbal', projectId: null, refs: ['sb', 'gitlab'] },
]

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(fetchCleanupSurvey).mockResolvedValue(survey({}))
  vi.mocked(createAlias).mockResolvedValue({} as any)
})

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/composer/:scenarioId', component: { template: '<div/>' } },
    ],
  })
  router.push('/admin/credential-cleanup')
  await router.isReady()
  const w = mount(CredentialCleanupWizard, {
    global: { plugins: [createPinia(), router] },
  })
  await flushPromises()
  return w
}

describe('清账向导 — 盘点渲染', () => {
  it('三面清零 → 绿灯就绪面板(可切 enforce 提示 + 运维指引)', async () => {
    const w = await mountPage()
    const panel = w.find('[data-testid="cw-readiness"]')
    expect(panel.text()).toContain('三面已清零')
    expect(panel.text()).toContain('REGISTRY_ONLY_IDENTITIES=enforce')
    expect(panel.text()).toContain('audit')
    w.unmount()
  })

  it('未登记引用:distinct 名 chip + 场景行;余项计数进就绪面板', async () => {
    vi.mocked(fetchCleanupSurvey).mockResolvedValue(survey({
      unregistered: SB_ROWS,
      snapshots: [{
        scenarioId: 'sc-snap-1', name: '快照', owner: 'codfish2',
        keys: ['codfish2'], referencedKeys: ['codfish2'],
      }],
    }))
    const w = await mountPage()
    expect(w.find('[data-testid="cw-register-sb"]').exists()).toBe(true)
    expect(w.find('[data-testid="cw-register-gitlab"]').exists()).toBe(true)
    expect(w.find('[data-testid="cw-unreg-row-sc-seed-2"]').text()).toContain('sb、gitlab')
    const panel = w.find('[data-testid="cw-readiness"]')
    expect(panel.text()).toContain('未登记引用')
    expect(panel.text()).toContain('2')
    // 快照键被步骤引用 → 先登记徽标(直接清会执行面悬空)
    expect(w.find('[data-testid="cw-snap-row-sc-snap-1"]').text()).toContain('先登记:codfish2')
    w.unmount()
  })

  it('盘点读取失败 → error toast + 面板失败态(不悬置「盘点中」)', async () => {
    vi.mocked(fetchCleanupSurvey).mockRejectedValueOnce(new Error('down'))
    const w = await mountPage()
    expect(vi.mocked(toast.error).mock.calls.length).toBeGreaterThan(0)
    const panel = w.find('[data-testid="cw-readiness"]')
    expect(panel.text()).not.toContain('三面已清零')
    // FE-02:失败≠「盘点中」悬置 —— 显式失败态 + 余项未知口径
    expect(w.find('[data-testid="cw-load-failed"]').exists()).toBe(true)
    expect(w.find('[data-testid="cw-load-failed"]').text()).toContain('余项未知')
    expect(panel.text()).not.toContain('盘点中…')
    // 恢复:重盘点成功 → 失败态退场
    await w.find('[data-testid="cw-refresh"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="cw-load-failed"]').exists()).toBe(false)
    w.unmount()
  })
})

describe('清账向导 — 登记 / 清账操作', () => {
  it('登记条目:createAlias(aliasName=名)→ 成功 toast → 重盘点', async () => {
    vi.mocked(fetchCleanupSurvey).mockResolvedValue(survey({ unregistered: SB_ROWS }))
    const w = await mountPage()
    await w.find('[data-testid="cw-register-sb"]').trigger('click')
    await flushPromises()
    expect(createAlias).toHaveBeenCalledWith(
      expect.objectContaining({ aliasName: 'sb', kind: 'plate', refMode: 'default' }))
    expect(vi.mocked(toast.success).mock.calls.some(
      ([m]) => typeof m === 'string' && m.includes('sb'))).toBe(true)
    expect(fetchCleanupSurvey).toHaveBeenCalledTimes(2) // 初次 + 操作后
    w.unmount()
  })

  it('属主本人清空快照:确认闸 → 草稿读 → users={} → 保存链 PUT → 重盘点', async () => {
    vi.mocked(fetchCleanupSurvey).mockResolvedValue(survey({
      snapshots: [{
        scenarioId: 'sc-snap-1', name: '快照', owner: 'codfish2',
        keys: ['codfish2'], referencedKeys: [],
      }],
    }))
    vi.mocked(getScenarioDraft).mockResolvedValue({
      definition: { meta: {}, steps: [], config: { users: { codfish2: { username: 'u', password: 'p' } } } },
    } as any)
    vi.mocked(updateScenario).mockResolvedValue({
      scenario: {} as any, identityWarnings: [], baseWarnings: [],
    })
    const w = await mountPage()
    await w.find('[data-testid="cw-clear-sc-snap-1"]').trigger('click')
    await flushPromises()
    expect(confirmAction).toHaveBeenCalled()
    const [sid, draft] = vi.mocked(updateScenario).mock.calls[0]
    expect(sid).toBe('sc-snap-1')
    expect((draft as { definition: { config: { users: Record<string, unknown> } } })
      .definition.config.users).toEqual({})
    expect(fetchCleanupSurvey).toHaveBeenCalledTimes(2)
    w.unmount()
  })

  it('确认闸取消 → 不动草稿不保存', async () => {
    vi.mocked(confirmAction).mockResolvedValueOnce(false)
    vi.mocked(fetchCleanupSurvey).mockResolvedValue(survey({
      snapshots: [{
        scenarioId: 'sc-snap-2', name: '快照二', owner: 'codfish2',
        keys: ['k'], referencedKeys: [],
      }],
    }))
    const w = await mountPage()
    await w.find('[data-testid="cw-clear-sc-snap-2"]').trigger('click')
    await flushPromises()
    expect(getScenarioDraft).not.toHaveBeenCalled()
    expect(updateScenario).not.toHaveBeenCalled()
    w.unmount()
  })

  it('非属主快照 → 「属主执行」+ 深链,无清空按钮(W3 admin 无旁路)', async () => {
    vi.mocked(fetchCleanupSurvey).mockResolvedValue(survey({
      snapshots: [{
        scenarioId: 'sc-snap-3', name: '他属主', owner: 'Catfish',
        keys: ['codfish2'], referencedKeys: [],
      }],
    }))
    const w = await mountPage()
    const row = w.find('[data-testid="cw-snap-row-sc-snap-3"]')
    expect(row.text()).toContain('属主执行')
    expect(row.find('[data-testid="cw-clear-sc-snap-3"]').exists()).toBe(false)
    w.unmount()
  })
})
