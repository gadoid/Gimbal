/** M2a S2.3:部署地址管理页 — 环境切换 / 行内编辑 / 默认环境切换
 *  (API 全走 mock;路径与载荷钉住)。authz M2a S6:部署表成为地址唯一
 *  来源,/deployments/conflicts 端点与「待裁定」区已移除 — 这里钉住
 *  冲突区不再渲染。2026-11-11 补齐环境管理面:新建 / 编辑(lines 行
 *  编辑)/ 删除(级联删部署行)。 */
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
  createEnvironment: vi.fn(),
  updateEnvironment: vi.fn(),
  deleteEnvironment: vi.fn(),
}))
vi.mock('@/api/deployments', () => ({
  listDeployments: vi.fn(),
  createDeployment: vi.fn(),
  updateDeployment: vi.fn(),
  deleteDeployment: vi.fn(),
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

  it('默认进默认环境:chip 激活 + 部署行;冲突区已随 M2a S6 移除', async () => {
    const w = await mountPage()
    expect(deps.listDeployments).toHaveBeenCalledWith(1)
    // 形制对齐 .slib:环境 chip 复用 service-area.css 的 .svc-chip,选中态是 .on
    expect(w.get('[data-testid="dep-env-1"]').classes()).toContain('on')
    expect(w.get('[data-testid="dep-row-11"]').text()).toContain('fin-service')
    // M2a S6:别名地址退役,conflicts 端点下线 — 待裁定区不再渲染
    expect(w.find('[data-testid="dep-conflicts"]').exists()).toBe(false)
    expect(w.text()).not.toContain('待裁定')
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

  it('空态不再指向已退役的服务信息管理环境面', async () => {
    envs.listEnvironments.mockResolvedValue([])
    const w = await mountPage()
    expect(w.text()).not.toContain('服务信息管理')
    expect(w.find('[data-testid="dep-env-new"]').exists()).toBe(true)
    w.unmount()
  })

  it('新建环境:name/description/lines → POST 后切到新环境', async () => {
    envs.createEnvironment.mockResolvedValue(
      { id: 3, name: 'UAT', description: '预发验收', lines: {},
        owner_id: null, is_default: false })
    const w = await mountPage()
    await w.get('[data-testid="dep-env-new"]').trigger('click')
    await w.get('[data-testid="dep-env-name"]').setValue('UAT')
    await w.get('[data-testid="dep-env-desc"]').setValue('预发验收')
    // 加两行版本线(一行留空系统名 → 落 lines 时剔除)
    await w.get('[data-testid="dep-env-add-line"]').trigger('click')
    await w.get('[data-testid="dep-env-add-line"]').trigger('click')
    await w.get('[data-testid="dep-env-sys-0"]').setValue('fin')
    await w.get('[data-testid="dep-env-line-0"]').setValue('2.0')
    await w.get('[data-testid="dep-env-save"]').trigger('click')
    await flushPromises()
    expect(envs.createEnvironment).toHaveBeenCalledWith(
      { name: 'UAT', description: '预发验收', lines: { fin: '2.0' } })
    // 建完自动切到新环境拉部署行
    expect(deps.listDeployments).toHaveBeenCalledWith(3)
    expect(w.find('[data-testid="dep-env-form-create"]').exists()).toBe(false)
    w.unmount()
  })

  it('编辑环境:回填 description/lines → PUT {description, lines}', async () => {
    envs.listEnvironments.mockResolvedValue([
      { id: 1, name: '测试', description: '旧描述', lines: { fin: '1.0' },
        owner_id: null, is_default: true },
    ])
    envs.updateEnvironment.mockResolvedValue(
      { id: 1, name: '测试', description: '新描述', lines: { fin: '2.0' },
        owner_id: null, is_default: true })
    const w = await mountPage()
    await w.get('[data-testid="dep-env-edit"]').trigger('click')
    // lines 回填成行(存量 fin:1.0 → 一行)
    expect(
      (w.get('[data-testid="dep-env-sys-0"]').element as HTMLInputElement).value,
    ).toBe('fin')
    await w.get('[data-testid="dep-env-desc"]').setValue('新描述')
    await w.get('[data-testid="dep-env-sys-0"]').setValue('fin')
    await w.get('[data-testid="dep-env-line-0"]').setValue('2.0')
    await w.get('[data-testid="dep-env-save"]').trigger('click')
    await flushPromises()
    expect(envs.updateEnvironment).toHaveBeenCalledWith(
      1, { description: '新描述', lines: { fin: '2.0' } })
    w.unmount()
  })

  it('删除环境:两步确认 → DELETE 后回落到默认/首个环境', async () => {
    envs.deleteEnvironment.mockResolvedValue(undefined)
    const w = await mountPage()
    // 当前环境 1(默认);第一步武装,第二步才真删
    await w.get('[data-testid="dep-env-del"]').trigger('click')
    expect(envs.deleteEnvironment).not.toHaveBeenCalled()
    expect(w.text()).toContain('部署地址将一并删除')
    await w.get('[data-testid="dep-env-del-ok"]').trigger('click')
    await flushPromises()
    expect(envs.deleteEnvironment).toHaveBeenCalledWith(1)
    // 回落:列表刷新后选默认(仍在)或首个 → 拉部署行
    expect(deps.listDeployments).toHaveBeenCalledWith(1)
    expect(w.find('[data-testid="dep-env-del-ok"]').exists()).toBe(false)
    w.unmount()
  })
})
