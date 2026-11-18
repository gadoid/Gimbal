/** 执行配置管理页测试(执行配置分层①/③;2026-11-18 注册簿驱动重构 +
 * 表单 v2 级联驱动 + 2026-11-19 表单 v3 carry 退场)— API 全走 mock,
 * 载荷与交互流钉住:选中回填 / 新建(行内「换用为」即成绑定)/保存 /
 * 默认切换 / 复制 / 两步删除 / 409 内联;表单 v2(身份条目表行内换用 +
 * 装载列 + 实例过滤 + 存量绑定节);v3(配置级 carry 写面退场 —— 存量
 * 只读回写、无任何 carry 编辑控件、枢纽④漂移撤下);③ 枢纽(部署×实例
 * 并集矩阵含登录口 / 条目就绪 / 预览)。§8.2 后配置无 env 位 —— 载荷
 * 不再带 environmentId。 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ExecConfigsView from '@/views/ExecConfigsView.vue'
import * as ecApi from '@/api/execConfigs'
import type { ExecConfigRow } from '@/api/execConfigs'
import * as envApi from '@/api/environments'
import * as depApi from '@/api/deployments'
import * as svcApi from '@/api/services'
import type { ServiceList } from '@/api/services'
import * as aliasApi from '@/api/service-aliases'
import type { ServiceAliasRow, AliasPage } from '@/api/service-aliases'
import * as authApi from '@/api/auth_sessions'

vi.mock('@/api/execConfigs', () => ({
  listExecConfigs: vi.fn(),
  createExecConfig: vi.fn(),
  getExecConfig: vi.fn(),
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
  listAll: vi.fn(),
}))
// 注册簿:主档(listServices)+ 实例行(listInstances,登录口列/实例过滤)
vi.mock('@/api/services', () => ({
  listServices: vi.fn(),
  listInstances: vi.fn(),
}))
// 身份条目注册表:按 {base}(写面身份表)/ {q}(枢纽定向检索)分派
vi.mock('@/api/service-aliases', () => ({
  listAliases: vi.fn(),
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

// ── 注册簿布景 ────────────────────────────────────────────────────
// 主档两条服务;条目 fin-service × 3(UAT 2 + SIT 1,供跨环境换用/实例
// 过滤用例)+ crm × 2。
const CATALOG: ServiceList = {
  services: [
    { name: 'fin-service', system: 'fin-service', kind: 'plate', abbr: '',
      description: '交易核心服务', inCatalog: true, createdAt: '', updatedAt: '' },
    { name: 'crm', system: 'crm', kind: 'plate', abbr: '',
      description: '客户关系服务', inCatalog: true, createdAt: '', updatedAt: '' },
  ],
  unregistered: [], plateReachable: true,
}

const ALIASES: ServiceAliasRow[] = [
  { aliasName: 'fin-service.merchant-b', baseService: 'fin-service',
    kind: 'plate', slot: 'fin-service.merchant-b', envId: 2,
    refMode: 'username', refUsername: 'merchant-b',
    display: '', createdAt: '', updatedAt: '' },
  { aliasName: 'merchant-b', baseService: 'fin-service',
    kind: 'plate', slot: 'merchant-b', envId: 2,
    refMode: 'default', refUsername: null,
    display: '', createdAt: '', updatedAt: '' },
  { aliasName: 'merchant-sit', baseService: 'fin-service',
    kind: 'plate', slot: 'merchant-sit', envId: 1,
    refMode: 'default', refUsername: null,
    display: '', createdAt: '', updatedAt: '' },
  { aliasName: 'crm.admin', baseService: 'crm',
    kind: 'plate', slot: 'crm.admin', envId: 1,
    refMode: 'username', refUsername: 'admin',
    display: '', createdAt: '', updatedAt: '' },
  { aliasName: 'admin', baseService: 'crm',
    kind: 'plate', slot: 'admin', envId: 1,
    refMode: 'default', refUsername: null,
    display: '', createdAt: '', updatedAt: '' },
]

function dispatchAliases(params?: { base?: string; q?: string; page_size?: number }): Promise<AliasPage> {
  let items = ALIASES
  if (params?.base) items = items.filter((a) => a.baseService === params.base)
  if (params?.q) items = items.filter((a) => a.aliasName === params.q)
  return Promise.resolve({
    items, total: items.length, page: 1, pageSize: params?.page_size ?? 10,
  })
}

const ROW: ExecConfigRow = {
  id: 7, name: '商户B视角@UAT', isDefault: true,
  systems: [{
    service: 'fin-service',
    bindings: { 'fin-service.merchant-b': 'merchant-b' },
    carryOverrides: { 'merchant.grade': 'B' },
  }],
}

function setup(list: ExecConfigRow[] = [ROW]) {
  ec.listExecConfigs.mockResolvedValue(list)
  envs.listEnvironments.mockResolvedValue([
    { id: 1, name: 'SIT', description: '', lines: {}, owner_id: null, is_default: false },
    { id: 2, name: 'UAT', description: '', lines: {}, owner_id: null, is_default: true },
  ])
  deps.listDeployments.mockResolvedValue([
    { id: 1, baseService: 'fin-service', envId: 2, baseUrl: 'http://uat-fin' },
  ])
  vi.mocked(svcApi.listServices).mockResolvedValue(CATALOG)
  vi.mocked(svcApi.listInstances).mockResolvedValue([])
  vi.mocked(aliasApi.listAliases).mockImplementation(dispatchAliases)
  vi.mocked(authApi.listAll).mockResolvedValue([])
}

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      // 枢纽深链目标:服务注册(矩阵 + 服务子页;身份面入子页)
      { path: '/service-admin', component: { template: '<div/>' } },
      { path: '/service-admin/:alias', component: { template: '<div/>' } },
      { path: '/auths', component: { template: '<div/>' } },
    ],
  })
  const w = mount(ExecConfigsView, { global: { plugins: [createPinia(), router] } })
  await flushPromises()
  return w
}

/** select 的 optgroup → {label: [option values]}(断言换用候选分组) */
function optgroupsOf(el: HTMLSelectElement): Array<[string, string[]]> {
  return [...el.getElementsByTagName('optgroup')].map((g) => [
    g.label,
    [...g.getElementsByTagName('option')].map((o) => o.value),
  ])
}

