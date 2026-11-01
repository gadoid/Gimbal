/**
 * ServiceAliasDetail — 键详情(配套方案 §2.2)。核心契约:
 *   - 三种键身份:已登记别名(别名模式 + 凭证 tab)/ 目录服务(服务模式,
 *     无凭证 tab)/ 都 miss → missing 面板(不猜);
 *   - ?tab=credential 深链直达凭证 tab(认证管理反查面板的落点);
 *   - 字段默认值 tab 内嵌 ServiceBindingEditor(键 + base 透传)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ServiceAliasDetail from '@/views/ServiceAliasDetail.vue'
import * as aliasApi from '@/api/service-aliases'
import * as catalog from '@/utils/catalog-services'

vi.mock('@/api/service-aliases', () => ({
  listAliases: vi.fn(),
  listAllAliases: vi.fn(),
  listGrants: vi.fn(),
}))
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceNames: vi.fn(),
  loadCatalogEntries: vi.fn(),
}))
vi.mock('@/components/carry/ServiceBindingEditor.vue', () => ({
  default: {
    name: 'ServiceBindingEditor',
    props: ['serviceKey', 'baseService'],
    template: '<div data-testid="binding-editor-stub">{{ serviceKey }}|{{ baseService ?? "-" }}</div>',
  },
}))
vi.mock('@/components/integration/InboundPanel.vue', () => ({
  default: {
    name: 'InboundPanel',
    props: ['aliasName', 'inboundEnabled', 'callbackEnabled', 'callbackPath', 'canManage'],
    template: '<div data-testid="inbound-panel-stub">{{ aliasName }}|{{ inboundEnabled }}|{{ canManage }}</div>',
  },
}))

const aliases: aliasApi.ServiceAliasRow[] = [
  { aliasName: 'fin-service-uat', baseService: 'fin-service', kind: 'plate', baseUrl: 'https://uat.fin.local', environmentId: 1, environmentName: '测试',
    credentialAlias: 'uat-cred', ownerUserId: null, inboundEnabled: false, callbackEnabled: false, callbackPath: null, callbackSecretSet: false, createdAt: '', updatedAt: '' },
  { aliasName: 'fin-service', baseService: 'fin-service', kind: 'plate', baseUrl: null, environmentId: null, environmentName: null,
    credentialAlias: null, ownerUserId: null, inboundEnabled: false, callbackEnabled: false, callbackPath: null, callbackSecretSet: false, createdAt: '', updatedAt: '' },
  { aliasName: 'agent-sys', baseService: 'pay-service', kind: 'external', baseUrl: 'https://cb.example.local', environmentId: null, environmentName: null,
    credentialAlias: null, ownerUserId: null, inboundEnabled: true, callbackEnabled: true, callbackPath: '/gimbal/callback', callbackSecretSet: true, createdAt: '', updatedAt: '' },
]

async function makeRouter(path: string): Promise<Router> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/service-admin/:alias', component: ServiceAliasDetail },
      { path: '/service-admin', component: { template: '<div />' } },
      { path: '/auths', component: { template: '<div />' } },
      { path: '/services/:name', component: { template: '<div />' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  return router
}

async function mountDetail(path: string) {
  const router = await makeRouter(path)
  const pinia = createPinia()
  setActivePinia(pinia)
  const w = mount(ServiceAliasDetail, { global: { plugins: [router, pinia] } })
  await flushPromises()
  return { w, router }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(aliasApi.listAllAliases).mockResolvedValue(aliases)
  vi.mocked(catalog.loadCatalogServiceNames).mockResolvedValue(['fin-service', 'wms-service'])
})

describe('ServiceAliasDetail — 键身份判定', () => {
  it('别名模式:徽标 + 分组 + 凭证徽章 + 三层链说明;编辑器收到 别名键/base', async () => {
    const { w } = await mountDetail('/service-admin/fin-service-uat')
    expect(w.text()).toContain('别名详情')
    expect(w.text()).toContain('测试')
    // 原型 H-alias-detail:头部直接亮出凭证绑定状态(已绑定 = 绿字带别名)
    expect(w.find('[data-testid="cred-bound-badge"]').text()).toContain('uat-cred')
    expect(w.find('[data-testid="binding-editor-stub"]').text()).toBe('fin-service-uat|fin-service')
    expect(w.text()).toContain('精确命中本别名')
    w.unmount()
  })

  it('别名未绑凭证 → 头部红字「凭证未绑定」(原型 H-alias-detail)', async () => {
    const { w } = await mountDetail('/service-admin/fin-service')
    expect(w.find('[data-testid="cred-unbound-badge"]').text()).toContain('凭证未绑定')
    w.unmount()
  })

  it('服务模式:目录服务未登记为别名 → 无凭证 tab,base=自身', async () => {
    const { w } = await mountDetail('/service-admin/wms-service')
    expect(w.text()).toContain('服务详情')
    expect(w.text()).toContain('目录服务')
    expect(w.find('[data-testid="binding-editor-stub"]').text()).toBe('wms-service|wms-service')
    expect(w.text()).not.toContain('凭证绑定')
    w.unmount()
  })

  it('missing:既非别名也非目录服务 → 找不到面板,不猜', async () => {
    const { w } = await mountDetail('/service-admin/ghost-key')
    expect(w.text()).toContain('找不到')
    expect(w.find('[data-testid="binding-editor-stub"]').exists()).toBe(false)
    w.unmount()
  })
})

describe('ServiceAliasDetail — 凭证 tab', () => {
  it('?tab=credential 深链:直达凭证 tab,展示绑定凭证与解析语义', async () => {
    const { w } = await mountDetail('/service-admin/fin-service-uat?tab=credential')
    expect(w.text()).toContain('凭证绑定')
    expect(w.text()).toContain('uat-cred')
    expect(w.text()).toContain('执行者本人')
    w.unmount()
  })

  it('默认落在字段默认值 tab', async () => {
    const { w } = await mountDetail('/service-admin/fin-service-uat')
    expect(w.find('[data-testid="binding-editor-stub"]').exists()).toBe(true)
    expect(w.text()).not.toContain('凭证绑定')
    w.unmount()
  })
})

describe('ServiceAliasDetail — 入站与回调 tab(webhook 设计 v3 P1)', () => {
  it('external 别名:tab 存在,?tab=inbound 深链渲染三区块面板', async () => {
    const { w } = await mountDetail('/service-admin/agent-sys?tab=inbound')
    expect(w.find('[data-testid="tab-inbound"]').exists()).toBe(true)
    const panel = w.find('[data-testid="inbound-panel-stub"]')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain('agent-sys')
    w.unmount()
  })

  it('plate 别名:无入站 tab(webhook 设计 v3:入站身份只挂 external)', async () => {
    const { w } = await mountDetail('/service-admin/fin-service-uat')
    expect(w.find('[data-testid="tab-inbound"]').exists()).toBe(false)
    expect(w.find('[data-testid="inbound-panel-stub"]').exists()).toBe(false)
    w.unmount()
  })
})
