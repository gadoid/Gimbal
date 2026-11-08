/** M2a S2.3:部署地址管理页 — 环境切换 / 行内编辑 / 默认环境切换 /
 * 冲突裁定(API 全走 mock;路径与载荷钉住)。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DeploymentsAdmin from '@/views/DeploymentsAdmin.vue'
import * as envApi from '@/api/environments'
import * as depApi from '@/api/deployments'

vi.mock('@/api/environments', () => ({
  listEnvironments: vi.fn(),
  setDefaultEnvironment: vi.fn(),
  unsetDefaultEnvironment: vi.fn(),
}))
vi.mock('@/api/deployments', () => ({
  listDeployments: vi.fn(),
  createDeployment: vi.fn(),
  updateDeployment: vi.fn(),
  deleteDeployment: vi.fn(),
  listDeploymentConflicts: vi.fn(),
}))

const envs = vi.mocked(envApi)
const deps = vi.mocked(depApi)

function setup() {
  envs.listEnvironments.mockResolvedValue([
    { id: 1, name: '测试', description: '', lines: {},
      owner_id: null, is_default: true },
    { id: 2, name: '预发', description: '', lines: {},
      owner_id: null, is_default: false },
  ])
  deps.listDeployments.mockResolvedValue([
    { id: 11, baseService: 'fin-service', envId: 1, baseUrl: 'http://fin-dev' },
  ])
  deps.listDeploymentConflicts.mockResolvedValue([
    { baseService: 'jira', envId: 1,
      aliases: { 'jira-a': 'http://a', 'jira-b': 'http://b' } },
  ])
}

async function mountPage() {
  const w = mount(DeploymentsAdmin, { global: { plugins: [createPinia()] } })
  await flushPromises()
  return w
}

describe('DeploymentsAdmin', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    setup()
  })

  it('默认进默认环境:chip 激活 + 部署行 + 冲突区', async () => {
    const w = await mountPage()
    expect(deps.listDeployments).toHaveBeenCalledWith(1)
    expect(w.get('[data-testid="dep-env-1"]').classes()).toContain('active')
    expect(w.get('[data-testid="dep-row-11"]').text()).toContain('fin-service')
    expect(w.get('[data-testid="dep-conflict-jira-1"]').text())
      .toContain('jira')
    // 默认环境:按钮是「取消默认」
    expect(w.find('[data-testid="dep-set-default"]').exists()).toBe(false)
    expect(w.find('[data-testid="dep-unset-default"]').exists()).toBe(true)
  })

  it('切换环境 chip → 按该环境拉部署行', async () => {
    const w = await mountPage()
    await w.get('[data-testid="dep-env-2"]').trigger('click')
    await flushPromises()
    expect(deps.listDeployments).toHaveBeenCalledWith(2)
  })

  it('添加部署行:载荷 (baseService, envId, baseUrl)', async () => {
    deps.createDeployment.mockResolvedValue(
      { id: 12, baseService: 'crm', envId: 1, baseUrl: 'http://crm' })
    const w = await mountPage()
    await w.get('[data-testid="dep-new-service"]').setValue('crm')
    await w.get('[data-testid="dep-new-url"]').setValue('http://crm')
    await w.get('[data-testid="dep-add"]').trigger('click')
    await flushPromises()
    expect(deps.createDeployment).toHaveBeenCalledWith(
      { baseService: 'crm', envId: 1, baseUrl: 'http://crm' })
  })

  it('行内编辑保存 → PATCH /deployments/{id}', async () => {
    deps.updateDeployment.mockResolvedValue(
      { id: 11, baseService: 'fin-service', envId: 1, baseUrl: 'http://v2' })
    const w = await mountPage()
    await w.get('[data-testid="dep-edit-11"]').trigger('click')
    await w.get('[data-testid="dep-edit-url-11"]').setValue('http://v2')
    await w.get('[data-testid="dep-save-11"]').trigger('click')
    await flushPromises()
    expect(deps.updateDeployment).toHaveBeenCalledWith(11, 'http://v2')
  })

  it('删除部署行', async () => {
    deps.deleteDeployment.mockResolvedValue(undefined)
    const w = await mountPage()
    await w.get('[data-testid="dep-del-11"]').trigger('click')
    await flushPromises()
    expect(deps.deleteDeployment).toHaveBeenCalledWith(11)
  })

  it('冲突裁定:选别名地址 → 建部署行并刷新', async () => {
    deps.createDeployment.mockResolvedValue(
      { id: 13, baseService: 'jira', envId: 1, baseUrl: 'http://a' })
    const w = await mountPage()
    await w.get('[data-testid="dep-resolve-jira-jira-a"]').trigger('click')
    await flushPromises()
    expect(deps.createDeployment).toHaveBeenCalledWith(
      { baseService: 'jira', envId: 1, baseUrl: 'http://a' })
    expect(deps.listDeploymentConflicts).toHaveBeenCalledTimes(2)
  })

  it('置默认/取消默认 → 环境列表刷新', async () => {
    envs.setDefaultEnvironment.mockResolvedValue(
      { id: 2, name: '预发', description: '', lines: {},
        owner_id: null, is_default: true })
    envs.unsetDefaultEnvironment.mockResolvedValue(
      { id: 1, name: '测试', description: '', lines: {},
        owner_id: null, is_default: false })
    const w = await mountPage()
    // 当前是默认环境 1 → 取消默认
    await w.get('[data-testid="dep-unset-default"]').trigger('click')
    await flushPromises()
    expect(envs.unsetDefaultEnvironment).toHaveBeenCalledWith(1)
    // 切到环境 2(刷新后仍可点)→ 设默认
    await w.get('[data-testid="dep-env-2"]').trigger('click')
    await flushPromises()
    await w.get('[data-testid="dep-set-default"]').trigger('click')
    await flushPromises()
    expect(envs.setDefaultEnvironment).toHaveBeenCalledWith(2)
  })
})