describe('ExecConfigsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    setup()
  })

  it('首载:默认配置选中 → 身份表行回填换用值 + 存量 carry 只读视图', async () => {
    const w = await mountPage()
    expect(w.get('[data-testid="ec-chip-7"]').classes()).toContain('on')
    expect((w.get('[data-testid="ec-name"]').element as HTMLInputElement).value)
      .toBe('商户B视角@UAT')
    // 服务 = 主档下拉,回填值命中主档选项
    expect((w.get('[data-testid="ec-sys-0"]').element as HTMLSelectElement).value)
      .toBe('fin-service')
    // 身份条目表:行 = 该服务注册表条目(3 条);声明条目行回显换用值
    expect(w.get('[data-testid="ec-idents-0"]').text()).toContain('merchant-sit')
    expect((w.get('[data-testid="ec-swap-0-fin-service.merchant-b"]').element as HTMLSelectElement).value).toBe('merchant-b')
    // v3:存量 carry 只读视图(无编辑控件、无字段面)
    const legacy = w.get('[data-testid="ec-carry-legacy-0"]')
    expect(legacy.text()).toContain('merchant.grade')
    expect(legacy.text()).toContain('B')
    expect(w.find('[data-testid="ec-carryv-0-merchant.grade"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-face-0"]').exists()).toBe(false)
    // 手写拼行按钮全站退场
    expect(w.find('[data-testid="ec-bind-add-0"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-carry-add-0"]').exists()).toBe(false)
    // 默认配置:无「设为默认」钮,有「默认配置」标
    expect(w.find('[data-testid="ec-set-default"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-is-default"]').exists()).toBe(true)
    w.unmount()
  })

  it('新建:身份表行上选「换用为」即成绑定 → POST 载荷(§8.2 无 env 位)', async () => {
    const CREATED = { id: 8, name: '新配置', isDefault: false, systems: [] }
    ec.createExecConfig.mockResolvedValue(CREATED)
    const w = await mountPage()
    // 保存后的 reload 返回含新配置的列表(选中新行需要它在 chips 里)
    ec.listExecConfigs.mockResolvedValue([ROW, CREATED])
    await w.get('[data-testid="ec-new"]').trigger('click')
    await w.get('[data-testid="ec-name"]').setValue('新配置')
    await w.get('[data-testid="ec-sys-add"]').trigger('click')
    await w.get('[data-testid="ec-sys-0"]').setValue('crm')
    await flushPromises() // 该服务条目表懒加载
    // 身份表行 = crm 注册表条目;在行上选「换用为」
    expect(w.get('[data-testid="ec-idents-0"]').text()).toContain('crm.admin')
    await w.get('[data-testid="ec-swap-0-crm.admin"]').setValue('admin')
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(ec.createExecConfig).toHaveBeenCalledWith({
      name: '新配置',
      systems: [
        // v3:无 carry 写面 → carryOverrides 恒空
        { service: 'crm', bindings: { 'crm.admin': 'admin' }, carryOverrides: {} },
      ],
    })
    expect(w.get('[data-testid="ec-chip-8"]').classes()).toContain('on')
    w.unmount()
  })

  it('编辑保存 → PATCH 载荷(存量 carry 原样回写)', async () => {
    ec.updateExecConfig.mockResolvedValue(ROW)
    const w = await mountPage()
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(ec.updateExecConfig).toHaveBeenCalledWith(7, {
      name: '商户B视角@UAT',
      systems: [{
        service: 'fin-service',
        bindings: { 'fin-service.merchant-b': 'merchant-b' },
        // 存量 carry 覆盖逐字保留(v3 只读回写)
        carryOverrides: { 'merchant.grade': 'B' },
      }],
    })
    w.unmount()
  })

  it('存量 carry 含 null:只读视图显式标注,保存载荷 null 不丢真(回归钉)', async () => {
    const NULL_ROW: ExecConfigRow = {
      id: 11, name: '含null配置', isDefault: true,
      systems: [{
        service: 'fin-service',
        bindings: {},
        carryOverrides: { 'merchant.grade': null },
      }],
    }
    setup([NULL_ROW])
    ec.updateExecConfig.mockResolvedValue(NULL_ROW)
    const w = await mountPage()
    const legacy = w.get('[data-testid="ec-carry-legacy-0"]')
    expect(legacy.text()).toContain('null(显式)')
    // 写面退场:无 null 开关
    expect(w.find('[data-testid="ec-carry-null-0-merchant.grade"]').exists()).toBe(false)
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    // 保存载荷:null 原样保留(执行链照常消费)
    expect(ec.updateExecConfig).toHaveBeenCalledWith(11, {
      name: '含null配置',
      systems: [{
        service: 'fin-service',
        bindings: {},
        carryOverrides: { 'merchant.grade': null },
      }],
    })
    w.unmount()
  })

  it('换用候选按环境 optgroup 分组(跨环境换用 = 换环境机制)', async () => {
    const w = await mountPage()
    const sel = w.get('[data-testid="ec-swap-0-fin-service.merchant-b"]').element as HTMLSelectElement
    // 候选 = 该服务全部条目(排除自身)按环境分组,不被实例过滤收窄
    expect(optgroupsOf(sel)).toEqual([
      ['UAT', ['merchant-b']],
      ['SIT', ['merchant-sit']],
    ])
    w.unmount()
  })

  it('存量:声明 ∉ 注册表落存量绑定节;跨服务换用值落存量组,保存不丢', async () => {
    const LEGACY: ExecConfigRow = {
      id: 13, name: '存量配置', isDefault: true,
      systems: [{
        service: 'fin-service',
        bindings: { 'ghost.entry': 'admin', 'fin-service.merchant-b': 'admin' },
        carryOverrides: {},
      }],
    }
    setup([LEGACY])
    ec.updateExecConfig.mockResolvedValue(LEGACY)
    const w = await mountPage()
    // 未登记声明条目 → 存量绑定节(手输可改可删,不再提供新增)
    const sec = w.get('[data-testid="ec-legacy-binds-0"]')
    expect((sec.get('[data-testid="ec-bind-0-0"]').element as HTMLInputElement).value)
      .toBe('ghost.entry')
    expect((sec.get('[data-testid="ec-slot-0-0"]').element as HTMLInputElement).value)
      .toBe('admin')
    // 已登记行上的跨服务换用值('admin' 属 crm)→ 存量 optgroup 兜底
    const sel = w.get('[data-testid="ec-swap-0-fin-service.merchant-b"]').element as HTMLSelectElement
    expect(sel.value).toBe('admin')
    expect(optgroupsOf(sel)).toContainEqual(['存量(不在该服务条目表)', ['admin']])
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(ec.updateExecConfig).toHaveBeenCalledWith(13, {
      name: '存量配置',
      systems: [{
        service: 'fin-service',
        bindings: { 'ghost.entry': 'admin', 'fin-service.merchant-b': 'admin' },
        carryOverrides: {},
      }],
    })
    w.unmount()
  })

  it('实例过滤:选实例 → 身份表行集收窄(换用候选不收窄)', async () => {
    // fin-service(SIT=1)有实例;UAT 无实例行
    vi.mocked(svcApi.listInstances).mockResolvedValue([
      { system: 'fin-service', envId: 1, envName: 'SIT', groupId: 'g-sit',
        tags: ['SIT'], loginUrl: 'http://sit-login', line: '', note: '',
        updatedAt: null },
    ])
    const w = await mountPage()
    await w.get('[data-testid="ec-inst-0"]').setValue('1')
    await flushPromises()
    // 行集 = SIT 条目
    expect(w.find('[data-testid="ec-ident-0-merchant-sit"]').exists()).toBe(true)
    expect(w.find('[data-testid="ec-ident-0-merchant-b"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-ident-0-fin-service.merchant-b"]').exists()).toBe(false)
    // 换用候选仍含全环境条目(跨环境换用不受过滤器影响;注册表序)
    const sel = w.get('[data-testid="ec-swap-0-merchant-sit"]').element as HTMLSelectElement
    expect(optgroupsOf(sel)).toContainEqual(['UAT', ['fin-service.merchant-b', 'merchant-b']])
    w.unmount()
  })

  it('身份表装载列:个人池解析账户回显;缺账户按坐标预填深链', async () => {
    // (fin-service, UAT=2) 默认账户 → merchant-b 行已装载;SIT 行缺账户
    vi.mocked(authApi.listAll).mockResolvedValue([
      { id: 1, system: 'fin-service', envId: 2, username: 'merchant-b',
        isDefault: true },
    ] as never)
    const w = await mountPage()
    expect(w.get('[data-testid="ec-ident-0-merchant-b"]').text())
      .toContain('账户 merchant-b')
    const sit = w.get('[data-testid="ec-ident-0-merchant-sit"]')
    expect(sit.text()).toContain('缺账户')
    expect(w.get('[data-testid="ec-ident-auth-merchant-sit"]').attributes('href'))
      .toBe('/auths?system=fin-service&envId=1')
    w.unmount()
  })

  it('服务不在主档 → 存量兜底 option 可见,保存不丢', async () => {
    const LEGACY_SVC: ExecConfigRow = {
      id: 12, name: '存量服务配置', isDefault: true,
      systems: [{ service: 'legacy-svc', bindings: {}, carryOverrides: {} }],
    }
    setup([LEGACY_SVC])
    ec.updateExecConfig.mockResolvedValue(LEGACY_SVC)
    const w = await mountPage()
    const sel = w.get('[data-testid="ec-sys-0"]').element as HTMLSelectElement
    expect(sel.value).toBe('legacy-svc')
    const legacyOpt = [...sel.options].find((o) => o.value === 'legacy-svc')
    expect(legacyOpt).toBeTruthy()
    expect((legacyOpt!.parentElement as HTMLOptGroupElement).label)
      .toBe('存量(未在主档)')
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(ec.updateExecConfig).toHaveBeenCalledWith(12, {
      name: '存量服务配置',
      systems: [{ service: 'legacy-svc', bindings: {}, carryOverrides: {} }],
    })
    w.unmount()
  })

  it('设为默认 → POST /{id}/default + 刷新', async () => {
    ec.listExecConfigs.mockResolvedValue([
      { id: 7, name: '默认套', isDefault: true, systems: [] },
      { id: 9, name: '变体', isDefault: false, systems: [] },
    ])
    ec.setDefaultExecConfig.mockResolvedValue(
      { id: 9, name: '变体', isDefault: true, systems: [] })
    const w = await mountPage()
    await w.get('[data-testid="ec-chip-9"]').trigger('click')
    await w.get('[data-testid="ec-set-default"]').trigger('click')
    await flushPromises()
    expect(ec.setDefaultExecConfig).toHaveBeenCalledWith(9)
    expect(ec.listExecConfigs).toHaveBeenCalledTimes(2)
    w.unmount()
  })

  it('复制为新配置 → copyExecConfig(id, name) 并选中副本', async () => {
    const COPY = { id: 10, name: '副本', isDefault: false, systems: ROW.systems }
    ec.copyExecConfig.mockResolvedValue(COPY)
    const w = await mountPage()
    ec.listExecConfigs.mockResolvedValue([ROW, COPY])
    await w.get('[data-testid="ec-copy"]').trigger('click')
    await w.get('[data-testid="ec-copy-name"]').setValue('副本')
    await w.get('[data-testid="ec-copy-ok"]').trigger('click')
    await flushPromises()
    expect(ec.copyExecConfig).toHaveBeenCalledWith(7, '副本')
    expect(w.get('[data-testid="ec-chip-10"]').classes()).toContain('on')
    w.unmount()
  })

  it('删除:两步确认 → DELETE 后回落首行', async () => {
    ec.listExecConfigs.mockResolvedValue([
      { id: 7, name: '默认套', isDefault: true, systems: [] },
      { id: 9, name: '变体', isDefault: false, systems: [] },
    ])
    ec.deleteExecConfig.mockResolvedValue(undefined)
    const w = await mountPage()
    await w.get('[data-testid="ec-chip-9"]').trigger('click')
    await w.get('[data-testid="ec-del"]').trigger('click')
    expect(ec.deleteExecConfig).not.toHaveBeenCalled()
    await w.get('[data-testid="ec-del-ok"]').trigger('click')
    await flushPromises()
    expect(ec.deleteExecConfig).toHaveBeenCalledWith(9)
    expect(w.get('[data-testid="ec-chip-7"]').classes()).toContain('on')
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

  it('③ 枢纽:地址矩阵就绪 + 条目缺账户预填深链 + pickable 预览', async () => {
    const w = await mountPage()
    // 地址就绪(§8.2 全环境矩阵,部署×实例并集):fin-service 的部署行
    // (UAT=2)逐环境展示,含登录口列
    expect(w.get('[data-testid="ec-hub-deps"]').text()).toContain('登录口')
    const uat = w.get('[data-testid="ec-dep-fin-service-2"]')
    expect(uat.text()).toContain('http://uat-fin')
    expect(uat.text()).toContain('UAT')
    expect(uat.text()).toContain('就绪')
    // 条目缺账户:merchant-b 条目在个人池无 (system, env) 命中 →
    // 缺账户 + /auths 按装载坐标(system+envId)预填直达
    expect(w.get('[data-testid="ec-slot-miss-merchant-b"]').text()).toContain('缺账户')
    expect(w.get('[data-testid="ec-goto-auth-merchant-b"]').attributes('href'))
      .toBe('/auths?system=fin-service&envId=2')
    // 装载坐标列(建账户的落点)
    expect(w.get('[data-testid="ec-hub-bindings"]').text())
      .toContain('fin-service × UAT · ref 默认')
    // v3:carry 漂移读面撤下(端点保留)
    expect(ec.execConfigDrift).not.toHaveBeenCalled()
    expect(w.find('[data-testid="ec-hub-carry"]').exists()).toBe(false)
    // 预览:打开 pickable dialog(execConfigId = 选定配置)
    await w.get('[data-testid="ec-preview-open"]').trigger('click')
    expect(w.find('[data-testid="ec-preview-dialog"]').exists()).toBe(true)
    w.unmount()
  })

  it('③ 枢纽:实例环境无部署行 → 并集出行(缺地址但登录口可见)', async () => {
    // SIT(1) 有 fin-service 实例但无部署地址;部署只有 UAT(2)
    vi.mocked(svcApi.listInstances).mockResolvedValue([
      { system: 'fin-service', envId: 1, envName: 'SIT', groupId: 'g-sit',
        tags: ['SIT'], loginUrl: 'http://sit-login', line: '', note: '',
        updatedAt: null },
    ])
    const w = await mountPage()
    const sit = w.get('[data-testid="ec-dep-fin-service-1"]')
    expect(sit.text()).toContain('SIT')
    expect(sit.text()).toContain('http://sit-login')
    expect(sit.text()).toContain('缺地址')
    expect(w.get('[data-testid="ec-dep-fin-service-2"]').text()).toContain('就绪')
    w.unmount()
  })

  it('③ 枢纽:条目 ref 命中个人池账户 → 已装载不出深链缺口', async () => {
    // merchant-b 条目 ref 默认 → (fin-service, UAT=2) 需默认账户
    vi.mocked(authApi.listAll).mockResolvedValue([
      { id: 1, system: 'fin-service', envId: 2, username: 'merchant-b',
        isDefault: true },
    ] as never)
    const w = await mountPage()
    expect(w.find('[data-testid="ec-slot-miss-merchant-b"]').exists()).toBe(false)
    expect(w.text()).toContain('已装载')
    w.unmount()
  })

  it('③ 枢纽:default ref 只认 is_default 账户(非默认行不算命中)', async () => {
    vi.mocked(authApi.listAll).mockResolvedValue([
      { id: 1, system: 'fin-service', envId: 2, username: 'merchant-b',
        isDefault: false },
    ] as never)
    const w = await mountPage()
    expect(w.get('[data-testid="ec-slot-miss-merchant-b"]').text()).toContain('缺账户')
    w.unmount()
  })

  it('③ 枢纽:绑定条目的注册表状态按名定向检索(不再全量拉取)', async () => {
    const w = await mountPage()
    // q = 声明/换用条目精确名;不是 listAllAliases 全量
    expect(vi.mocked(aliasApi.listAliases)).toHaveBeenCalledWith({
      q: 'fin-service.merchant-b', page_size: 10,
    })
    expect(vi.mocked(aliasApi.listAliases)).toHaveBeenCalledWith({
      q: 'merchant-b', page_size: 10,
    })
    // 精确命中 → 无「未登记」flag
    expect(w.find('[data-testid="ec-goto-faces-fin-service.merchant-b"]').exists())
      .toBe(false)
    expect(w.get('[data-testid="ec-hub-bindings"]').text()).toContain('merchant-b')
    w.unmount()
  })

  it('③ 服务接入面板:主档说明/系统回显 + 身份面子页深链', async () => {
    const w = await mountPage()
    const row = w.get('[data-testid="ec-svc-fin-service"]')
    expect(row.text()).toContain('fin-service')
    // 说明直读主档(services.description;service-meta 兼容层退役)
    expect(row.text()).toContain('交易核心服务')
    expect(w.get('[data-testid="ec-goto-faces-fin-service"]').attributes('href'))
      .toBe('/service-admin/fin-service?tab=faces')
    w.unmount()
  })

  it('③ 未登记的绑定条目 → 去该服务子页身份条目 tab 登记', async () => {
    vi.mocked(aliasApi.listAliases).mockResolvedValue({
      items: [], total: 0, page: 1, pageSize: 10,
    })
    const w = await mountPage()
    await flushPromises()
    expect(w.get('[data-testid="ec-goto-faces-fin-service.merchant-b"]').attributes('href'))
      .toBe('/service-admin/fin-service?tab=faces')
    expect(w.get('[data-testid="ec-hub-bindings"]').text()).toContain('✕ 未登记')
    w.unmount()
  })
})
