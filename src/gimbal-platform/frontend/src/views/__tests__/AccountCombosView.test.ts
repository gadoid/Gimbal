/**
 * AccountCombosView.vue 管理页 v1(账户组合 §8.2 四区之①②④ + ③简版):
 * scope 分组列表 / 引用计数 / 创建(含条目)/ 保存(条目脏才带 entries,
 * 元数据不加修订)/ 删除被引用 409 方案清单。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import AccountCombosView from '@/views/AccountCombosView.vue'
import {
  createAccountCombo, deleteAccountCombo, getAccountComboReadiness,
  listAccountCombos, setDefaultAccountCombo, updateAccountCombo,
  type AccountComboList, type AccountComboReadiness,
} from '@/api/accountCombos'
import { pingDeployment } from '@/api/deployments'
import { testConnection } from '@/api/auth_sessions'
import { testProjectCredential } from '@/api/project_credentials'
import { ApiError } from '@/api/http'

vi.mock('@/api/accountCombos', async (importOriginal) => {
  const orig = await importOriginal<typeof import('@/api/accountCombos')>()
  return {
    ...orig,
    listAccountCombos: vi.fn(),
    createAccountCombo: vi.fn(),
    updateAccountCombo: vi.fn(),
    setDefaultAccountCombo: vi.fn(),
    deleteAccountCombo: vi.fn(),
    getAccountComboReadiness: vi.fn(),
  }
})

vi.mock('@/api/deployments', () => ({ pingDeployment: vi.fn() }))
vi.mock('@/api/auth_sessions', () => ({ testConnection: vi.fn() }))
vi.mock('@/api/project_credentials', () => ({ testProjectCredential: vi.fn() }))

vi.mock('@/api/projects', () => ({
  listProjects: vi.fn().mockResolvedValue([]),
}))

vi.mock('@/api/service-aliases', () => ({
  listAllAliases: vi.fn().mockResolvedValue([
    { aliasName: 'fin-qa1', baseService: 'fin-service' },
    { aliasName: 'jira-ops', baseService: 'jira' },
  ]),
}))

const _list: AccountComboList = {
  personal: [{
    id: 7, scope: 'user', scopeId: 1, name: '测试组合', description: '',
    isDefault: true, revision: 2,
    entries: [{ service: 'fin-service', alias: 'fin-qa1' }],
    referenceCount: 1,
    schemes: [{
      comboId: 7, schemeId: 'rs-1', schemeName: '冒烟方案',
      scenarioId: 'sc-1', scenarioName: '订单场景',
    }],
  }],
  projects: [{
    projectId: 4, projectName: '商户B', items: [{
      id: 9, scope: 'project', scopeId: 4, name: '项目组合', description: '',
      isDefault: false, revision: 1, entries: [], referenceCount: 0, schemes: [],
    }],
  }],
}

function ready(
  source: 'personal' | 'project' = 'personal',
): AccountComboReadiness {
  return {
    credentialSource: source,
    projectId: source === 'project' ? 4 : null,
    poolName: source === 'project' ? '商户B' : '我',
    canProbeCredentials: true,
    environmentId: 1,
    environmentName: '测试环境',
    environmentSource: 'identity',
    envError: null,
    ready: true,
    entries: [{
      service: 'fin-service', alias: 'fin-qa1', baseService: 'fin-service',
      system: 'fin', identityEnvId: 1, refMode: 'default', refUsername: '',
      poolStatus: 'ok', accountId: 12, accountUsername: 'fin-user',
      accountEnvId: 1, envMismatch: false,
    }],
    addresses: [{
      service: 'fin-service', envId: 1, envName: '测试环境',
      baseUrl: 'https://fin.internal', loginUrl: 'https://fin-login.internal',
      deploymentId: 3, resolved: true,
    }],
  }
}

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/composer/:scenarioId', component: { template: '<div/>' } },
      { path: '/scenarios/:scenarioId/schemes', component: { template: '<div/>' } },
    ],
  })
  const w = mount(AccountCombosView, { global: { plugins: [router] } })
  await flushPromises()
  return w
}

describe('AccountCombosView 管理页 v1(账户组合 §8.2)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(listAccountCombos).mockResolvedValue(structuredClone(_list))
    vi.mocked(getAccountComboReadiness).mockImplementation(async (_id, source) => ready(source))
    vi.mocked(pingDeployment).mockResolvedValue({
      ok: true, statusCode: 200, latencyMs: 5, message: 'ok',
    })
    vi.mocked(testConnection).mockResolvedValue({
      ok: true, status_code: 200, message: 'ok',
    })
    vi.mocked(testProjectCredential).mockResolvedValue({
      ok: true, status_code: 200, message: 'ok',
    })
  })

  it('① 列表 scope 分组:个人 + 项目组;默认标记与引用计数', async () => {
    const w = await mountPage()
    const rail = w.get('[data-testid="ac-list"]')
    expect(rail.text()).toContain('个人')
    expect(rail.text()).toContain('测试组合')
    expect(rail.text()).toContain('默认')
    expect(rail.text()).toContain('引 1')
    expect(rail.text()).toContain('商户B')
    expect(rail.text()).toContain('项目组合')
    w.unmount()
  })

  it('② 选中组合:条目回填;保存(条目无变化不带 entries → 不加修订)', async () => {
    const w = await mountPage()
    await w.get('[data-testid="ac-item-7"]').trigger('click')
    await flushPromises()
    expect(w.get('[data-testid="ac-entry-service-0"]').element as HTMLInputElement)
      .toBeTruthy()
    // 条目未变只保存元数据 → 不携带 entries(§4.1 元数据不加修订)
    vi.mocked(updateAccountCombo).mockResolvedValue(
      structuredClone(_list.personal[0]))
    await w.get('[data-testid="ac-save"]').trigger('click')
    await flushPromises()
    expect(updateAccountCombo).toHaveBeenCalledWith(7,
      expect.not.objectContaining({ entries: expect.anything() }))
    w.unmount()
  })

  it('创建:填名 + 添加条目 → facade 载荷带 entries', async () => {
    vi.mocked(createAccountCombo).mockResolvedValue(
      structuredClone(_list.personal[0]))
    const w = await mountPage()
    await w.get('[data-testid="ac-new"]').trigger('click')
    await w.get('[data-testid="ac-name"]').setValue('新组合')
    await w.get('[data-testid="ac-add-entry"]').trigger('click')
    await w.get('[data-testid="ac-entry-service-0"]').setValue('fin-service')
    await w.get('[data-testid="ac-entry-alias-0"]').setValue('fin-qa1')
    await w.get('[data-testid="ac-save"]').trigger('click')
    await flushPromises()
    expect(createAccountCombo).toHaveBeenCalledWith(expect.objectContaining({
      name: '新组合', scope: 'user',
      entries: [{ service: 'fin-service', alias: 'fin-qa1' }],
    }))
    w.unmount()
  })

  it('④ 引用方案清单可读;删除被引用 → 409 方案清单就地展示', async () => {
    vi.mocked(deleteAccountCombo).mockRejectedValue(new ApiError(
      409, 'account_combo_in_use', '组合仍被方案引用', {
        code: 'account_combo_in_use',
        schemes: [{
          comboId: 7, schemeId: 'rs-1', schemeName: '冒烟方案',
          scenarioId: 'sc-1', scenarioName: '订单场景',
        }],
      }))
    const w = await mountPage()
    await w.get('[data-testid="ac-item-7"]').trigger('click')
    await flushPromises()
    await w.get('[data-testid="ac-delete"]').trigger('click')
    await flushPromises()
    expect(w.get('[data-testid="ac-scheme-refs"]').text()).toContain('冒烟方案')
    const box = w.get('[data-testid="ac-in-use"]')
    expect(box.text()).toContain('冒烟方案')
    expect(box.text()).toContain('订单场景')
    w.unmount()
  })

  it('③ 就绪区展示个人池装载与地址矩阵,Ping All 调地址和账户拨测', async () => {
    const w = await mountPage()
    await w.get('[data-testid="ac-item-7"]').trigger('click')
    await flushPromises()
    expect(getAccountComboReadiness).toHaveBeenCalledWith(7, 'personal')
    expect(w.get('[data-testid="ac-ready-summary"]').text()).toContain('当前执行池可执行')
    expect(w.get('[data-testid="ac-ready-entry-fin-service"]').text()).toContain('fin-user')
    expect(w.get('[data-testid="ac-address-fin-service-1"]').text()).toContain('采用')
    await w.get('[data-testid="ac-ping-all"]').trigger('click')
    await flushPromises()
    expect(pingDeployment).toHaveBeenCalledWith(3)
    expect(testConnection).toHaveBeenCalledWith(12)
    expect(w.get('[data-testid="ac-ready-summary"]').text()).toContain('2/2 正常')
    w.unmount()
  })

  it('③ 项目组合可切个人/项目池,拨测走项目凭证端点', async () => {
    const w = await mountPage()
    await w.get('[data-testid="ac-item-9"]').trigger('click')
    await flushPromises()
    expect(getAccountComboReadiness).toHaveBeenCalledWith(9, 'project')
    const buttons = w.get('[data-testid="ac-pool-switch"]').findAll('button')
    await buttons[0]!.trigger('click')
    await flushPromises()
    expect(getAccountComboReadiness).toHaveBeenLastCalledWith(9, 'personal')
    await buttons[1]!.trigger('click')
    await flushPromises()
    expect(getAccountComboReadiness).toHaveBeenLastCalledWith(9, 'project')
    await w.get('[data-testid="ac-ping-all"]').trigger('click')
    await flushPromises()
    expect(testProjectCredential).toHaveBeenCalledWith(4, 12)
    expect(testConnection).not.toHaveBeenCalled()
    w.unmount()
  })

  it('设为默认走 set-default 端点', async () => {
    vi.mocked(setDefaultAccountCombo).mockResolvedValue(
      structuredClone(_list.projects[0].items[0]))
    const w = await mountPage()
    await w.get('[data-testid="ac-item-9"]').trigger('click')
    await flushPromises()
    await w.get('[data-testid="ac-set-default"]').trigger('click')
    await flushPromises()
    expect(setDefaultAccountCombo).toHaveBeenCalledWith(9)
    w.unmount()
  })
})
