/**
 * ServiceAdmin.vue — 服务注册(服务×环境地址矩阵 + 服务说明列):
 *   - 矩阵面全量(目录∪部署 = 服务全集);行 = 服务,列 = 环境,格 = 地址;
 *   - 说明列 = 服务级元数据(service-meta,读全员/写 ops.write),格内点击
 *     即编辑;
 *   - 服务名 → 子页 /service-admin/{服务}(身份面注册表已迁子页);
 *     「字段」= 子页字段默认值深链(?tab=fields);
 *   - 环境 chip 聚焦列(只显该环境缺地址的服务)+ 聚焦态环境管理条;
 *   - 缺格「缺 · 登记」就地补录;有地址格内行内编辑(含删除)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ServiceAdmin from '@/views/ServiceAdmin.vue'
import * as envApi from '@/api/environments'
import * as depApi from '@/api/deployments'
import * as metaApi from '@/api/service-meta'
import * as catalog from '@/utils/catalog-services'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const ENVS = [
  { id: 1, name: '测试', description: '', lines: {}, owner_id: null, is_default: true },
  { id: 2, name: '预发', description: '', lines: {}, owner_id: null, is_default: false },
]
const DEPS = [
  { id: 11, baseService: 'fin-service', envId: 1, baseUrl: 'http://fin-dev' },
]
const CATALOG = [
  { service: 'fin-service', system: 'fin' },
  { service: 'fin-report-service', system: 'fin' },
  { service: 'wms-service', system: 'wms' },
]

function setupBase() {
  vi.spyOn(catalog, 'loadCatalogEntries').mockResolvedValue(CATALOG)
  vi.spyOn(envApi, 'listEnvironments').mockResolvedValue(ENVS)
  vi.spyOn(depApi, 'listDeployments').mockResolvedValue(DEPS)
  vi.spyOn(metaApi, 'listServiceMeta').mockResolvedValue([
    { serviceName: 'fin-service', description: '交易核心服务,负责订单/支付', updatedAt: null },
  ])
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  setupBase()
})

async function mountPage() {
  const w = mount(ServiceAdmin, { global: { plugins: [createPinia()] } })
  await flushPromises()
  return w
}

// ══ 矩阵本体 ═══════════════════════════════════════════════════
describe('ServiceAdmin — 矩阵本体', () => {
  it('服务全集 = 目录∪部署成行;分区行;地址格/缺格分态', async () => {
    const w = await mountPage()
    // 目录 3 + 部署 0 新增 = 3 服务行
    for (const svc of ['fin-service', 'fin-report-service', 'wms-service']) {
      expect(w.find(`[data-testid="mx-row-${svc}"]`).exists()).toBe(true)
    }
    expect(w.find('[data-testid="svc-kind-sut"]').exists()).toBe(true)
    // 有地址:格显地址;缺:琥珀「缺 · 登记」
    expect(w.find('[data-testid="mx-cell-fin-service-1"]').text()).toContain('http://fin-dev')
    expect(w.find('[data-testid="mx-miss-fin-service-2"]').exists()).toBe(true)
    expect(w.find('[data-testid="mx-miss-fin-report-service-1"]').exists()).toBe(true)
    // 全局缺口计数在环境 chip 上(服务全集 3 − 已部署 1 = 缺2)
    expect(w.get('[data-testid="dep-env-1"]').text()).toContain('缺2')
    expect(w.get('[data-testid="dep-env-2"]').text()).toContain('缺3')
    w.unmount()
  })

  it('行序:缺口多的排前;svc-search 客户端收窄', async () => {
    const w = await mountPage()
    const rows = w.findAll('[data-testid^="mx-row-"]')
    // fin-report(0/2)与 wms(0/2)在 fin-service(1/2)前
    expect(rows[0].attributes('data-testid')).toBe('mx-row-fin-report-service')
    expect(rows[2].attributes('data-testid')).toBe('mx-row-fin-service')
    await w.find('[data-testid="svc-search"]').setValue('wms')
    await flushPromises()
    expect(w.findAll('[data-testid^="mx-row-"]')).toHaveLength(1)
    expect(w.find('[data-testid="mx-row-wms-service"]').exists()).toBe(true)
    w.unmount()
  })

  it('地址格点击 → 行内编辑保存 → updateDeployment(id, url)', async () => {
    vi.spyOn(depApi, 'updateDeployment').mockResolvedValue(
      { id: 11, baseService: 'fin-service', envId: 1, baseUrl: 'http://v2' })
    const w = await mountPage()
    await w.get('[data-testid="mx-cell-fin-service-1"]').trigger('click')
    await w.get('[data-testid="mx-url-fin-service-1"]').setValue('http://v2')
    await w.get('[data-testid="mx-save-fin-service-1"]').trigger('click')
    await flushPromises()
    expect(depApi.updateDeployment).toHaveBeenCalledWith(11, 'http://v2')
    // 保存后矩阵重拉(缺口计数同源更新)
    expect(depApi.listDeployments).toHaveBeenCalledTimes(2)
    w.unmount()
  })

  it('编辑态内删除地址 → deleteDeployment(id)', async () => {
    vi.spyOn(depApi, 'deleteDeployment').mockResolvedValue(undefined)
    const w = await mountPage()
    await w.get('[data-testid="mx-cell-fin-service-1"]').trigger('click')
    await w.get('[data-testid="mx-del-fin-service-1"]').trigger('click')
    await flushPromises()
    expect(depApi.deleteDeployment).toHaveBeenCalledWith(11)
    w.unmount()
  })

  it('缺格「缺 · 登记」→ 格内输入 → createDeployment({baseService, envId, baseUrl})', async () => {
    vi.spyOn(depApi, 'createDeployment').mockResolvedValue(
      { id: 12, baseService: 'wms-service', envId: 2, baseUrl: 'http://wms-uat' })
    const w = await mountPage()
    await w.get('[data-testid="mx-miss-wms-service-2"]').trigger('click')
    await w.get('[data-testid="mx-new-url-wms-service-2"]').setValue('http://wms-uat')
    await w.get('[data-testid="mx-register-wms-service-2"]').trigger('click')
    await flushPromises()
    expect(depApi.createDeployment).toHaveBeenCalledWith(
      { baseService: 'wms-service', envId: 2, baseUrl: 'http://wms-uat' })
    w.unmount()
  })

  it('环境 chip 聚焦:矩阵只显该环境缺地址的服务行 + 环境管理条在场;再点收起', async () => {
    const w = await mountPage()
    await w.get('[data-testid="dep-env-1"]').trigger('click')
    // 环境 1:fin-service 已有地址 → 行滤掉;缺的两行保留待补
    expect(w.find('[data-testid="mx-row-fin-service"]').exists()).toBe(false)
    expect(w.find('[data-testid="mx-row-wms-service"]').exists()).toBe(true)
    expect(w.find('[data-testid="dep-current"]').exists()).toBe(true)
    // 再点同 chip → 收起聚焦
    await w.get('[data-testid="dep-env-1"]').trigger('click')
    expect(w.find('[data-testid="mx-row-fin-service"]').exists()).toBe(true)
    expect(w.find('[data-testid="dep-current"]').exists()).toBe(false)
    w.unmount()
  })
})

// ══ 说明列(service_meta)══════════════════════════════════════
describe('ServiceAdmin — 说明列', () => {
  it('元数据回显;未登记的服务显「—」', async () => {
    const w = await mountPage()
    expect(w.get('[data-testid="meta-cell-fin-service"]').text()).toContain('交易核心服务')
    expect(w.get('[data-testid="meta-cell-wms-service"]').text()).toContain('—')
    w.unmount()
  })

  it('格内点击即编辑 → 保存 → putServiceMeta(serviceName, text)并回显', async () => {
    vi.spyOn(metaApi, 'putServiceMeta').mockResolvedValue(
      { serviceName: 'wms-service', description: '仓储服务', updatedAt: null })
    const w = await mountPage()
    await w.get('[data-testid="meta-cell-wms-service"]').trigger('click')
    await w.get('[data-testid="meta-input-wms-service"]').setValue('仓储服务')
    await w.get('[data-testid="meta-save-wms-service"]').trigger('click')
    await flushPromises()
    expect(metaApi.putServiceMeta).toHaveBeenCalledWith('wms-service', '仓储服务')
    expect(w.get('[data-testid="meta-cell-wms-service"]').text()).toContain('仓储服务')
    w.unmount()
  })

  it('服务名点击 → 子页 /service-admin/{服务};「字段」→ ?tab=fields 深链', async () => {
    const { createMemoryHistory, createRouter } = await import('vue-router')
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/service-admin', component: ServiceAdmin },
        { path: '/service-admin/:alias', component: { template: '<div />' } },
      ],
    })
    await router.push('/service-admin')
    await router.isReady()
    const w = mount(ServiceAdmin, { global: { plugins: [createPinia(), router] } })
    await flushPromises()
    await w.get('[data-testid="mx-svc-link-fin-service"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/service-admin/fin-service')

    await router.push('/service-admin')
    await flushPromises()
    await w.get('[data-testid="svc-config-wms-service"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/service-admin/wms-service?tab=fields')
    w.unmount()
  })
})

// ══ 环境管理(聚焦态)══════════════════════════════════════════
describe('ServiceAdmin — 环境管理', () => {
  it('置默认/取消默认 → 环境列表刷新', async () => {
    vi.spyOn(envApi, 'setDefaultEnvironment').mockResolvedValue(
      { ...ENVS[1], is_default: true })
    vi.spyOn(envApi, 'unsetDefaultEnvironment').mockResolvedValue(
      { ...ENVS[0], is_default: false })
    const w = await mountPage()
    await w.get('[data-testid="dep-env-1"]').trigger('click')
    await w.get('[data-testid="dep-unset-default"]').trigger('click')
    await flushPromises()
    expect(envApi.unsetDefaultEnvironment).toHaveBeenCalledWith(1)
    await w.get('[data-testid="dep-env-2"]').trigger('click')
    await w.get('[data-testid="dep-set-default"]').trigger('click')
    await flushPromises()
    expect(envApi.setDefaultEnvironment).toHaveBeenCalledWith(2)
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
    await w.get('[data-testid="dep-env-add-line"]').trigger('click')
    await w.get('[data-testid="dep-env-sys-0"]').setValue('fin')
    await w.get('[data-testid="dep-env-line-0"]').setValue('2.0')
    await w.get('[data-testid="dep-env-save"]').trigger('click')
    await flushPromises()
    expect(envApi.createEnvironment).toHaveBeenCalledWith(
      { name: 'UAT', description: '预发验收', lines: { fin: '2.0' } })
    // 建完聚焦新列(逐服务补地址的工作流)
    expect(w.get('[data-testid="dep-env-3"]').classes()).toContain('on')
    expect(w.find('[data-testid="dep-env-form-create"]').exists()).toBe(false)
    w.unmount()
  })

  it('编辑环境:回填 description/lines → PUT {description, lines}', async () => {
    vi.spyOn(envApi, 'listEnvironments').mockResolvedValue([
      { id: 1, name: '测试', description: '旧描述', lines: { fin: '1.0' },
        owner_id: null, is_default: true },
    ])
    vi.spyOn(envApi, 'updateEnvironment').mockResolvedValue(
      { id: 1, name: '测试', description: '新描述', lines: { fin: '2.0' },
        owner_id: null, is_default: true })
    const w = await mountPage()
    await w.get('[data-testid="dep-env-1"]').trigger('click')
    await w.get('[data-testid="dep-env-edit"]').trigger('click')
    expect(
      (w.get('[data-testid="dep-env-sys-0"]').element as HTMLInputElement).value,
    ).toBe('fin')
    await w.get('[data-testid="dep-env-desc"]').setValue('新描述')
    await w.get('[data-testid="dep-env-line-0"]').setValue('2.0')
    await w.get('[data-testid="dep-env-save"]').trigger('click')
    await flushPromises()
    expect(envApi.updateEnvironment).toHaveBeenCalledWith(
      1, { description: '新描述', lines: { fin: '2.0' } })
    w.unmount()
  })

  it('删除环境:两步确认 → DELETE 后退出聚焦', async () => {
    vi.spyOn(envApi, 'deleteEnvironment').mockResolvedValue(undefined)
    const w = await mountPage()
    await w.get('[data-testid="dep-env-1"]').trigger('click')
    await w.get('[data-testid="dep-env-del"]').trigger('click')
    expect(envApi.deleteEnvironment).not.toHaveBeenCalled()
    expect(w.text()).toContain('部署地址将一并删除')
    await w.get('[data-testid="dep-env-del-ok"]').trigger('click')
    await flushPromises()
    expect(envApi.deleteEnvironment).toHaveBeenCalledWith(1)
    expect(w.find('[data-testid="dep-current"]').exists()).toBe(false)
    expect(w.find('[data-testid="dep-env-del-ok"]').exists()).toBe(false)
    w.unmount()
  })

  it('无环境:缺格列不渲染,环境新建入口在场', async () => {
    vi.spyOn(envApi, 'listEnvironments').mockResolvedValue([])
    vi.spyOn(depApi, 'listDeployments').mockResolvedValue([])
    const w = await mountPage()
    expect(w.find('[data-testid="dep-env-new"]').exists()).toBe(true)
    expect(w.find('[data-testid="mx-miss-fin-service-1"]').exists()).toBe(false)
    w.unmount()
  })
})
