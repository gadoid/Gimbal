/**
 * ServiceAdmin.vue — 服务注册(M5 重排:卡片流 + 实例表 + 配置管理抽屉):
 *   - 服务全集 = 主档 services(注册簿制,不是 plate 目录镜像);目录只用于
 *     对账(未登记候选 / 漂移 / 不可达);
 *   - 一服务一卡(平铺不分组):标识区(名/系统 chip/接入态/漂移)+ 说明
 *     行内编辑 + 就绪度摘要(地址 x/y · 登录口 a/b)+ 部署节点预览条;
 *   - 展开实例表:实例 = 服务 × 环境,一环境一行(地址/登录口/就绪度);
 *   - 「服务配置管理」抽屉:实例端点(地址登记/编辑/删除)+ 实例配置
 *     (登录口/版本线,系统共享)+ 调用身份卡(只显引用);
 *   - 服务名 → 子页 /service-admin/{服务}(身份条目);登记/编辑/删除
 *     随卡片菜单;环境管理(聚焦态)不变。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ServiceAdmin from '@/views/ServiceAdmin.vue'
import * as envApi from '@/api/environments'
import * as depApi from '@/api/deployments'
import * as svcApi from '@/api/services'
import * as aliasApi from '@/api/service-aliases'
import type { ServiceAliasRow } from '@/api/service-aliases'
import type { ServiceRow, InstanceRow } from '@/api/services'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@/utils/confirmAction', () => ({ confirmAction: vi.fn() }))
vi.mock('@/api/service-aliases', () => ({ listAliases: vi.fn() }))

/** 抽屉调用身份面:按服务锚取条目(组件客户端按标签过滤)。 */
const FACES: ServiceAliasRow[] = [
  { aliasName: 'fin-service.merchant-b', baseService: 'fin-service',
    slot: 'fin-service.merchant-b', kind: 'plate', envId: 1,
    refMode: 'username', refUsername: 'merchant-b',
    display: '商户B', createdAt: '', updatedAt: '' },
  { aliasName: 'fin-service.admin', baseService: 'fin-service',
    slot: 'fin-service.admin', kind: 'plate', envId: 2,
    refMode: 'default', refUsername: null,
    display: '', createdAt: '', updatedAt: '' },
]

const ENVS = [
  { id: 1, name: '测试', description: '', lines: {}, owner_id: null, is_default: true },
  { id: 2, name: '预发', description: '', lines: {}, owner_id: null, is_default: false },
]
const SERVICES: ServiceRow[] = [
  { name: 'fin-service', system: 'fin', kind: 'plate', abbr: '', inCatalog: true,
    description: '交易核心服务,负责订单/支付', createdAt: null, updatedAt: null },
  { name: 'fin-report-service', system: 'fin', kind: 'plate', abbr: '', inCatalog: true,
    description: '', createdAt: null, updatedAt: null },
  { name: 'wms-service', system: 'wms', kind: 'external', abbr: '', inCatalog: false,
    description: '', createdAt: null, updatedAt: null },
]
const INSTANCES: InstanceRow[] = [
  { system: 'fin', envId: 1, envName: '测试', loginUrl: 'http://fin/auth',
    line: '1.0', note: '', updatedAt: null },
]
const DEPS = [
  { id: 11, baseService: 'fin-service', envId: 1, baseUrl: 'http://fin-dev' },
]

