/**
 * AccountCombosView.vue 管理页 v1(账户组合 §8.2 四区之①②④ + ③简版):
 * scope 分组列表 / 引用计数 / 创建(含条目)/ 保存(条目脏才带 entries,
 * 元数据不加修订)/ 删除被引用 409 场景清单。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import AccountCombosView from '@/views/AccountCombosView.vue'
import {
  createAccountCombo, deleteAccountCombo, listAccountCombos,
  setDefaultAccountCombo, updateAccountCombo,
  type AccountComboList,
} from '@/api/accountCombos'
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
  }
})

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
    referenceCount: 3,
  }],
  projects: [{
    projectId: 4, projectName: '商户B', items: [{
      id: 9, scope: 'project', scopeId: 4, name: '项目组合', description: '',
      isDefault: false, revision: 1, entries: [], referenceCount: 0,
    }],
  }],
}

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/composer/:scenarioId', component: { template: '<div/>' } },
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
  })

  it('① 列表 scope 分组:个人 + 项目组;默认标记与引用计数', async () => {
    const w = await mountPage()
    const rail = w.get('[data-testid="ac-list"]')
    expect(rail.text()).toContain('个人')
    expect(rail.text()).toContain('测试组合')
    expect(rail.text()).toContain('默认')
    expect(rail.text()).toContain('引 3')
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

  it('④ 删除被引用 → 409 场景清单就地展示(不解绑不给删)', async () => {
    vi.mocked(deleteAccountCombo).mockRejectedValue(new ApiError(
      409, 'account_combo_in_use', '组合仍被场景引用', {
        code: 'account_combo_in_use',
        scenarios: [{ scenarioId: 'sc-1', name: '订单场景' }],
      }))
    const w = await mountPage()
    await w.get('[data-testid="ac-item-7"]').trigger('click')
    await flushPromises()
    await w.get('[data-testid="ac-delete"]').trigger('click')
    await flushPromises()
    const box = w.get('[data-testid="ac-in-use"]')
    expect(box.text()).toContain('订单场景')
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
