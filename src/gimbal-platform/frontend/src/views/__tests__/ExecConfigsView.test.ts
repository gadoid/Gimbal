/** 执行配置管理页测试(执行配置分层①/③) — API 全走 mock,载荷与
 * 交互流钉住:选中回填 / 新建(空行剔除+envId 置空)/ PATCH 保存 /
 * 默认切换 / 复制 / 两步删除 / 409 内联;③ 枢纽(地址/槽位就绪 + 漂移
 * + 预览按钮)。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ExecConfigsView from '@/views/ExecConfigsView.vue'
import * as ecApi from '@/api/execConfigs'
import * as envApi from '@/api/environments'
import * as depApi from '@/api/deployments'
import * as driftApi from '@/api/execConfigs'

vi.mock('@/api/execConfigs', () => ({
  listExecConfigs: vi.fn(),
  createExecConfig: vi.fn(),
  updateExecConfig: vi.fn(),
  setDefaultExecConfig: vi.fn(),
  copyExecConfig: vi.fn(),
  deleteExecConfig: vi.fn(),
  execConfigDrift: vi.fn(),
}))
vi.mock('@/api/environments', () => ({
  listEnvironments: vi.fn(),
}))
vi.mock('@/api/deployments', () => ({
  listDeployments: vi.fn(),
}))
vi.mock('@/api/auth_sessions', () => ({
  listAll: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/api/service-aliases', () => ({
  listAllAliases: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/api/scenario-composer', () => ({
  listScenarioOptions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))
vi.mock('@/components/runs/EffectivePreviewDialog.vue', () => ({
  default: { name: 'EffectivePreviewDialog', props: ['open', 'scenarios',
    'execConfigId', 'envNames'], template: '<div data-testid="ec-preview-dialog" v-if="open"/>' },
}))

const ec = vi.mocked(ecApi)
const envs = vi.mocked(envApi)
const deps = vi.mocked(depApi)
const drift = vi.mocked(driftApi.execConfigDrift)

const ROW = {
  id: 7, name: '商户B视角@UAT', isDefault: true, environmentId: 2,
  systems: [{
    service: 'fin-service',
    bindings: { 'fin-service.merchant-b': 'merchant-b' },
    carryOverrides: { 'merchant.grade': 'B' },
  }],
}

function setup(list = [ROW]) {
  ec.listExecConfigs.mockResolvedValue(list)
  envs.listEnvironments.mockResolvedValue([
    { id: 1, name: 'SIT', description: '', lines: {}, owner_id: null, is_default: false },
    { id: 2, name: 'UAT', description: '', lines: {}, owner_id: null, is_default: true },
  ])
  deps.listDeployments.mockResolvedValue([
    { id: 1, baseService: 'fin-service', envId: 2, baseUrl: 'http://uat-fin' },
  ])
  drift.mockResolvedValue({ services: [], plateReachable: true })
}

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/admin/deployments', component: { template: '<div/>' } },
      { path: '/service-admin', component: { template: '<div/>' } },
      { path: '/auths', component: { template: '<div/>' } },
      { path: '/carry-config', component: { template: '<div/>' } },
    ],
  })
  const w = mount(ExecConfigsView, { global: { plugins: [createPinia(), router] } })
  await flushPromises()
  return w
}

describe('ExecConfigsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    setup()
  })

  it('首载:默认配置选中 → 编辑表单回填(env/绑定/carry 行)', async () => {
    const w = await mountPage()
    expect(w.get('[data-testid="ec-chip-7"]').classes()).toContain('active')
    expect((w.get('[data-testid="ec-name"]').element as HTMLInputElement).value)
      .toBe('商户B视角@UAT')
    expect((w.get('[data-testid="ec-env"]').element as HTMLSelectElement).value).toBe('2')
    expect((w.get('[data-testid="ec-sys-0"]').element as HTMLInputElement).value)
      .toBe('fin-service')
    expect((w.get('[data-testid="ec-bind-0-0"]').element as HTMLInputElement).value)
      .toBe('fin-service.merchant-b')
    expect((w.get('[data-testid="ec-slot-0-0"]').element as HTMLInputElement).value)
      .toBe('merchant-b')
    expect((w.get('[data-testid="ec-carry-0-0"]').element as HTMLInputElement).value)
      .toBe('merchant.grade')
    expect((w.get('[data-testid="ec-carryv-0-0"]').element as HTMLInputElement).value)
      .toBe('B')
    // 默认配置:无「设为默认」钮,有「默认配置」标
    expect(w.find('[data-testid="ec-set-default"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-is-default"]').exists()).toBe(true)
    w.unmount()
  })

  it('新建:空行剔除 + envId 不设置=null → POST 载荷', async () => {
    const CREATED = { id: 8, name: '新配置', isDefault: false,
                      environmentId: null, systems: [] }
    ec.createExecConfig.mockResolvedValue(CREATED)
    const w = await mountPage()
    // 保存后的 reload 返回含新配置的列表(选中新行需要它在 chips 里)
    ec.listExecConfigs.mockResolvedValue([ROW, CREATED])
    await w.get('[data-testid="ec-new"]').trigger('click')
    await w.get('[data-testid="ec-name"]').setValue('新配置')
    // 不设置环境(select 保持 '')
    await w.get('[data-testid="ec-sys-add"]').trigger('click')
    await w.get('[data-testid="ec-sys-add"]').trigger('click')
    // 两行系统:一空一实
    await w.get('[data-testid="ec-sys-1"]').setValue('crm')
    // 绑定行:一空一实
    await w.get('[data-testid="ec-bind-add-1"]').trigger('click')
    await w.get('[data-testid="ec-bind-add-1"]').trigger('click')
    await w.get('[data-testid="ec-bind-1-1"]').setValue('crm.admin')
    await w.get('[data-testid="ec-slot-1-1"]').setValue('admin')
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(ec.createExecConfig).toHaveBeenCalledWith({
      name: '新配置', environmentId: null,
      systems: [
        // 0 号空系统行被剔除;1 号的空绑定行被剔除
        { service: 'crm', bindings: { 'crm.admin': 'admin' }, carryOverrides: {} },
      ],
    })
    // 建完自动选中新副本
    expect(w.get('[data-testid="ec-chip-8"]').classes()).toContain('active')
    w.unmount()
  })

  it('编辑保存 → PATCH 整体载荷(envId 数值化)', async () => {
    ec.updateExecConfig.mockResolvedValue(ROW)
    const w = await mountPage()
    await w.get('[data-testid="ec-carryv-0-0"]').setValue('A')
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(ec.updateExecConfig).toHaveBeenCalledWith(7, {
      name: '商户B视角@UAT', environmentId: 2,
      systems: [{
        service: 'fin-service',
        bindings: { 'fin-service.merchant-b': 'merchant-b' },
        carryOverrides: { 'merchant.grade': 'A' },
      }],
    })
    w.unmount()
  })

  it('设为默认 → POST /{id}/default + 刷新', async () => {
    ec.listExecConfigs.mockResolvedValue([
      { id: 7, name: '默认套', isDefault: true, environmentId: null, systems: [] },
      { id: 9, name: '变体', isDefault: false, environmentId: null, systems: [] },
    ])
    ec.setDefaultExecConfig.mockResolvedValue(
      { id: 9, name: '变体', isDefault: true, environmentId: null, systems: [] })
    const w = await mountPage()
    await w.get('[data-testid="ec-chip-9"]').trigger('click')
    await w.get('[data-testid="ec-set-default"]').trigger('click')
    await flushPromises()
    expect(ec.setDefaultExecConfig).toHaveBeenCalledWith(9)
    expect(ec.listExecConfigs).toHaveBeenCalledTimes(2)
    w.unmount()
  })

  it('复制为新配置 → copyExecConfig(id, name) 并选中副本', async () => {
    const COPY = { id: 10, name: '副本', isDefault: false, environmentId: 2,
                   systems: ROW.systems }
    ec.copyExecConfig.mockResolvedValue(COPY)
    const w = await mountPage()
    // 复制后的 reload 返回含副本的列表(选中副本需要它在 chips 里)
    ec.listExecConfigs.mockResolvedValue([ROW, COPY])
    await w.get('[data-testid="ec-copy"]').trigger('click')
    await w.get('[data-testid="ec-copy-name"]').setValue('副本')
    await w.get('[data-testid="ec-copy-ok"]').trigger('click')
    await flushPromises()
    expect(ec.copyExecConfig).toHaveBeenCalledWith(7, '副本')
    expect(w.get('[data-testid="ec-chip-10"]').classes()).toContain('active')
    w.unmount()
  })

  it('删除:两步确认 → DELETE 后回落首行', async () => {
    ec.listExecConfigs.mockResolvedValue([
      { id: 7, name: '默认套', isDefault: true, environmentId: null, systems: [] },
      { id: 9, name: '变体', isDefault: false, environmentId: null, systems: [] },
    ])
    ec.deleteExecConfig.mockResolvedValue(undefined)
    const w = await mountPage()
    await w.get('[data-testid="ec-chip-9"]').trigger('click')
    await w.get('[data-testid="ec-del"]').trigger('click')
    expect(ec.deleteExecConfig).not.toHaveBeenCalled()
    await w.get('[data-testid="ec-del-ok"]').trigger('click')
    await flushPromises()
    expect(ec.deleteExecConfig).toHaveBeenCalledWith(9)
    // 回落:刷新后的首行(默认在前)
    expect(w.get('[data-testid="ec-chip-7"]').classes()).toContain('active')
    w.unmount()
  })

  it('重名 409 → detail.message 内联展示', async () => {
    ec.createExecConfig.mockRejectedValue({
      response: { data: { detail: { code: 'exec_config_name_exists',
                                    message: "执行配置名 'x' 已存在" } } },
    })
    const w = await mountPage()
    await w.get('[data-testid="ec-new"]').trigger('click')
    await w.get('[data-testid="ec-name"]').setValue('x')
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(w.get('[data-testid="ec-err"]').text())
      .toContain("执行配置名 'x' 已存在")
    w.unmount()
  })

  it('空态:无配置 → 空态文案,无编辑表单', async () => {
    setup([])
    const w = await mountPage()
    expect(w.text()).toContain('暂无执行配置')
    expect(w.find('[data-testid="ec-form-create"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-form-edit"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-set-default"]').exists()).toBe(false)
    w.unmount()
  })

  it('③ 枢纽:地址就绪 + 槽位缺失预填深链 + 漂移拉取 + pickable 预览', async () => {
    const w = await mountPage()
    // 地址就绪:fin-service 在所选环境(UAT=2)有部署行
    expect(w.get('[data-testid="ec-dep-fin-service"]').text())
      .toContain('http://uat-fin')
    expect(w.get('[data-testid="ec-dep-fin-service"]').text()).toContain('就绪')
    // 槽位缺失:merchant-b 无池行 → 缺绑定 + /auths 预填直达
    expect(w.get('[data-testid="ec-slot-miss-merchant-b"]').text()).toContain('缺绑定')
    expect(w.get('[data-testid="ec-goto-auth-merchant-b"]').attributes('href'))
      .toBe('/auths?newSlot=merchant-b&system=fin-service')
    // 漂移读面随选择拉取
    expect(ec.execConfigDrift).toHaveBeenCalledWith(7)
    // 预览:打开 pickable dialog(execConfigId = 选定配置)
    await w.get('[data-testid="ec-preview-open"]').trigger('click')
    expect(w.find('[data-testid="ec-preview-dialog"]').exists()).toBe(true)
    w.unmount()
  })

  it('③ 枢纽:槽位池内已绑定 → 显示就绪不出深链缺口', async () => {
    const { listAll } = await import('@/api/auth_sessions')
    vi.mocked(listAll).mockResolvedValue([
      { alias: 'b-merchant-b', slot: 'merchant-b', system: 'fin-service' },
    ] as never)
    const w = await mountPage()
    expect(w.find('[data-testid="ec-slot-miss-merchant-b"]').exists()).toBe(false)
    expect(w.text()).toContain('已绑定')
    w.unmount()
  })
})