function setupBase() {
  vi.spyOn(envApi, 'listEnvironments').mockResolvedValue(ENVS)
  vi.spyOn(depApi, 'listDeployments').mockResolvedValue(DEPS)
  vi.spyOn(svcApi, 'listServices').mockResolvedValue({
    services: SERVICES, unregistered: ['order-service'], plateReachable: true,
  })
  vi.spyOn(svcApi, 'listInstances').mockResolvedValue(INSTANCES)
  // 工厂 mock 会被 restoreAllMocks 清实现 → 每例在此重挂
  vi.mocked(aliasApi.listAliases).mockResolvedValue({
    items: FACES, total: FACES.length, page: 1, pageSize: 200,
  })
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

/** 展开某服务的实例表(卡片流默认收起)。 */
async function expand(w: Awaited<ReturnType<typeof mountPage>>, svc: string) {
  await w.get(`[data-testid="svc-expand-${svc}"]`).trigger('click')
  await flushPromises()
}

/** 打开某 (服务, 环境) 的配置管理抽屉(经实例表入口)。 */
async function openDrawer(w: Awaited<ReturnType<typeof mountPage>>, svc: string, envId: number) {
  await expand(w, svc)
  await w.get(`[data-testid="mx-inst-${svc}-${envId}"]`).trigger('click')
  await flushPromises()
  return w.get('[data-testid="cfg-drawer"]')
}

/** reka 下拉菜单 teleport 到 body → 先开菜单再取项。 */
async function openSvcMenu(w: Awaited<ReturnType<typeof mountPage>>, svc: string) {
  await w.get(`[data-testid="svc-more-${svc}"]`).trigger('click')
  await flushPromises()
}
function bodyEl(sel: string): DOMWrapper<Element> {
  const el = document.body.querySelector(sel)
  if (!el) throw new Error(`body 里找不到 ${sel}`)
  return new DOMWrapper(el)
}

// ══ 卡片流本体 ═════════════════════════════════════════════════
describe('ServiceAdmin — 服务卡片流', () => {
  it('主档成卡 + 系统 chip 在场 + 对账:external 不判漂移、目录未登记候选在场', async () => {
    const w = await mountPage()
    for (const svc of ['fin-service', 'fin-report-service', 'wms-service']) {
      expect(w.find(`[data-testid="mx-row-${svc}"]`).exists()).toBe(true)
    }
    // 标识区带系统 chip(卡片流平铺,不再按 system 分组表头)
    expect(w.get('[data-testid="mx-row-fin-service"]').text()).toContain('fin')
    expect(w.get('[data-testid="mx-row-wms-service"]').text()).toContain('第三方')
    expect(w.get('[data-testid="mx-row-fin-service"]').text()).toContain('plate 已同步')
    // external 不参与对账 → 无漂移标记
    expect(w.find('[data-testid="mx-drift-wms-service"]').exists()).toBe(false)
    // 目录未登记候选 + 点击预填新建
    expect(w.get('[data-testid="recon-add-order-service"]').text()).toContain('order-service')
    w.unmount()
  })

  it('plate 行不在目录 → 漂移徽章(testid 绑定到服务名)', async () => {
    vi.spyOn(svcApi, 'listServices').mockResolvedValue({
      services: [{ ...SERVICES[0], inCatalog: false }],
      unregistered: [], plateReachable: true,
    })
    const w = await mountPage()
    expect(w.find('[data-testid="mx-drift-fin-service"]').exists()).toBe(true)
    expect(w.find('[data-testid="mx-drift-fin-report-service"]').exists()).toBe(false)
    w.unmount()
  })

  it('收起态部署节点预览条:逐环境 url/缺;点击直达配置抽屉', async () => {
    const w = await mountPage()
    expect(w.get('[data-testid="mx-prev-fin-service-1"]').text())
      .toContain('http://fin-dev')
    expect(w.get('[data-testid="mx-prev-fin-service-2"]').text()).toContain('缺')
    await w.get('[data-testid="mx-prev-fin-service-1"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="cfg-drawer"]').exists()).toBe(true)
    w.unmount()
  })

  it('卡头就绪度摘要:地址 x/y · 登录口 a/b(系统维共享)', async () => {
    const w = await mountPage()
    expect(w.get('[data-testid="svc-cov-fin-service"]').text())
      .toContain('地址 1/2')
    expect(w.get('[data-testid="svc-cov-fin-service"]').text())
      .toContain('登录口 1/2')
    expect(w.get('[data-testid="svc-cov-wms-service"]').text())
      .toContain('地址 0/2')
    w.unmount()
  })

  it('卡序:缺口多的排前;svc-search 客户端收窄(按名/系统)', async () => {
    const w = await mountPage()
    const cards = w.findAll('[data-testid^="mx-row-"]')
    // 缺口降序 → 名字升序:fin-report(0/2)、wms(0/2)在前,fin-service(1/2)殿后
    expect(cards[0].attributes('data-testid')).toBe('mx-row-fin-report-service')
    expect(cards[1].attributes('data-testid')).toBe('mx-row-wms-service')
    expect(cards[2].attributes('data-testid')).toBe('mx-row-fin-service')
    await w.get('[data-testid="svc-search"]').setValue('wms')
    await flushPromises()
    expect(w.findAll('[data-testid^="mx-row-"]')).toHaveLength(1)
    expect(w.find('[data-testid="mx-row-wms-service"]').exists()).toBe(true)
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

  it('登记校验:缺系统名前置拦截,不发请求', async () => {
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

  it('编辑说明 → patchService(name, {description}) 并回显', async () => {
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
    expect(w.get('[data-testid="meta-cell-fin-service"]').text())
      .toContain('交易核心服务')
    w.unmount()
  })

  it('删除实例(卡片菜单):确认后 DELETE;有挂靠 409 错误上屏', async () => {
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

// ══ 实例表(卡内展开)═══════════════════════════════════════════
describe('ServiceAdmin — 实例表(展开)', () => {
  it('展开 → 一环境一行:地址/登录口/就绪度分态;环境缺地址计数', async () => {
    const w = await mountPage()
    // 环境 chip 计数(主档 3 服务;环境1 已部署 1 → 缺2;环境2 全缺 → 缺3)
    expect(w.get('[data-testid="dep-env-1"]').text()).toContain('缺2')
    expect(w.get('[data-testid="dep-env-2"]').text()).toContain('缺3')
    await expand(w, 'fin-service')
    expect(w.get('[data-testid="mx-cell-fin-service-1"]').text())
      .toContain('http://fin-dev')
    expect(w.find('[data-testid="mx-miss-fin-service-2"]').exists()).toBe(true)
    // 就绪度:环境1 双绿(地址 + 登录口);环境2 双缺
    const row1 = w.get('[data-testid="inst-row-fin-service-1"]').text()
    expect(row1).toContain('✓ 地址')
    expect(row1).toContain('✓ 登录口')
    const row2 = w.get('[data-testid="inst-row-fin-service-2"]').text()
    expect(row2).toContain('✗ 地址')
    expect(row2).toContain('✗ 登录口')
    // 配置入口:登录口已配 = ready
    expect(w.get('[data-testid="mx-inst-fin-service-1"]').classes()).toContain('ready')
    expect(w.get('[data-testid="mx-inst-fin-service-2"]').classes()).not.toContain('ready')
    w.unmount()
  })
})

// ══ 服务配置管理抽屉 ════════════════════════════════════════════
describe('ServiceAdmin — 配置管理抽屉', () => {
  it('实例端点:已有地址 → 编辑保存 updateDeployment(id, url)', async () => {
    vi.spyOn(depApi, 'updateDeployment').mockResolvedValue(
      { id: 11, baseService: 'fin-service', envId: 1, baseUrl: 'http://v2' })
    const w = await mountPage()
    const drawer = await openDrawer(w, 'fin-service', 1)
    expect(drawer.text()).toContain('http://fin-dev')
    await w.get('[data-testid="cfg-url-edit"]').trigger('click')
    await w.get('[data-testid="mx-url-fin-service-1"]').setValue('http://v2')
    await w.get('[data-testid="mx-save-fin-service-1"]').trigger('click')
    await flushPromises()
    expect(depApi.updateDeployment).toHaveBeenCalledWith(11, 'http://v2')
    w.unmount()
  })

  it('实例端点:缺地址 → 登记 createDeployment({baseService, envId, baseUrl})', async () => {
    vi.spyOn(depApi, 'createDeployment').mockResolvedValue(
      { id: 12, baseService: 'wms-service', envId: 2, baseUrl: 'http://wms-uat' })
    const w = await mountPage()
    await openDrawer(w, 'wms-service', 2)
    await w.get('[data-testid="mx-new-url-wms-service-2"]').setValue('http://wms-uat')
    await w.get('[data-testid="mx-register-wms-service-2"]').trigger('click')
    await flushPromises()
    expect(depApi.createDeployment).toHaveBeenCalledWith(
      { baseService: 'wms-service', envId: 2, baseUrl: 'http://wms-uat' })
    w.unmount()
  })

  it('实例端点:删除地址 → deleteDeployment(id)', async () => {
    vi.spyOn(depApi, 'deleteDeployment').mockResolvedValue(undefined)
    const w = await mountPage()
    await openDrawer(w, 'fin-service', 1)
    await w.get('[data-testid="cfg-url-edit"]').trigger('click')
    await w.get('[data-testid="mx-del-fin-service-1"]').trigger('click')
    await flushPromises()
    expect(depApi.deleteDeployment).toHaveBeenCalledWith(11)
    w.unmount()
  })

  it('实例配置:预填实例 → putInstance(system, envId, {...})', async () => {
    vi.spyOn(svcApi, 'putInstance').mockResolvedValue({
      system: 'fin', envId: 1, envName: '测试', loginUrl: 'http://fin/auth2',
      line: '2.0', note: '新实例', updatedAt: null,
    })
    const w = await mountPage()
    await openDrawer(w, 'fin-service', 1)
    expect((w.get('[data-testid="inst-form-url"]').element as HTMLInputElement).value)
      .toBe('http://fin/auth')
    await w.get('[data-testid="inst-form-url"]').setValue('http://fin/auth2')
    await w.get('[data-testid="inst-form-line"]').setValue('2.0')
    await w.get('[data-testid="inst-form-note"]').setValue('新实例')
    await w.get('[data-testid="inst-form-save"]').trigger('click')
    await flushPromises()
    expect(svcApi.putInstance).toHaveBeenCalledWith('fin', 1, {
      loginUrl: 'http://fin/auth2', line: '2.0', note: '新实例',
    })
    w.unmount()
  })

  it('调用身份卡:该标签下的条目只显引用与可见性(不在场的不列)', async () => {
    const w = await mountPage()
    await openDrawer(w, 'fin-service', 1)
    // env1 → merchant-b(username ref);env2 的 admin 不混入
    expect(w.find('[data-testid="cfg-face-fin-service.merchant-b"]').exists()).toBe(true)
    expect(w.find('[data-testid="cfg-face-fin-service.admin"]').exists()).toBe(false)
    expect(w.get('[data-testid="cfg-face-fin-service.merchant-b"]').text())
      .toContain('ref merchant-b')
    // 子页管理入口在场(维护留在子页,抽屉只读)
    expect(w.get('[data-testid="cfg-faces-link"]').text()).toContain('子页管理')
    w.unmount()
  })

  it('关闭抽屉:✕ 与遮罩均可收起', async () => {
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

// ══ 环境管理(聚焦态)══════════════════════════════════════════
describe('ServiceAdmin — 环境管理', () => {
  it('环境 chip 聚焦:只显该环境缺地址的服务卡 + 环境管理条在场;再点收起', async () => {
    const w = await mountPage()
    await w.get('[data-testid="dep-env-1"]').trigger('click')
    expect(w.find('[data-testid="mx-row-fin-service"]').exists()).toBe(false)
    expect(w.find('[data-testid="mx-row-wms-service"]').exists()).toBe(true)
    expect(w.find('[data-testid="dep-current"]').exists()).toBe(true)
    await w.get('[data-testid="dep-env-1"]').trigger('click')
    expect(w.find('[data-testid="mx-row-fin-service"]').exists()).toBe(true)
    expect(w.find('[data-testid="dep-current"]').exists()).toBe(false)
    w.unmount()
  })

  it('新建环境:name/description/lines → POST 后聚焦新列', async () => {
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
