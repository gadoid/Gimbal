/** 执行配置管理页测试(执行配置分层①/③;2026-11-18 注册簿驱动重构 +
 * 表单 v2 级联驱动 + 2026-11-19 表单 v3 carry 退场 + v4 原型改造)—
 * API 全走 mock,载荷与交互流钉住:选中回填 / 新建(行内「换用为」
 * 即成绑定)/保存 / 默认切换 / 复制 / 两步删除 / 409 内联;表单 v2
 * (身份条目表行内换用 + 装载列 + 实例过滤 + 存量绑定节);v3(配置级
 * carry 写面退场 —— 存量只读回写、无任何 carry 编辑控件、枢纽④漂移
 * 撤下);v4(左栏套件列表替代 chip 行 + 节点卡展开/收起 + 虚线追加
 * 节点大卡 + sticky 底栏 + Ping All:地址 ping 与绑定账户拨测的就地
 * 渲染与汇总);③ 枢纽(部署×实例并集矩阵含登录口 / 条目就绪 /
 * 预览)。§8.2 后配置无 env 位 —— 载荷不再带 environmentId。 */
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
import * as scenApi from '@/api/scenario-composer'
import { toast } from '@/utils/toast'
import { confirmAction } from '@/utils/confirmAction'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn().mockResolvedValue(true),
  promptAction: vi.fn(),
}))
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
  pingDeployment: vi.fn(),
}))
vi.mock('@/api/auth_sessions', () => ({
  listAll: vi.fn(),
  testConnection: vi.fn(),
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
  default: { name: 'EffectivePreviewDialog', props: ['open', 'inline', 'scenarios',
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
  // Ping All 默认:地址 ping 可达;拨测通过(用例覆盖失败路径)
  vi.mocked(depApi.pingDeployment).mockResolvedValue(
    { ok: true, statusCode: 200, latencyMs: 45, message: 'HTTP 200 · 45ms' })
  vi.mocked(authApi.testConnection).mockResolvedValue(
    { ok: true, status_code: 200, message: '连通成功' })
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

/** 工作台页签切换(v6:编辑 / 就绪度 / 预览) */
async function openTab(w: Awaited<ReturnType<typeof mountPage>>, tab: string) {
  await w.get(`[data-testid="ec-tab-${tab}"]`).trigger('click')
  await flushPromises()
}

/** 节点进入编辑态(v6:节点卡默认只读,写面控件仅编辑态渲染) */
async function enterEdit(w: Awaited<ReturnType<typeof mountPage>>, i = 0) {
  await w.get(`[data-testid="ec-node-edit-${i}"]`).trigger('click')
  await flushPromises()
}

/** 头卡进入编辑态(v7:名称/说明/标签仅编辑态渲染) */
async function enterMetaEdit(w: Awaited<ReturnType<typeof mountPage>>) {
  await w.get('[data-testid="ec-meta-edit"]').trigger('click')
  await flushPromises()
}

/** 编辑态候选下拉加入一个调用身份(搜索词可选,先筛选再选) */
async function pickAlias(
  w: Awaited<ReturnType<typeof mountPage>>, i: number,
  alias: string, query = '',
) {
  if (query) {
    await w.get(`[data-testid="ec-pick-q-${i}"]`).setValue(query)
    await flushPromises()
  }
  await w.get(`[data-testid="ec-pick-${i}"]`).setValue(alias)
  await flushPromises()
}

describe('ExecConfigsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    setup()
  })

  it('首载:默认配置选中 → 只读态已选列表 + 编辑态回填换用值 + 存量 carry 只读', async () => {
    const w = await mountPage()
    expect(w.get('[data-testid="ec-list-row-7"]').classes()).toContain('on')
    // v7:头卡默认只读 —— 名称以文本呈现,input 仅在编辑态
    expect(w.get('[data-testid="ec-meta-name"]').text()).toBe('商户B视角@UAT')
    expect(w.find('[data-testid="ec-name"]').exists()).toBe(false)
    await enterMetaEdit(w)
    expect((w.get('[data-testid="ec-name"]').element as HTMLInputElement).value)
      .toBe('商户B视角@UAT')
    // 服务 = 主档下拉,回填值命中主档选项
    expect((w.get('[data-testid="ec-sys-0"]').element as HTMLSelectElement).value)
      .toBe('fin-service')
    // v6:默认只读态 —— 已选身份紧凑列表可见,写面控件不可见
    expect(w.find('[data-testid="ec-node-view-0"]').exists()).toBe(true)
    expect(w.get('[data-testid="ec-view-slot-0-fin-service.merchant-b"]').text())
      .toContain('merchant-b')
    expect(w.find('[data-testid="ec-idents-0"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-pick-0"]').exists()).toBe(false)
    // 「编辑」进入写面:已选明细表回显换用值
    await enterEdit(w)
    expect(w.find('[data-testid="ec-node-view-0"]').exists()).toBe(false)
    expect(w.get('[data-testid="ec-idents-0"]').text())
      .toContain('fin-service.merchant-b')
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

  it('v7 头卡两态:只读呈现名称/说明/标签;编辑态改说明并卡片级保存', async () => {
    const META: ExecConfigRow = {
      id: 21, name: '元信息套', isDefault: true,
      description: '商户B端回归主配置', tags: ['UAT', '核心'],
      systems: [{ service: 'fin-service', aliases: [], bindings: {}, carryOverrides: {} }],
    }
    setup([META])
    ec.updateExecConfig.mockResolvedValue(META)
    const w = await mountPage()
    // 只读态:名称文本 + 默认徽章 + 标签 chips + 说明;无 input
    expect(w.get('[data-testid="ec-meta-name"]').text()).toBe('元信息套')
    expect(w.find('[data-testid="ec-is-default"]').exists()).toBe(true)
    expect(w.get('[data-testid="ec-meta-tag-UAT"]').text()).toBe('UAT')
    expect(w.get('[data-testid="ec-meta-tag-核心"]').text()).toBe('核心')
    expect(w.get('[data-testid="ec-meta-desc"]').text()).toContain('商户B端回归主配置')
    expect(w.find('[data-testid="ec-name"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-desc"]').exists()).toBe(false)
    // 编辑态:回填 + 改说明 + 卡片级保存(PATCH 含元信息与 systems)
    await enterMetaEdit(w)
    expect((w.get('[data-testid="ec-desc"]').element as HTMLInputElement).value)
      .toBe('商户B端回归主配置')
    // 动作行在编辑态收起
    expect(w.find('[data-testid="ec-copy"]').exists()).toBe(false)
    await w.get('[data-testid="ec-desc"]').setValue('新说明')
    // v8.2:取消/保存统一在头卡动作行(底部常驻条撤下)
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(ec.updateExecConfig).toHaveBeenCalledWith(21, expect.objectContaining({
      name: '元信息套', description: '新说明', tags: ['UAT', '核心'],
      systems: [expect.objectContaining({ service: 'fin-service' })],
    }))
    expect(toast.success).toHaveBeenCalledWith('配置已保存')
    w.unmount()
  })

  it('FE-05 在飞守卫:保存落定前按钮禁用且不双发(create 双击曾双 POST 撞名 409)', async () => {
    const META: ExecConfigRow = {
      id: 21, name: '元信息套', isDefault: true,
      description: 'd', tags: [],
      systems: [{ service: 'fin-service', aliases: [], bindings: {}, carryOverrides: {} }],
    }
    setup([META])
    ec.updateExecConfig.mockReset()
    let release!: (v: ExecConfigRow) => void
    ec.updateExecConfig.mockReturnValueOnce(
      new Promise<ExecConfigRow>((r) => { release = r }))
    const w = await mountPage()
    await enterMetaEdit(w)
    await w.get('[data-testid="ec-desc"]').setValue('新说明')
    const btn = w.get('[data-testid="ec-save"]')
    await btn.trigger('click')
    // saving 态:UI 禁用 + 文案切换
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.text()).toContain('保存中')
    // 程序化点击仍会派发事件(VTU dispatchEvent 不看 disabled)——
    // 钉的是 save() 的 saving 早退守卫:不双发 PATCH
    await btn.trigger('click')
    expect(ec.updateExecConfig).toHaveBeenCalledTimes(1)
    release(META)
    await flushPromises()
    expect(w.get('[data-testid="ec-save"]').attributes('disabled')).toBeUndefined()
    w.unmount()
  })

  it('v7/v8.2 取消:放弃全部未保存改动,头卡与节点回到只读态', async () => {
    const META: ExecConfigRow = {
      id: 22, name: '取消套', isDefault: false,
      description: '原说明', tags: [],
      systems: [{ service: 'fin-service', aliases: [], bindings: {}, carryOverrides: {} }],
    }
    setup([META])
    const w = await mountPage()
    await enterMetaEdit(w)
    await w.get('[data-testid="ec-name"]').setValue('改坏了')
    await enterEdit(w)
    // v8.2:取消 = 放弃全部未保存改动(fillForm 回填),头卡与节点均回默认态
    await w.get('[data-testid="ec-cancel"]').trigger('click')
    await flushPromises()
    expect(w.get('[data-testid="ec-meta-name"]').text()).toBe('取消套')
    expect(w.find('[data-testid="ec-name"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-idents-0"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-node-view-0"]').exists()).toBe(true)
    w.unmount()
  })

  it('v7 左栏:标签 chips + 说明副行;搜索命中说明/标签', async () => {
    const META: ExecConfigRow = {
      id: 23, name: '左栏元信息套', isDefault: true,
      description: '商户B端回归主配置', tags: ['UAT', '核心', '回归'],
      systems: [],
    }
    setup([META])
    const w = await mountPage()
    // 行内:默认徽章 + 前 2 枚标签 + +N + 说明
    expect(w.get('[data-testid="ec-list-tag-23-UAT"]').text()).toBe('UAT')
    expect(w.get('[data-testid="ec-list-tag-23-核心"]').text()).toBe('核心')
    expect(w.get('[data-testid="ec-list-row-23"]').text()).toContain('+1')
    expect(w.get('[data-testid="ec-list-desc-23"]').text()).toBe('商户B端回归主配置')
    // 搜索命中标签 / 说明
    await w.get('[data-testid="ec-list-search"]').setValue('回归')
    expect(w.find('[data-testid="ec-list-row-23"]').exists()).toBe(true)
    await w.get('[data-testid="ec-list-search"]').setValue('不存在的词')
    expect(w.find('[data-testid="ec-list-row-23"]').exists()).toBe(false)
    w.unmount()
  })

  it('v4 左栏:套件列表渲染(默认徽章 + 副行计数)+ 点击切换选中', async () => {
    ec.listExecConfigs.mockResolvedValue([
      ROW,
      { id: 9, name: '跨境链路@PRE', isDefault: false, systems: [
        { service: 'crm', bindings: { 'crm.admin': 'admin' }, carryOverrides: {} },
      ] },
    ])
    const w = await mountPage()
    const first = w.get('[data-testid="ec-list-row-7"]')
    expect(first.text()).toContain('商户B视角@UAT')
    // 默认徽章只在 isDefault 行
    expect(first.text()).toContain('默认')
    expect(w.find('[data-testid="ec-list-default-9"]').exists()).toBe(false)
    // 副行:N 服务 · M 换用(自 payload 派生)
    expect(w.get('[data-testid="ec-list-row-9"]').text()).toContain('1 服务 · 1 换用')
    // 搜索过滤(纯前端)
    await w.get('[data-testid="ec-list-search"]').setValue('跨境')
    expect(w.find('[data-testid="ec-list-row-7"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-list-row-9"]').exists()).toBe(true)
    await w.get('[data-testid="ec-list-search"]').setValue('')
    // 点击切换:选中态与表单跟随
    await w.get('[data-testid="ec-list-row-9"]').trigger('click')
    expect(w.get('[data-testid="ec-list-row-9"]').classes()).toContain('on')
    expect(w.get('[data-testid="ec-list-row-7"]').classes()).not.toContain('on')
    expect((w.get('[data-testid="ec-sys-0"]').element as HTMLSelectElement).value)
      .toBe('crm')
    w.unmount()
  })

  it('v4/v6 节点卡:默认只读已选列表;收起态摘要行 + 展开/收起切换', async () => {
    const w = await mountPage()
    // 默认展开 + 只读:已选列表可见,收起态不可见
    expect(w.find('[data-testid="ec-node-view-0"]').exists()).toBe(true)
    expect(w.find('[data-testid="ec-node-collapsed-0"]').exists()).toBe(false)
    await w.get('[data-testid="ec-node-toggle-0"]').trigger('click')
    // 收起:摘要 = §8.10 圈定集口径(存量推导 = bindings 声明键 1 条;
    // 无账户 → 1 缺装载;注册表 3 行中未圈选 2 行不计)
    expect(w.find('[data-testid="ec-node-view-0"]').exists()).toBe(false)
    const fold = w.get('[data-testid="ec-node-collapsed-0"]')
    expect(fold.text()).toContain('1 个身份条目')
    expect(fold.text()).toContain('1 条换用')
    expect(fold.text()).toContain('1 条缺装载')
    // 再点展开恢复只读态
    await w.get('[data-testid="ec-node-toggle-0"]').trigger('click')
    expect(w.find('[data-testid="ec-node-view-0"]').exists()).toBe(true)
    w.unmount()
  })

  it('新建:勾选纳入 → 行上选「换用为」 → POST 载荷(§8.10 圈定集 + §8.2 无 env 位)', async () => {
    const CREATED = { id: 8, name: '新配置', isDefault: false, systems: [] }
    ec.createExecConfig.mockResolvedValue(CREATED)
    const w = await mountPage()
    // 保存后的 reload 返回含新配置的列表(选中新行需要它在列表里)
    ec.listExecConfigs.mockResolvedValue([ROW, CREATED])
    await w.get('[data-testid="ec-new"]').trigger('click')
    await w.get('[data-testid="ec-name"]').setValue('新配置')
    // v4:虚线追加节点大卡(替代原「+ 添加服务」小钮)
    await w.get('[data-testid="ec-node-add-card"]').trigger('click')
    await w.get('[data-testid="ec-sys-0"]').setValue('crm')
    await flushPromises() // 该服务条目表懒加载
    // v6:已选列表 + 搜索加入 —— 从候选下拉加入 crm.admin,再在行上选换用
    await pickAlias(w, 0, 'crm.admin')
    expect(w.get('[data-testid="ec-idents-0"]').text()).toContain('crm.admin')
    await w.get('[data-testid="ec-swap-0-crm.admin"]').setValue('admin')
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(ec.createExecConfig).toHaveBeenCalledWith({
      name: '新配置',
      description: '',
      tags: [],
      systems: [
        // §8.10 aliases = 圈定集 ∪ 换用目标值(决策 1 阶段 1:绑定换到的
        // 取用条目自动写入圈定,白名单生效时换用目标必在圈内)
        { service: 'crm', aliases: ['crm.admin', 'admin'],
          bindings: { 'crm.admin': 'admin' }, carryOverrides: {} },
      ],
    })
    expect(w.get('[data-testid="ec-list-row-8"]').classes()).toContain('on')
    w.unmount()
  })

  it('编辑保存 → PATCH 载荷(存量 carry 原样回写)+ 成功 toast', async () => {
    ec.updateExecConfig.mockResolvedValue(ROW)
    const w = await mountPage()
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(ec.updateExecConfig).toHaveBeenCalledWith(7, {
      name: '商户B视角@UAT',
      description: '',
      tags: [],
      systems: [{
        service: 'fin-service',
        // §8.10:存量行无 aliases → 按 bindings 声明键推导,保存固化;
        // 换用目标 merchant-b 随决策 1 阶段 1 一并写入圈定集
        aliases: ['fin-service.merchant-b', 'merchant-b'],
        bindings: { 'fin-service.merchant-b': 'merchant-b' },
        // 存量 carry 覆盖逐字保留(v3 只读回写)
        carryOverrides: { 'merchant.grade': 'B' },
      }],
    })
    expect(toast.success).toHaveBeenCalledWith('配置已保存')
    w.unmount()
  })

  it('脏检查:有未保存改动 → 切换先确认;取消则不切换', async () => {
    ec.listExecConfigs.mockResolvedValue([
      ROW,
      { id: 9, name: '变体', isDefault: false, systems: [] },
    ])
    vi.mocked(confirmAction).mockResolvedValueOnce(false)
    const w = await mountPage()
    // 改名 → dirty(v7:名称输入在头卡编辑态)
    await enterMetaEdit(w)
    await w.get('[data-testid="ec-name"]').setValue('改过的名字')
    await w.get('[data-testid="ec-list-row-9"]').trigger('click')
    await flushPromises()
    expect(confirmAction).toHaveBeenCalled()
    expect(w.get('[data-testid="ec-list-row-7"]').classes()).toContain('on')
    expect((w.get('[data-testid="ec-name"]').element as HTMLInputElement).value)
      .toBe('改过的名字')
    // 确认放行 → 切换到变体(头卡回只读态,再进编辑读名称)
    vi.mocked(confirmAction).mockResolvedValueOnce(true)
    await w.get('[data-testid="ec-list-row-9"]').trigger('click')
    await flushPromises()
    expect(w.get('[data-testid="ec-list-row-9"]').classes()).toContain('on')
    expect(w.get('[data-testid="ec-meta-name"]').text()).toBe('变体')
    await enterMetaEdit(w)
    expect((w.get('[data-testid="ec-name"]').element as HTMLInputElement).value)
      .toBe('变体')
    w.unmount()
  })

  it('无改动切换不拦截(confirmAction 不调用)', async () => {
    ec.listExecConfigs.mockResolvedValue([
      ROW,
      { id: 9, name: '变体', isDefault: false, systems: [] },
    ])
    const w = await mountPage()
    await w.get('[data-testid="ec-list-row-9"]').trigger('click')
    await flushPromises()
    expect(confirmAction).not.toHaveBeenCalled()
    w.unmount()
  })

  it('移除服务节点:有绑定先确认;取消则保留,确认则移除', async () => {
    const w = await mountPage()
    // ROW 的 fin-service 节点有 1 条绑定 → 确认弹窗
    vi.mocked(confirmAction).mockResolvedValueOnce(false)
    await w.get('[data-testid="ec-sys-rm-0"]').trigger('click')
    await flushPromises()
    expect(confirmAction).toHaveBeenCalled()
    expect(w.find('[data-testid="ec-node-0"]').exists()).toBe(true)
    // 确认 → 节点移除,底栏保存时 systems 为空
    vi.mocked(confirmAction).mockResolvedValueOnce(true)
    await w.get('[data-testid="ec-sys-rm-0"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="ec-node-0"]').exists()).toBe(false)
    w.unmount()
  })

  it('移除节点后编辑态不串位:后继节点原位继承被移除节点的写面(回归钉)', async () => {
    const TWO: ExecConfigRow = {
      id: 7, name: '双节点', isDefault: true,
      systems: [
        { service: 'fin-service',
          bindings: { 'fin-service.merchant-b': 'merchant-b' },
          carryOverrides: {} },
        { service: 'crm', bindings: {}, carryOverrides: {} },
      ],
    }
    setup([TWO])
    const w = await mountPage()
    // 节点 0(fin-service)进入编辑态;节点 1(crm)保持只读
    await enterEdit(w, 0)
    expect(w.find('[data-testid="ec-pick-0"]').exists()).toBe(true)
    expect(w.find('[data-testid="ec-pick-1"]').exists()).toBe(false)
    // 移除节点 0(有绑定 → 确认放行)
    vi.mocked(confirmAction).mockResolvedValueOnce(true)
    await w.get('[data-testid="ec-sys-rm-0"]').trigger('click')
    await flushPromises()
    // 原 crm 节点顶到下标 0 —— 不得继承被移除节点的编辑态(写面
    // 控件不渲染);显式进入编辑后才出现
    expect(w.find('[data-testid="ec-node-0"]').exists()).toBe(true)
    expect(w.find('[data-testid="ec-pick-0"]').exists()).toBe(false)
    await enterEdit(w, 0)
    expect(w.find('[data-testid="ec-pick-0"]').exists()).toBe(true)
    w.unmount()
  })

  it('设为默认/复制:有未保存改动先确认,取消则不发请求', async () => {
    // 「设为默认」钮只在非默认配置上渲染(v-if="!selected.isDefault")
    ec.listExecConfigs.mockResolvedValue([{ ...ROW, isDefault: false }])
    const COPY = { id: 10, name: '副本', isDefault: false, systems: [] }
    ec.setDefaultExecConfig.mockResolvedValue(
      { id: 7, name: '默认套', isDefault: true, systems: [] })
    ec.copyExecConfig.mockResolvedValue(COPY)
    const w = await mountPage()
    // 节点加入身份 → dirty(设默认/复制钮在头卡只读态动作行,meta
    // 编辑态会将其收起,故用节点编辑制造脏态)
    await enterEdit(w, 0)
    await pickAlias(w, 0, 'merchant-sit')
    vi.mocked(confirmAction).mockResolvedValueOnce(false)
    await w.get('[data-testid="ec-set-default"]').trigger('click')
    await flushPromises()
    expect(ec.setDefaultExecConfig).not.toHaveBeenCalled()
    // 确认放行 → 设默认照常(收尾整表单回填)
    vi.mocked(confirmAction).mockResolvedValueOnce(true)
    await w.get('[data-testid="ec-set-default"]').trigger('click')
    await flushPromises()
    expect(ec.setDefaultExecConfig).toHaveBeenCalledWith(7)
    // 复制同守卫:重新制造脏态 → 拦截
    await enterEdit(w, 0)
    await pickAlias(w, 0, 'merchant-sit')
    vi.mocked(confirmAction).mockResolvedValueOnce(false)
    await w.get('[data-testid="ec-copy"]').trigger('click')
    await w.get('[data-testid="ec-copy-name"]').setValue('副本')
    await w.get('[data-testid="ec-copy-ok"]').trigger('click')
    await flushPromises()
    expect(ec.copyExecConfig).not.toHaveBeenCalled()
    w.unmount()
  })

  it('新建后取消 → 回到新建前选中的配置(不落空白工作台)', async () => {
    const w = await mountPage()
    expect(w.get('[data-testid="ec-list-row-7"]').classes()).toContain('on')
    await w.get('[data-testid="ec-new"]').trigger('click')
    await flushPromises()
    expect(w.get('[data-testid="ec-name"]').element).toBeTruthy()   // 新建态
    await w.get('[data-testid="ec-cancel"]').trigger('click')
    await flushPromises()
    // 回选 ROW:左栏高亮复位 + 头卡只读名恢复
    expect(w.get('[data-testid="ec-list-row-7"]').classes()).toContain('on')
    expect(w.get('[data-testid="ec-meta-name"]').text()).toBe('商户B视角@UAT')
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
    await enterEdit(w)
    const legacy = w.get('[data-testid="ec-carry-legacy-0"]')
    expect(legacy.text()).toContain('null(显式)')
    // 写面退场:无 null 开关
    expect(w.find('[data-testid="ec-carry-null-0-merchant.grade"]').exists()).toBe(false)
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    // 保存载荷:null 原样保留(执行链照常消费)
    expect(ec.updateExecConfig).toHaveBeenCalledWith(11, {
      name: '含null配置',
      description: '',
      tags: [],
      systems: [{
        service: 'fin-service',
        aliases: [],   // §8.10:无 bindings → 推导空集
        bindings: {},
        carryOverrides: { 'merchant.grade': null },
      }],
    })
    w.unmount()
  })

  it('换用候选按环境 optgroup 分组(跨环境换用 = 换环境机制)', async () => {
    const w = await mountPage()
    await enterEdit(w)
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
    await enterEdit(w)
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
      description: '',
      tags: [],
      systems: [{
        service: 'fin-service',
        // §8.10:存量推导 = bindings 声明键(ghost.entry 未登记也并入 —— 恒视为已纳入)
        // + 换用目标值 admin(决策 1 阶段 1:取用条目自动写入圈定)
        aliases: ['ghost.entry', 'fin-service.merchant-b', 'admin'],
        bindings: { 'ghost.entry': 'admin', 'fin-service.merchant-b': 'admin' },
        carryOverrides: {},
      }],
    })
    w.unmount()
  })

  it('实例过滤(v6):收窄候选集;已选明细不随过滤消失;换用候选不收窄', async () => {
    // fin-service(SIT=1)有实例;UAT 无实例行
    vi.mocked(svcApi.listInstances).mockResolvedValue([
      { system: 'fin-service', envId: 1, envName: 'SIT', groupId: 'g-sit',
        tags: ['SIT'], loginUrl: 'http://sit-login', line: '', note: '',
        updatedAt: null },
    ])
    const w = await mountPage()
    await enterEdit(w)
    await w.get('[data-testid="ec-inst-0"]').setValue('1')
    await flushPromises()
    // 候选 = SIT 且未选 → 只有 merchant-sit(已选行仍在明细表中)
    const pick = w.get('[data-testid="ec-pick-0"]').element as HTMLSelectElement
    expect(optgroupsOf(pick)).toEqual([['SIT', ['merchant-sit']]])
    expect(w.find('[data-testid="ec-ident-0-fin-service.merchant-b"]').exists())
      .toBe(true)
    // 加入 SIT 行后,换用候选仍含全环境条目(跨环境换用不受过滤器影响)
    await pickAlias(w, 0, 'merchant-sit')
    const sel = w.get('[data-testid="ec-swap-0-merchant-sit"]').element as HTMLSelectElement
    expect(optgroupsOf(sel)).toContainEqual(['UAT', ['fin-service.merchant-b', 'merchant-b']])
    w.unmount()
  })

  it('已选明细装载列(§8.3 口径):同标签命中;跨标签唯一默认回落不误报缺', async () => {
    // (fin-service, UAT=2) 唯一默认账户 —— 声明行(username ref)同标签命中;
    // SIT 条目(default ref)按「system 内唯一回落」也命中(0059 默认按
    // (池, system) 唯一,跨标签共用是正常形态 —— 与后端 _pick_one 同口径)
    vi.mocked(authApi.listAll).mockResolvedValue([
      { id: 1, system: 'fin-service', envId: 2, username: 'merchant-b',
        isDefault: true },
    ] as never)
    const w = await mountPage()
    await enterEdit(w)
    // 声明行(fin-service.merchant-b)取用 merchant-b → 已装载
    expect(w.get('[data-testid="ec-ident-0-fin-service.merchant-b"]').text())
      .toContain('已装载')
    // 加入 SIT 行 → 取用自身(default ref)→ 跨标签唯一默认 → 已装载
    await pickAlias(w, 0, 'merchant-sit')
    expect(w.get('[data-testid="ec-ident-0-merchant-sit"]').text())
      .toContain('已装载')
    w.unmount()
  })

  it('缺账户 + 深链:池内无 ref 命中行 → 缺账户,深链按条目坐标预填', async () => {
    // 池内无 fin-service 账户 → 声明行(username ref merchant-b)缺账户
    vi.mocked(authApi.listAll).mockResolvedValue([] as never)
    const w = await mountPage()
    await enterEdit(w)
    expect(w.get('[data-testid="ec-ident-0-fin-service.merchant-b"]').text())
      .toContain('缺账户')
    expect(w.get('[data-testid="ec-ident-auth-fin-service.merchant-b"]')
      .attributes('href')).toBe('/auths?system=fin-service&envId=2')
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
      description: '',
      tags: [],
      systems: [{ service: 'legacy-svc', aliases: [], bindings: {}, carryOverrides: {} }],
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
    await w.get('[data-testid="ec-list-row-9"]').trigger('click')
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
    expect(w.get('[data-testid="ec-list-row-10"]').classes()).toContain('on')
    w.unmount()
  })

  it('删除:两步确认 → DELETE 后回落首行', async () => {
    ec.listExecConfigs.mockResolvedValue([
      { id: 7, name: '默认套', isDefault: true, systems: [] },
      { id: 9, name: '变体', isDefault: false, systems: [] },
    ])
    ec.deleteExecConfig.mockResolvedValue(undefined)
    const w = await mountPage()
    await w.get('[data-testid="ec-list-row-9"]').trigger('click')
    await w.get('[data-testid="ec-del"]').trigger('click')
    expect(ec.deleteExecConfig).not.toHaveBeenCalled()
    await w.get('[data-testid="ec-del-ok"]').trigger('click')
    await flushPromises()
    expect(ec.deleteExecConfig).toHaveBeenCalledWith(9)
    expect(w.get('[data-testid="ec-list-row-7"]').classes()).toContain('on')
    w.unmount()
  })

  it('重名 409 → detail.message 内联展示', async () => {
    // FE-08e:http 拦截器归一后错误是 Error(message 含 detail)——
    // 桩改真实形状(旧 response.data.detail 形状在真链路不可达)
    ec.createExecConfig.mockRejectedValue(Object.assign(
      new Error("执行配置名 'x' 已存在"),
      { status: 409, code: 'exec_config_name_exists' }))
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

  it('v4 Ping All:地址 ping + 绑定账户拨测,结果就地渲染 + 汇总', async () => {
    // merchant-b(换用条目,ref 默认)在个人池有默认账户(id=5)→ 拨测目标
    vi.mocked(authApi.listAll).mockResolvedValue([
      { id: 5, system: 'fin-service', envId: 2, username: 'merchant-b',
        isDefault: true },
    ] as never)
    // 地址 ping 成功,拨测失败 → 1/2
    vi.mocked(depApi.pingDeployment).mockResolvedValue(
      { ok: true, statusCode: 200, latencyMs: 45, message: 'HTTP 200 · 45ms' })
    vi.mocked(authApi.testConnection).mockResolvedValue(
      { ok: false, status_code: 401, message: '认证失败' })
    const w = await mountPage()
    await openTab(w, 'readiness')
    await w.get('[data-testid="ec-ping-all"]').trigger('click')
    await flushPromises()
    // 目标:配置内服务的部署行(id=1)+ 换用条目解析账户(id=5)
    expect(depApi.pingDeployment).toHaveBeenCalledWith(1)
    expect(authApi.testConnection).toHaveBeenCalledWith(5)
    // 就地渲染:枢纽①地址行 ping 徽章;枢纽②装载行拨测徽章
    expect(w.get('[data-testid="ec-dep-ping-fin-service-2"]').text())
      .toContain('200')
    expect(w.get('[data-testid="ec-slot-probe-merchant-b"]').text())
      .toContain('拨测失败')
    // 汇总 chip + warning toast
    expect(w.get('[data-testid="ec-ping-all-result"]').text()).toBe('1/2 正常')
    expect(toast.warning).toHaveBeenCalledWith('1 项检测失败')
    w.unmount()
  })

  it('v4 Ping All:无部署行且无已装载换用条目 → 不发检测,提示无目标', async () => {
    // crm 无部署行;默认布景无账户(拨测目标空)→ 双目标皆空
    setup([{ id: 14, name: '无目标配置', isDefault: true,
      systems: [{ service: 'crm', bindings: {}, carryOverrides: {} }] }])
    const w = await mountPage()
    await openTab(w, 'readiness')
    await w.get('[data-testid="ec-ping-all"]').trigger('click')
    await flushPromises()
    expect(depApi.pingDeployment).not.toHaveBeenCalled()
    expect(authApi.testConnection).not.toHaveBeenCalled()
    expect(toast.warning).toHaveBeenCalledWith(
      expect.stringContaining('没有可检测的目标'))
    w.unmount()
  })

  it('就绪度页签:地址矩阵就绪 + 条目缺账户预填深链 + 预览页签内嵌', async () => {
    const w = await mountPage()
    await openTab(w, 'readiness')
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
    // 预览页签:内嵌 pickable 预览(open 常真,execConfigId = 选定配置)
    await openTab(w, 'preview')
    expect(w.find('[data-testid="ec-preview-dialog"]').exists()).toBe(true)
    w.unmount()
  })

  it('就绪度页签:实例环境无部署行 → 并集出行(缺地址但登录口可见)', async () => {
    // SIT(1) 有 fin-service 实例但无部署地址;部署只有 UAT(2)
    vi.mocked(svcApi.listInstances).mockResolvedValue([
      { system: 'fin-service', envId: 1, envName: 'SIT', groupId: 'g-sit',
        tags: ['SIT'], loginUrl: 'http://sit-login', line: '', note: '',
        updatedAt: null },
    ])
    const w = await mountPage()
    await openTab(w, 'readiness')
    const sit = w.get('[data-testid="ec-dep-fin-service-1"]')
    expect(sit.text()).toContain('SIT')
    expect(sit.text()).toContain('http://sit-login')
    expect(sit.text()).toContain('缺地址')
    expect(w.get('[data-testid="ec-dep-fin-service-2"]').text()).toContain('就绪')
    w.unmount()
  })

  it('就绪度页签:条目 ref 命中个人池账户 → 已装载不出深链缺口', async () => {
    // merchant-b 条目 ref 默认 → (fin-service, UAT=2) 需默认账户
    vi.mocked(authApi.listAll).mockResolvedValue([
      { id: 1, system: 'fin-service', envId: 2, username: 'merchant-b',
        isDefault: true },
    ] as never)
    const w = await mountPage()
    await openTab(w, 'readiness')
    expect(w.find('[data-testid="ec-slot-miss-merchant-b"]').exists()).toBe(false)
    expect(w.text()).toContain('已装载')
    w.unmount()
  })

  it('就绪度页签:default ref 只认 is_default 账户(非默认行不算命中)', async () => {
    vi.mocked(authApi.listAll).mockResolvedValue([
      { id: 1, system: 'fin-service', envId: 2, username: 'merchant-b',
        isDefault: false },
    ] as never)
    const w = await mountPage()
    await openTab(w, 'readiness')
    expect(w.get('[data-testid="ec-slot-miss-merchant-b"]').text()).toContain('缺账户')
    w.unmount()
  })

  it('§8.10 移除已选:一并移除该行换用,保存载荷不含该条目', async () => {
    ec.updateExecConfig.mockResolvedValue(ROW)
    const w = await mountPage()
    await enterEdit(w)
    // 首载:声明行已选(存量推导)+ 换用 merchant-b
    expect(w.find('[data-testid="ec-ident-0-fin-service.merchant-b"]').exists())
      .toBe(true)
    await w.get('[data-testid="ec-unuse-0-fin-service.merchant-b"]').trigger('click')
    await flushPromises()
    // 不用即不换:行与换用控件一并消失,回空态提示
    expect(w.find('[data-testid="ec-ident-0-fin-service.merchant-b"]').exists())
      .toBe(false)
    expect(w.find('[data-testid="ec-swap-0-fin-service.merchant-b"]').exists())
      .toBe(false)
    expect(w.find('[data-testid="ec-use-hint"]').exists()).toBe(true)
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(ec.updateExecConfig).toHaveBeenCalledWith(7, {
      name: '商户B视角@UAT',
      description: '',
      tags: [],
      systems: [{
        service: 'fin-service',
        aliases: [],   // 圈定集空
        bindings: {},  // 换用随移除一并移除
        carryOverrides: { 'merchant.grade': 'B' },  // 存量 carry 不动
      }],
    })
    w.unmount()
  })

  it('§8.10 就绪度:未换用的所选条目也进装载面板(此前只看换用绑定)', async () => {
    // 圈定 merchant-sit(无换用、无账户)→ 面板出该行 + 缺账户 + 深链
    const CHOSEN: ExecConfigRow = {
      id: 15, name: '圈定无换用', isDefault: true,
      systems: [{ service: 'fin-service', aliases: ['merchant-sit'],
                  bindings: {}, carryOverrides: {} }],
    }
    setup([CHOSEN])
    const w = await mountPage()
    // 编辑页签只读态:已选回显
    expect(w.get('[data-testid="ec-view-slot-0-merchant-sit"]').text())
      .toContain('merchant-sit')
    await openTab(w, 'readiness')
    const row = w.get('[data-testid="ec-slot-row-merchant-sit"]')
    expect(row.text()).toContain('merchant-sit')
    expect(row.text()).not.toContain('换用')
    expect(w.get('[data-testid="ec-slot-miss-merchant-sit"]').text()).toContain('缺账户')
    expect(w.get('[data-testid="ec-goto-auth-merchant-sit"]').attributes('href'))
      .toBe('/auths?system=fin-service&envId=1')
    w.unmount()
  })

  it('就绪度页签:绑定条目的注册表状态按名定向检索(不再全量拉取)', async () => {
    const w = await mountPage()
    await openTab(w, 'readiness')
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

  it('节点卡头:主档说明/系统回显 + 服务子页深链(服务列表页签撤下后归位)', async () => {
    const w = await mountPage()
    const node = w.get('[data-testid="ec-node-0"]')
    expect(node.text()).toContain('fin-service')
    // 说明直读主档(services.description;service-meta 兼容层退役)
    expect(node.text()).toContain('交易核心服务')
    expect(w.get('[data-testid="ec-goto-faces-fin-service"]').attributes('href'))
      .toBe('/service-admin/fin-service?tab=faces')
    w.unmount()
  })

  it('v6 搜索加入:搜索词过滤候选 → 加入 → 明细行出现 + 保存载荷含新条目', async () => {
    ec.updateExecConfig.mockResolvedValue(ROW)
    const w = await mountPage()
    await enterEdit(w)
    // 搜索 'sit' → 候选只剩 merchant-sit
    await w.get('[data-testid="ec-pick-q-0"]').setValue('sit')
    await flushPromises()
    const pick = w.get('[data-testid="ec-pick-0"]').element as HTMLSelectElement
    expect(optgroupsOf(pick)).toEqual([['SIT', ['merchant-sit']]])
    // 加入 → 明细行出现
    await w.get('[data-testid="ec-pick-0"]').setValue('merchant-sit')
    await flushPromises()
    expect(w.find('[data-testid="ec-ident-0-merchant-sit"]').exists()).toBe(true)
    // 保存载荷:圈定集含新旧两条(存量推导 + 新加入)
    await w.get('[data-testid="ec-save"]').trigger('click')
    await flushPromises()
    expect(ec.updateExecConfig).toHaveBeenCalledWith(7, {
      name: '商户B视角@UAT',
      description: '',
      tags: [],
      systems: [{
        service: 'fin-service',
        // 末位 = 换用目标值(决策 1 阶段 1 自动写入圈定)
        aliases: ['fin-service.merchant-b', 'merchant-sit', 'merchant-b'],
        bindings: { 'fin-service.merchant-b': 'merchant-b' },
        carryOverrides: { 'merchant.grade': 'B' },
      }],
    })
    w.unmount()
  })

  it('v6 注册表截断:>200 未全量载入 → 提示去服务子页管理', async () => {
    vi.mocked(aliasApi.listAliases).mockResolvedValue({
      items: ALIASES.filter((a) => a.baseService === 'fin-service'),
      total: 300, page: 1, pageSize: 200,
    })
    const w = await mountPage()
    await enterEdit(w)
    expect(w.text()).toContain('注册表超过 200 条未全量载入')
    w.unmount()
  })

  it('就绪度页签:未登记的绑定条目 → 去该服务子页身份条目 tab 登记', async () => {
    vi.mocked(aliasApi.listAliases).mockResolvedValue({
      items: [], total: 0, page: 1, pageSize: 10,
    })
    const w = await mountPage()
    await openTab(w, 'readiness')
    await flushPromises()
    expect(w.get('[data-testid="ec-goto-faces-fin-service.merchant-b"]').attributes('href'))
      .toBe('/service-admin/fin-service?tab=faces')
    expect(w.get('[data-testid="ec-hub-bindings"]').text()).toContain('✕ 未登记')
    w.unmount()
  })

  it('页签:三页签默认编辑 + 就绪度缺口角标 + 切页签保留表单态', async () => {
    const w = await mountPage()
    // 默认编辑页签:节点卡可见,就绪度/预览不可见;服务列表页签已撤下
    expect(w.get('[data-testid="ec-tab-edit"]').classes()).toContain('on')
    expect(w.find('[data-testid="ec-node-0"]').exists()).toBe(true)
    expect(w.find('[data-testid="ec-hub"]').exists()).toBe(false)
    expect(w.find('[data-testid="ec-tab-services"]').exists()).toBe(false)
    // 就绪度角标:1 缺账户(merchant-b;地址行就绪)
    const badge = w.get('[data-testid="ec-tab-readiness"] .cnt')
    expect(badge.classes()).toContain('alert')
    expect(badge.text()).toBe('1')
    // 切换页签保留表单态:改名 + 节点进入编辑 → 切回,值仍在
    await enterMetaEdit(w)
    await w.get('[data-testid="ec-name"]').setValue('页签保留名')
    await enterEdit(w)
    await openTab(w, 'readiness')
    await openTab(w, 'edit')
    expect((w.get('[data-testid="ec-name"]').element as HTMLInputElement).value)
      .toBe('页签保留名')
    expect(w.find('[data-testid="ec-idents-0"]').exists()).toBe(true)
    w.unmount()
  })

  it('新建模式不显页签(恒编辑页签内容)', async () => {
    const w = await mountPage()
    await w.get('[data-testid="ec-new"]').trigger('click')
    expect(w.find('[data-testid="ec-tabs"]').exists()).toBe(false)
    // 新建即编辑态:名称输入可用;机制说明已收进页头问号(v8)
    expect(w.find('[data-testid="ec-name"]').exists()).toBe(true)
    expect(w.find('[data-testid="ec-mech"]').exists()).toBe(false)
    w.unmount()
  })

  it('v8/v8.1 节点状态徽章组统一贴服务选框(未圈选 / 条目·换用·装载同位置)', async () => {
    // 未圈选态
    setup([{ id: 31, name: '未圈定套', isDefault: false,
      systems: [{ service: 'fin-service', aliases: [],
                  bindings: {}, carryOverrides: {} }] }])
    const w = await mountPage()
    const titleRow = w.get('[data-testid="ec-node-0"] .node-title-row')
    expect(titleRow.text()).toContain('未圈选身份')
    expect(w.find('[data-testid="ec-node-unpicked-0"]').exists()).toBe(true)
    expect(w.find('[data-testid="ec-node-0"] .node-status').exists()).toBe(true)
    w.unmount()
    // 有圈定态:条目/换用/装载在同一位置(ROW = 1 条目 · 1 换用 · 1 缺装载)
    setup()
    const w2 = await mountPage()
    const titleRow2 = w2.get('[data-testid="ec-node-0"] .node-title-row')
    expect(titleRow2.text()).toContain('1 条目')
    expect(titleRow2.text()).toContain('1 换用')
    expect(titleRow2.text()).toContain('1 缺装载')
    w2.unmount()
  })
})

describe('FE-02 失败≠空态(旁路/条目面降级)', () => {
  it('旁路四面失败 → 降级横幅点名失败面,不静默伪装空数据', async () => {
    vi.mocked(authApi.listAll).mockRejectedValue(new Error('auth down'))
    vi.mocked(svcApi.listServices).mockRejectedValue(new Error('svc down'))
    vi.mocked(svcApi.listInstances).mockRejectedValue(new Error('inst down'))
    vi.mocked(scenApi.listScenarioOptions).mockRejectedValue(new Error('scen down'))
    const w = await mountPage()
    const banner = w.get('[data-testid="ec-bypass-degraded"]').text()
    expect(banner).toContain('账户(装载判定)')
    expect(banner).toContain('主档(服务选项)')
    expect(banner).toContain('实例(登录口)')
    expect(banner).toContain('场景(预览下拉)')
    w.unmount()
  })

  it('条目面失败 → 节点徽章显「条目读取失败」,不误报「未登记条目」', async () => {
    vi.mocked(aliasApi.listAliases).mockRejectedValue(new Error('alias down'))
    const w = await mountPage()
    expect(w.get('[data-testid="ec-node-alias-err-0"]').text()).toContain('条目读取失败')
    // 就绪度页签:取用条目解析不到 → 「读取失败」而非「未登记」
    await openTab(w, 'readiness')
    expect(w.text()).not.toContain('✕ 未登记')
    w.unmount()
  })
})
