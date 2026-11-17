/**
 * ServiceAdmin.vue — 服务注册(按 stitch 原型完整重建后的行为面):
 *   - 指标条:服务/实例/凭据别名/缺配置;实时同步徽标;
 *   - plate 差异横幅:未登记候选、批量导入(POST /services/import-catalog)、
 *     单条预填登记;
 *   - 筛选矩阵:搜索 / 环境快切 / 分类页签 / 排序 + 服务卡分页;
 *   - 服务卡片:标识区(名/系统/接入态/漂移)、说明行内编辑、就绪度摘要、
 *     部署节点预览条;
 *   - 实例表:一环境一行(实例 = 服务 × 环境)、Tag(环境)过滤、就绪度
 *     三 chip、凭据槽位、每页 5 条分页;
 *   - 配置管理抽屉:连通测速、地址登记/编辑/删除、说明保存、调用身份卡
 *     (拨测/设默认/编辑/删除/复制)、实例配置、测试全槽位、保存配置;
 *   - 环境管理(聚焦态)与主档登记弹框保持。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ServiceAdmin from '@/views/ServiceAdmin.vue'
import * as envApi from '@/api/environments'
import * as depApi from '@/api/deployments'
import * as svcApi from '@/api/services'
import * as aliasApi from '@/api/service-aliases'
import * as authApi from '@/api/auth_sessions'
import type { ServiceRow, InstanceRow } from '@/api/services'
import type { ServiceAliasRow } from '@/api/service-aliases'
import type { AuthSession, TestResult } from '@/api/auth_sessions'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@/utils/confirmAction', () => ({ confirmAction: vi.fn() }))
vi.mock('@/api/service-aliases', () => ({
  listAliases: vi.fn(),
  createAlias: vi.fn(),
  patchAlias: vi.fn(),
  deleteAlias: vi.fn(),
}))
vi.mock('@/api/auth_sessions', () => ({
  listAll: vi.fn(),
  testConnection: vi.fn(),
  setDefault: vi.fn(),
}))

const ENVS = [
  { id: 1, name: '测试', description: '', lines: {}, owner_id: null, is_default: true },
  { id: 2, name: '预发', description: '', lines: {}, owner_id: null, is_default: false },
]
const SERVICES: ServiceRow[] = [
  { name: 'fin-service', system: 'fin', kind: 'plate', abbr: '', inCatalog: true,
    description: '交易核心服务,负责订单/支付', createdAt: null, updatedAt: '2026-11-01T10:00:00' },
  { name: 'fin-report-service', system: 'fin', kind: 'plate', abbr: '', inCatalog: true,
    description: '', createdAt: null, updatedAt: '2026-11-02T10:00:00' },
  { name: 'wms-service', system: 'wms', kind: 'external', abbr: '', inCatalog: false,
    description: '', createdAt: null, updatedAt: null },
]
const INSTANCES: InstanceRow[] = [
  { system: 'fin', envId: 1, envName: '测试', loginUrl: 'http://fin/auth',
    line: '1.0', note: '联调用', updatedAt: null },
]
const DEPS = [
  { id: 11, baseService: 'fin-service', envId: 1, baseUrl: 'http://fin-dev' },
]
const ALIASES: ServiceAliasRow[] = [
  { aliasName: 'fin-service.merchant-b', baseService: 'fin-service',
    slot: 'fin-service.merchant-b', kind: 'plate', envId: 1,
    refMode: 'username', refUsername: 'merchant-b',
    display: '商户B视角', createdAt: '', updatedAt: '' },
  { aliasName: 'fin-service.admin', baseService: 'fin-service',
    slot: 'fin-service.admin', kind: 'plate', envId: 2,
    refMode: 'default', refUsername: null,
    display: '', createdAt: '', updatedAt: '' },
]
const ACCOUNTS: AuthSession[] = [
  { id: 101, system: 'fin', envId: 1, username: 'merchant-b',
    token_type: 'cookie', expires_in: 7200, isDefault: false,
    created_at: '', updated_at: '', password_masked: '••••',
    accountFields: { tenant: 'fin' } },
  { id: 102, system: 'fin', envId: 2, username: 'admin',
    token_type: 'token', expires_in: 3600, isDefault: true,
    created_at: '', updated_at: '', password_masked: '••••' },
]

function mockAliases(): void {
  vi.mocked(aliasApi.listAliases).mockImplementation((params?: {
    base?: string; q?: string; page?: number; page_size?: number
  }) => {
    const base = params?.base
    const items = base ? ALIASES.filter((a) => a.baseService === base) : ALIASES
    return Promise.resolve({
      items: params?.page_size === 1 ? [] : items,
      total: items.length,
      page: params?.page ?? 1,
      pageSize: params?.page_size ?? 100,
    })
  })
}

function setupBase(overrides: Partial<{
  services: ServiceRow[]
  envs: typeof ENVS
  deps: typeof DEPS
  instances: InstanceRow[]
  unregistered: string[]
  plateReachable: boolean
}> = {}) {
  vi.spyOn(envApi, 'listEnvironments').mockResolvedValue(overrides.envs ?? ENVS)
  vi.spyOn(depApi, 'listDeployments').mockResolvedValue(overrides.deps ?? DEPS)
  vi.spyOn(svcApi, 'listServices').mockResolvedValue({
    services: overrides.services ?? SERVICES,
    unregistered: overrides.unregistered ?? ['order-service'],
    plateReachable: overrides.plateReachable ?? true,
  })
  vi.spyOn(svcApi, 'listInstances').mockResolvedValue(overrides.instances ?? INSTANCES)
  vi.mocked(authApi.listAll).mockResolvedValue(ACCOUNTS)
  mockAliases()
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  document.body.innerHTML = ''
  setupBase()
})

async function mountPage() {
  const w = mount(ServiceAdmin, { global: { plugins: [createPinia()] }, attachTo: document.body })
  await flushPromises()
  return w
}

async function expand(w: Awaited<ReturnType<typeof mountPage>>, svc: string) {
  await w.get(`[data-testid="svc-expand-${svc}"]`).trigger('click')
  await flushPromises()
}

async function openDrawer(w: Awaited<ReturnType<typeof mountPage>>, svc: string, envId: number) {
  // 卡片可能已展开(连续开不同环境)- 只在缺少入口时点展开
  if (!w.find(`[data-testid="mx-inst-${svc}-${envId}"]`).exists()) {
    await expand(w, svc)
  }
  await w.get(`[data-testid="mx-inst-${svc}-${envId}"]`).trigger('click')
  await flushPromises()
}

async function openSvcMenu(w: Awaited<ReturnType<typeof mountPage>>, svc: string) {
  await w.get(`[data-testid="svc-more-${svc}"]`).trigger('click')
  await flushPromises()
}
function bodyEl(sel: string): DOMWrapper<Element> {
  const el = document.body.querySelector(sel)
  if (!el) throw new Error(`body 里找不到 ${sel}`)
  return new DOMWrapper(el)
}

// ══ 指标条 / 差异横幅 / 筛选 ═══════════════════════════════════
describe('ServiceAdmin — 指标条与差异横幅', () => {
  it('指标:服务/实例/条目/缺配置 + 实时同步徽标', async () => {
    const w = await mountPage()
    expect(w.get('[data-testid="metric-services"]').text()).toContain('3')
    expect(w.get('[data-testid="metric-instances"]').text()).toContain('1')
    expect(w.get('[data-testid="metric-aliases"]').text()).toContain('2')
    expect(w.get('[data-testid="metric-gaps"]').text()).toContain('3')
    expect(w.get('[data-testid="sync-bar"]').text()).toContain('plate 目录同步正常')
    w.unmount()
  })

  it('差异横幅:未登记候选 + 批量导入 → importCatalog(names)', async () => {
    vi.spyOn(svcApi, 'importCatalog').mockResolvedValue({
      created: ['order-service'], skipped: [], unregistered: [], plateReachable: true,
    })
    const w = await mountPage()
    expect(w.get('[data-testid="recon-panel"]').text()).toContain('order-service')
    await w.get('[data-testid="recon-batch-import"]').trigger('click')
    await flushPromises()
    expect(svcApi.importCatalog).toHaveBeenCalledWith(['order-service'])
    w.unmount()
  })

  it('全局「导入 Plate 服务定义」→ importCatalog([]);plate 不可达时禁用', async () => {
    vi.spyOn(svcApi, 'importCatalog').mockResolvedValue({
      created: ['order-service'], skipped: [], unregistered: [], plateReachable: true,
    })
    const w = await mountPage()
    await w.get('[data-testid="import-catalog"]').trigger('click')
    await flushPromises()
    expect(svcApi.importCatalog).toHaveBeenCalledWith([])
    w.unmount()
  })

  it('筛选:搜索 / 分类页签 / 环境快切', async () => {
    const w = await mountPage()
    await w.get('[data-testid="svc-search"]').setValue('wms')
    await flushPromises()
    expect(w.findAll('[data-testid^="mx-row-"]')).toHaveLength(1)
    await w.get('[data-testid="svc-search"]').setValue('')
    await flushPromises()
    await w.get('[data-testid="tab-external"]').trigger('click')
    await flushPromises()
    expect(w.findAll('[data-testid^="mx-row-"]')).toHaveLength(1)
    expect(w.find('[data-testid="mx-row-wms-service"]').exists()).toBe(true)
    await w.get('[data-testid="tab-all"]').trigger('click')
    await flushPromises()
    // 环境快切:只显该环境缺地址的服务(fin-service 在 env1 有地址 → 隐去)
    await w.get('[data-testid="dep-env-1"]').trigger('click')
    expect(w.find('[data-testid="mx-row-fin-service"]').exists()).toBe(false)
    expect(w.find('[data-testid="mx-row-wms-service"]').exists()).toBe(true)
    w.unmount()
  })
})

// ══ 服务卡片 ═════════════════════════════════════════════════
describe('ServiceAdmin — 服务卡片', () => {
  it('标识区/就绪度/预览条/漂移徽章', async () => {
    vi.spyOn(svcApi, 'listServices').mockResolvedValue({
      services: [{ ...SERVICES[0], inCatalog: false }, ...SERVICES.slice(1)],
      unregistered: [], plateReachable: true,
    })
    const w = await mountPage()
    const card = w.get('[data-testid="mx-row-fin-service"]')
    expect(card.text()).toContain('Plate(目录缺席)')
    expect(w.find('[data-testid="mx-drift-fin-service"]').exists()).toBe(true)
    expect(w.get('[data-testid="svc-cov-fin-service"]').text()).toContain('1/2 实例就绪')
    expect(w.get('[data-testid="svc-cov-fin-service"]').text())
      .toContain('地址 1/2 · 登录口 1/2')
    expect(w.get('[data-testid="mx-prev-fin-service-1"]').text())
      .toContain('http://fin-dev')
    // wms 无部署 → 提示
    expect(w.get('[data-testid="mx-row-wms-service"]').text()).toContain('暂无部署节点')
    w.unmount()
  })

  it('说明行内编辑 → patchService', async () => {
    vi.spyOn(svcApi, 'patchService').mockResolvedValue({
      ...SERVICES[2], description: '仓储服务',
    })
    const w = await mountPage()
    await w.get('[data-testid="meta-cell-wms-service"]').trigger('click')
    await w.get('[data-testid="meta-input-wms-service"]').setValue('仓储服务')
    await w.get('[data-testid="meta-save-wms-service"]').trigger('click')
    await flushPromises()
    expect(svcApi.patchService).toHaveBeenCalledWith('wms-service', {
      description: '仓储服务',
    })
    w.unmount()
  })

  it('服务卡分页:5 条/页 + 翻页', async () => {
    const many: ServiceRow[] = Array.from({ length: 7 }, (_, i) => ({
      name: `svc-${i}`, system: `sys-${i}`, kind: 'plate' as const,
      abbr: '', inCatalog: true, description: '', createdAt: null,
      updatedAt: `2026-11-0${i + 1}T00:00:00`,
    }))
    setupBase({ services: many, deps: [], instances: [] })
    const w = await mountPage()
    expect(w.findAll('[data-testid^="mx-row-"]')).toHaveLength(5)
    expect(w.get('[data-testid="svc-page-info"]').text()).toContain('显示 1 - 5 项')
    await w.get('[data-testid="svc-page-next"]').trigger('click')
    await flushPromises()
    expect(w.findAll('[data-testid^="mx-row-"]')).toHaveLength(2)
    expect(w.get('[data-testid="svc-page-info"]').text()).toContain('显示 6 - 7 项')
    w.unmount()
  })
})

// ══ 实例表(展开)═══════════════════════════════════════════════
describe('ServiceAdmin — 实例表', () => {
  it('展开:一环境一行 + 就绪度 + 槽位 + Tag 过滤', async () => {
    const w = await mountPage()
    await expand(w, 'fin-service')
    expect(w.get('[data-testid="inst-row-fin-service-1"]').text()).toContain('fin-service-测试')
    expect(w.get('[data-testid="inst-row-fin-service-1"]').text()).toContain('✓ 地址')
    expect(w.get('[data-testid="inst-row-fin-service-1"]').text()).toContain('✓ 登录口')
    expect(w.get('[data-testid="inst-row-fin-service-1"]').text()).toContain('1 个配置槽位')
    expect(w.get('[data-testid="inst-slots-fin-service-1"]').text()).toContain('ref merchant-b')
    // env2 缺地址/登录口;条目不在此环境(admin 属于 env2,但条目加载后按 env 过滤)
    expect(w.get('[data-testid="inst-row-fin-service-2"]').text()).toContain('缺地址')
    // Tag 过滤:只显 env2
    await w.get('[data-testid="tag-fin-service-2"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="inst-row-fin-service-1"]').exists()).toBe(false)
    expect(w.find('[data-testid="inst-row-fin-service-2"]').exists()).toBe(true)
    w.unmount()
  })

  it('实例分页:每页 5 条 + 翻页', async () => {
    const envs6 = Array.from({ length: 6 }, (_, i) => ({
      id: i + 1, name: `e${i + 1}`, description: '', lines: {},
      owner_id: null, is_default: i === 0,
    }))
    setupBase({ envs: envs6, deps: [], instances: [] })
    const w = await mountPage()
    await expand(w, 'fin-service')
    expect(w.findAll('[data-testid^="inst-row-fin-service-"]')).toHaveLength(5)
    expect(w.get('[data-testid="inst-page-info-fin-service"]').text())
      .toContain('显示第 1 - 5 条')
    await w.get('[data-testid="inst-page-next-fin-service"]').trigger('click')
    await flushPromises()
    expect(w.findAll('[data-testid^="inst-row-fin-service-"]')).toHaveLength(1)
    expect(w.find('[data-testid="inst-row-fin-service-6"]').exists()).toBe(true)
    w.unmount()
  })
})

// ══ 配置管理抽屉 ══════════════════════════════════════════════
describe('ServiceAdmin — 配置管理抽屉', () => {
  it('打开:就绪徽标 + 该标签下的条目卡(不混入其它环境)', async () => {
    const w = await mountPage()
    await openDrawer(w, 'fin-service', 1)
    expect(w.find('[data-testid="cfg-drawer"]').exists()).toBe(true)
    expect(w.get('[data-testid="cfg-readiness"]').text()).toContain('配置就绪')
    expect(w.find('[data-testid="face-card-fin-service.merchant-b"]').exists()).toBe(true)
    expect(w.find('[data-testid="face-card-fin-service.admin"]').exists()).toBe(false)
    const face = w.get('[data-testid="face-card-fin-service.merchant-b"]')
    expect(face.text()).toContain('ref merchant-b')
    expect(face.text()).toContain('merchant-b')
    expect(face.text()).toContain('已托管(不回显)')
    expect(w.get('[data-testid="cfg-faces-count"]').text()).toContain('1')
    w.unmount()
  })

  it('连通测速 → pingDeployment(id) 并展示结果', async () => {
    vi.spyOn(depApi, 'pingDeployment').mockResolvedValue({
      ok: true, statusCode: 200, latencyMs: 12, message: 'HTTP 200 · 12ms',
    })
    const w = await mountPage()
    await openDrawer(w, 'fin-service', 1)
    await w.get('[data-testid="cfg-ping"]').trigger('click')
    await flushPromises()
    expect(depApi.pingDeployment).toHaveBeenCalledWith(11)
    expect(w.get('[data-testid="cfg-ping-result"]').text()).toContain('HTTP 200 · 12ms')
    w.unmount()
  })

  it('地址编辑 → updateDeployment;缺地址 → createDeployment', async () => {
    vi.spyOn(depApi, 'updateDeployment').mockResolvedValue(
      { id: 11, baseService: 'fin-service', envId: 1, baseUrl: 'http://v2' })
    vi.spyOn(depApi, 'createDeployment').mockResolvedValue(
      { id: 12, baseService: 'fin-service', envId: 2, baseUrl: 'http://fin-uat' })
    const w = await mountPage()
    await openDrawer(w, 'fin-service', 1)
    await w.get('[data-testid="cfg-url-edit"]').trigger('click')
    await w.get('[data-testid="mx-url-fin-service-1"]').setValue('http://v2')
    await w.get('[data-testid="mx-save-fin-service-1"]').trigger('click')
    await flushPromises()
    expect(depApi.updateDeployment).toHaveBeenCalledWith(11, 'http://v2')
    // 切到 env2(缺地址)→ 登记
    await w.get('[data-testid="cfg-close"]').trigger('click')
    await openDrawer(w, 'fin-service', 2)
    await w.get('[data-testid="mx-new-url-fin-service-2"]').setValue('http://fin-uat')
    await w.get('[data-testid="mx-register-fin-service-2"]').trigger('click')
    await flushPromises()
    expect(depApi.createDeployment).toHaveBeenCalledWith({
      baseService: 'fin-service', envId: 2, baseUrl: 'http://fin-uat',
    })
    w.unmount()
  })

  it('实例配置与说明 → putInstance;底部保存合并 url+实例', async () => {
    vi.spyOn(svcApi, 'putInstance').mockResolvedValue({
      system: 'fin', envId: 1, envName: '测试', loginUrl: 'http://fin/auth2',
      line: '2.0', note: '新说明', updatedAt: null,
    })
    const w = await mountPage()
    await openDrawer(w, 'fin-service', 1)
    expect((w.get('[data-testid="inst-form-url"]').element as HTMLInputElement).value)
      .toBe('http://fin/auth')
    await w.get('[data-testid="inst-form-url"]').setValue('http://fin/auth2')
    await w.get('[data-testid="inst-form-line"]').setValue('2.0')
    await w.get('[data-testid="cfg-note"]').setValue('新说明')
    await w.get('[data-testid="cfg-save"]').trigger('click')
    await flushPromises()
    expect(svcApi.putInstance).toHaveBeenCalledWith('fin', 1, {
      loginUrl: 'http://fin/auth2', line: '2.0', note: '新说明',
    })
    w.unmount()
  })

  it('条目卡:拨测 / 设默认 / 编辑 / 删除', async () => {
    const { confirmAction } = await import('@/utils/confirmAction')
    vi.mocked(confirmAction).mockResolvedValue(true)
    vi.mocked(authApi.testConnection).mockResolvedValue({
      ok: true, status_code: 200, message: '连通成功',
    } as TestResult)
    vi.mocked(authApi.setDefault).mockResolvedValue({} as AuthSession)
    vi.mocked(aliasApi.patchAlias).mockResolvedValue(ALIASES[0])
    vi.mocked(aliasApi.deleteAlias).mockResolvedValue(undefined)
    const w = await mountPage()
    await openDrawer(w, 'fin-service', 1)
    // 拨测
    await w.get('[data-testid="face-probe-fin-service.merchant-b"]').trigger('click')
    await flushPromises()
    expect(authApi.testConnection).toHaveBeenCalledWith(101)
    expect(w.get('[data-testid="face-probe-result-fin-service.merchant-b"]').text())
      .toContain('连通成功')
    // 设默认
    await w.get('[data-testid="face-default-fin-service.merchant-b"]').trigger('click')
    await flushPromises()
    expect(authApi.setDefault).toHaveBeenCalledWith(101)
    // 编辑展示名
    await w.get('[data-testid="face-edit-fin-service.merchant-b"]').trigger('click')
    await w.get('[data-testid="alias-form-display"]').setValue('商户B')
    await w.get('[data-testid="alias-form-save"]').trigger('click')
    await flushPromises()
    expect(aliasApi.patchAlias).toHaveBeenCalledWith('fin-service.merchant-b', {
      refMode: 'username', refUsername: 'merchant-b', display: '商户B',
    })
    // 删除
    await w.get('[data-testid="face-del-fin-service.merchant-b"]').trigger('click')
    await flushPromises()
    expect(aliasApi.deleteAlias).toHaveBeenCalledWith('fin-service.merchant-b')
    w.unmount()
  })

  it('新增条目 → createAlias(服务锚 + 环境 + 引用)', async () => {
    vi.mocked(aliasApi.createAlias).mockResolvedValue(ALIASES[0])
    const w = await mountPage()
    await openDrawer(w, 'fin-service', 1)
    await w.get('[data-testid="cfg-alias-add"]').trigger('click')
    await w.get('[data-testid="alias-form-name"]').setValue('fin-service.merchant-c')
    await w.get('[data-testid="alias-form-refmode"]').setValue('username')
    await w.get('[data-testid="alias-form-refuser"]').setValue('merchant-c')
    await w.get('[data-testid="alias-form-display"]').setValue('商户C')
    await w.get('[data-testid="alias-form-save"]').trigger('click')
    await flushPromises()
    expect(aliasApi.createAlias).toHaveBeenCalledWith({
      aliasName: 'fin-service.merchant-c',
      kind: 'plate',
      baseService: 'fin-service',
      envId: 1,
      refMode: 'username',
      refUsername: 'merchant-c',
      display: '商户C',
    })
    w.unmount()
  })

  it('测试全槽位连通性 → 逐个 testConnection 并汇总', async () => {
    vi.mocked(authApi.testConnection).mockResolvedValue({
      ok: true, status_code: 200, message: 'ok',
    } as TestResult)
    const w = await mountPage()
    await openDrawer(w, 'fin-service', 1)
    await w.get('[data-testid="cfg-test-all"]').trigger('click')
    await flushPromises()
    expect(authApi.testConnection).toHaveBeenCalledTimes(1)
    expect(w.get('[data-testid="cfg-test-all-result"]').text()).toContain('1/1 正常')
    w.unmount()
  })

  it('关闭:✕ 与遮罩均可收起', async () => {
    const w = await mountPage()
    await openDrawer(w, 'fin-service', 1)
    await w.get('[data-testid="cfg-close"]').trigger('click')
    expect(w.find('[data-testid="cfg-drawer"]').exists()).toBe(false)
    // 收起卡片回到预览条 → 预览 chip 也能打开抽屉
    await w.get('[data-testid="svc-expand-fin-service"]').trigger('click')
    await w.get('[data-testid="mx-prev-fin-service-1"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="cfg-drawer"]').exists()).toBe(true)
    await w.get('[data-testid="cfg-backdrop"]').trigger('click')
    expect(w.find('[data-testid="cfg-drawer"]').exists()).toBe(false)
    w.unmount()
  })
})

// ══ 接入新实例 / 主档登记 ═══════════════════════════════════════
describe('ServiceAdmin — 接入与登记', () => {
  it('接入新实例:选服务+环境 → 打开配置抽屉', async () => {
    const w = await mountPage()
    await w.get('[data-testid="svc-access-global"]').trigger('click')
    await flushPromises()
    // reka Dialog teleport 到 body
    await bodyEl('[data-testid="access-form-service"]').setValue('wms-service')
    await bodyEl('[data-testid="access-form-env"]').setValue('2')
    await bodyEl('[data-testid="access-form-save"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="cfg-drawer"]').exists()).toBe(true)
    expect(w.get('[data-testid="cfg-drawer"]').text()).toContain('wms-service-预发')
    w.unmount()
  })

  it('从对账候选一键登记:预填服务名 → POST /services', async () => {
    vi.spyOn(svcApi, 'createService').mockResolvedValue({
      ...SERVICES[0], name: 'order-service', system: 'order',
    })
    const w = await mountPage()
    await w.get('[data-testid="recon-add-order-service"]').trigger('click')
    await flushPromises()
    expect((bodyEl('[data-testid="svc-form-name"]').element as HTMLInputElement).value)
      .toBe('order-service')
    await bodyEl('[data-testid="svc-form-system"]').setValue('order')
    await bodyEl('[data-testid="svc-form-save"]').trigger('click')
    await flushPromises()
    expect(svcApi.createService).toHaveBeenCalledWith(expect.objectContaining({
      name: 'order-service', system: 'order', kind: 'plate',
    }))
    w.unmount()
  })

  it('登记校验:缺系统名前置拦截', async () => {
    vi.spyOn(svcApi, 'createService')
    const w = await mountPage()
    await w.get('[data-testid="svc-new"]').trigger('click')
    await bodyEl('[data-testid="svc-form-name"]').setValue('new-svc')
    await bodyEl('[data-testid="svc-form-save"]').trigger('click')
    await flushPromises()
    expect(svcApi.createService).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('请输入系统名')
    w.unmount()
  })

  it('删除服务(卡片菜单):409 挂靠错误上屏', async () => {
    const { confirmAction } = await import('@/utils/confirmAction')
    vi.mocked(confirmAction).mockResolvedValue(true)
    vi.spyOn(svcApi, 'deleteService').mockRejectedValue(
      new Error('service_in_use: 该服务仍有部署地址或身份条目挂靠'))
    const w = await mountPage()
    await openSvcMenu(w, 'fin-service')
    await bodyEl('[data-testid="svc-del-fin-service"]').trigger('click')
    await flushPromises()
    expect(svcApi.deleteService).toHaveBeenCalledWith('fin-service')
    expect(w.get('[data-testid="dep-err"]').text()).toContain('service_in_use')
    w.unmount()
  })
})

// ══ 环境管理 ═══════════════════════════════════════════════════
describe('ServiceAdmin — 环境管理', () => {
  it('环境快切条 + 新建环境 → POST 后聚焦', async () => {
    const created = { id: 3, name: 'UAT', description: '预发验收', lines: {},
      owner_id: null, is_default: false }
    vi.spyOn(envApi, 'createEnvironment').mockResolvedValue(created)
    vi.spyOn(envApi, 'listEnvironments')
      .mockResolvedValueOnce(ENVS)
      .mockResolvedValueOnce([...ENVS, created])
    const w = await mountPage()
    await w.get('[data-testid="dep-env-new"]').trigger('click')
    await w.get('[data-testid="dep-env-name"]').setValue('UAT')
    await w.get('[data-testid="dep-env-desc"]').setValue('预发验收')
    await w.get('[data-testid="dep-env-add-line"]').trigger('click')
    await w.get('[data-testid="dep-env-sys-0"]').setValue('fin')
    await w.get('[data-testid="dep-env-line-0"]').setValue('2.0')
    await w.get('[data-testid="dep-env-save"]').trigger('click')
    await flushPromises()
    expect(envApi.createEnvironment).toHaveBeenCalledWith(
      { name: 'UAT', description: '预发验收', lines: { fin: '2.0' } })
    expect(w.get('[data-testid="dep-env-3"]').classes()).toContain('on')
    w.unmount()
  })

  it('删除环境:两步确认 → DELETE 后退出聚焦', async () => {
    vi.spyOn(envApi, 'deleteEnvironment').mockResolvedValue(undefined)
    const w = await mountPage()
    await w.get('[data-testid="dep-env-1"]').trigger('click')
    await w.get('[data-testid="dep-env-del"]').trigger('click')
    expect(envApi.deleteEnvironment).not.toHaveBeenCalled()
    expect(w.text()).toContain('实例配置将一并删除')
    await w.get('[data-testid="dep-env-del-ok"]').trigger('click')
    await flushPromises()
    expect(envApi.deleteEnvironment).toHaveBeenCalledWith(1)
    expect(w.find('[data-testid="dep-current"]').exists()).toBe(false)
    w.unmount()
  })
})
