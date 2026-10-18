/**
 * ServiceAdmin.vue — 服务信息管理(P1 唯一净新增页面):
 *   - 左栏系统→服务两层树(只到服务级),右侧数字 = 已登记别名数;
 *   - 顶部分组 chip 筛选(不选服务跨服务筛,选了服务在服务内筛);
 *   - 「服务级默认」行 = aliasName === baseService 的真实行打 tag;
 *   - 登记/编辑/删除走 api;admin 写面。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import ServiceAdmin from '@/views/ServiceAdmin.vue'
import * as api from '@/api/service-aliases'
import * as authApi from '@/api/auth_sessions'
import * as catalog from '@/utils/catalog-services'
import * as confirmModule from '@/utils/confirmAction'
import * as envApi from '@/api/environments'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const aliases: api.ServiceAliasRow[] = [
  { aliasName: 'fin-service', baseService: 'fin-service', kind: 'plate', baseUrl: null, environmentId: null, environmentName: null,
    credentialAlias: null, ownerUserId: null, createdAt: '', updatedAt: '' },
  { aliasName: 'fin-service-uat', baseService: 'fin-service', kind: 'plate', baseUrl: 'https://uat.fin.local', environmentId: 1, environmentName: '测试',
    credentialAlias: 'uat-cred', ownerUserId: null, createdAt: '', updatedAt: '' },
  { aliasName: 'wms-service-pre', baseService: 'wms-service', kind: 'plate', baseUrl: null, environmentId: 1, environmentName: '预发',
    credentialAlias: null, ownerUserId: 7, createdAt: '', updatedAt: '' },
]

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  vi.spyOn(api, 'listAllAliases').mockResolvedValue(aliases)
  vi.spyOn(authApi, 'listAll').mockResolvedValue([
    { alias: 'uat-cred' } as never,
  ])
  vi.spyOn(envApi, 'listEnvironments').mockResolvedValue([
    { id: 1, name: '测试', description: '', visibility: 'public', lines: {}, ownerId: null },
    { id: 2, name: '预发', description: '', visibility: 'public', lines: {}, ownerId: null },
  ])
  vi.spyOn(catalog, 'loadCatalogEntries').mockResolvedValue([
    { service: 'fin-service', system: 'fin' },
    { service: 'fin-report-service', system: 'fin' },
    { service: 'wms-service', system: 'wms' },
  ])
})

async function mountPage() {
  const w = mount(ServiceAdmin, { global: { plugins: [createPinia()] } })
  await flushPromises()
  return w
}

it('详情入口:别名行「详情」与树「字段」都进键详情路由(配套方案 §2.2)', async () => {
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

  await w.find('[data-testid="alias-detail-fin-service-uat"]').trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/service-admin/fin-service-uat')

  await router.push('/service-admin')
  await flushPromises()
  await w.find('[data-testid="svc-config-wms-service"]').trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/service-admin/wms-service')
  w.unmount()
})

it('左栏系统→服务两层;右侧数字 = 已登记别名数', async () => {
  const w = await mountPage()
  expect(w.find('[data-testid="svc-tree-fin-service"]').text()).toContain('2')
  expect(w.find('[data-testid="svc-tree-wms-service"]').text()).toContain('1')
  expect(w.find('[data-testid="svc-tree-fin-report-service"]').text()).toContain('0')
  // 三个别名全列出
  expect(w.findAll('[data-testid^="alias-row-"]')).toHaveLength(3)
})

it('服务级默认行打 tag;归属列区分团队/个人', async () => {
  const w = await mountPage()
  const finRow = w.find('[data-testid="alias-row-fin-service"]').text()
  expect(finRow).toContain('服务级默认')
  expect(w.find('[data-testid="alias-row-fin-service-uat"]').text()).not.toContain('服务级默认')
  expect(w.find('[data-testid="alias-row-wms-service-pre"]').text()).toContain('个人(#7)')
  expect(w.find('[data-testid="alias-row-fin-service-uat"]').text()).toContain('团队共享')
})

it('点树选服务 → 只看该服务;分组 chip 叠加筛选', async () => {
  const w = await mountPage()
  await w.find('[data-testid="svc-tree-fin-service"]').trigger('click')
  expect(w.findAll('[data-testid^="alias-row-"]')).toHaveLength(2)
  // 服务内分组:只有「测试」一个 chip
  await w.find('[data-testid="alias-chip-测试"]').trigger('click')
  expect(w.findAll('[data-testid^="alias-row-"]')).toHaveLength(1)
  expect(w.find('[data-testid="alias-row-fin-service-uat"]').exists()).toBe(true)
})

it('登记调用 createAlias 并重载(URL 必填,缺 URL 登记钮不可点);编辑回填且别名不可改', async () => {
  const create = vi.spyOn(api, 'createAlias').mockResolvedValue(aliases[1])
  const w = await mountPage()
  await w.find('[data-testid="svc-tree-fin-service"]').trigger('click')
  await w.find('[data-testid="alias-name-input"]').setValue('prod2')
  // V5(B):分组输入已退役(归属环境经下拉选择);未选择 → null
  // URL 必填(2026-09-23):没填时登记钮禁用,不发起请求
  expect((w.find('[data-testid="alias-save"]').element as HTMLButtonElement).disabled).toBe(true)
  await w.find('[data-testid="alias-url-input"]').setValue('https://prod.mall.local')
  await w.find('[data-testid="alias-save"]').trigger('click')
  await flushPromises()
  expect(create).toHaveBeenCalledWith({
    aliasName: 'fin-service-prod2', baseUrl: 'https://prod.mall.local', environmentId: null, credentialAlias: null, kind: 'plate', baseService: null,
  })
  expect(api.listAllAliases).toHaveBeenCalledTimes(2)

  await w.find('[data-testid="alias-edit-fin-service-uat"]').trigger('click')
  const nameInput = w.find('[data-testid="alias-name-input"]')
  expect((nameInput.element as HTMLInputElement).value).toBe('uat')
  expect((nameInput.element as HTMLInputElement).disabled).toBe(true)
})

it('前缀槽常驻:未选显「服务」占位;点选只换槽文字、后缀随身;取消选中剥前缀;编辑态槽显所属服务', async () => {
  const create = vi.spyOn(api, 'createAlias').mockResolvedValue(aliases[1])
  const w = await mountPage()
  await w.find('[data-testid="alias-url-input"]').setValue('https://x.fin.local')
  // 未选服务:槽占位「服务」,无基不可提交(槽恒在,输入框位置不跳)
  expect(w.find('[data-testid="alias-prefix"]').text()).toBe('服务名')
  expect((w.find('[data-testid="alias-save"]').element as HTMLButtonElement).disabled).toBe(true)
  const nameInput = w.find('[data-testid="alias-name-input"]')
  await nameInput.setValue('uat2')   // 无基时暂存裸后缀
  await w.find('[data-testid="svc-tree-fin-service"]').trigger('click')
  expect(w.find('[data-testid="alias-prefix"]').text()).toBe('fin-service-')
  expect((nameInput.element as HTMLInputElement).value).toBe('uat2')   // 后缀随身
  expect((w.find('[data-testid="alias-save"]').element as HTMLButtonElement).disabled).toBe(false)
  // 换服务:槽文字换,后缀留
  await w.find('[data-testid="svc-tree-wms-service"]').trigger('click')
  expect(w.find('[data-testid="alias-prefix"]').text()).toBe('wms-service-')
  expect((nameInput.element as HTMLInputElement).value).toBe('uat2')
  // 取消选中:槽回占位,输入框只剩后缀,无基再次不可提交
  await w.find('[data-testid="svc-tree-wms-service"]').trigger('click')
  expect(w.find('[data-testid="alias-prefix"]').text()).toBe('服务名')
  expect((nameInput.element as HTMLInputElement).value).toBe('uat2')
  expect((w.find('[data-testid="alias-save"]').element as HTMLButtonElement).disabled).toBe(true)
  // 选回并保存:提交完整全串
  await w.find('[data-testid="svc-tree-fin-service"]').trigger('click')
  await w.find('[data-testid="alias-save"]').trigger('click')
  await flushPromises()
  expect(create).toHaveBeenCalledWith({
    aliasName: 'fin-service-uat2', baseUrl: 'https://x.fin.local', environmentId: null, credentialAlias: null, kind: 'plate', baseService: null,
  })
  // 编辑态:槽显该别名所属服务,输入框只读展示后缀
  await w.find('[data-testid="alias-edit-fin-service-uat"]').trigger('click')
  expect(w.find('[data-testid="alias-prefix"]').text()).toBe('fin-service-')
  expect((nameInput.element as HTMLInputElement).value).toBe('uat')
  expect((nameInput.element as HTMLInputElement).disabled).toBe(true)
  w.unmount()
})

it('删除走确认对话框;取消不动', async () => {
  const del = vi.spyOn(api, 'deleteAlias').mockResolvedValue(undefined)
  vi.spyOn(confirmModule, 'confirmAction').mockResolvedValue(false)
  const w = await mountPage()
  await w.find('[data-testid="alias-del-fin-service-uat"]').trigger('click')
  await flushPromises()
  expect(del).not.toHaveBeenCalled()

  vi.spyOn(confirmModule, 'confirmAction').mockResolvedValue(true)
  await w.find('[data-testid="alias-del-fin-service-uat"]').trigger('click')
  await flushPromises()
  expect(del).toHaveBeenCalledWith('fin-service-uat')
})

// ── b2.5(归一 v1.0 §3.4/§1.6):kind 分区 + external base_service 下拉 ──
describe('ServiceAdmin — b2.5 kind 分区与 external base_service', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.spyOn(api, 'listAllAliases').mockResolvedValue(aliases)
    vi.spyOn(authApi, 'listAll').mockResolvedValue([])
    vi.spyOn(envApi, 'listEnvironments').mockResolvedValue([])
    vi.spyOn(catalog, 'loadCatalogEntries').mockResolvedValue([
      { service: 'fin-service', system: 'fin', kind: 'sut', id: 'fin.a.a' },
      { service: 'fin-report-service', system: 'fin', kind: 'sut', id: 'fin.a.b' },
      { service: 'wms-service', system: 'wms', kind: 'sut', id: 'wms.a.a' },
      { service: 'jira', system: 'jira', kind: 'integration', id: 'jira.a.list' },
      { service: 'jira', system: 'jira', kind: 'integration', id: 'jira.a.issue_get' },
    ])
  })

  it('左栏分「被测服务/第三方集成」两区,integration 服务在第三方区', async () => {
    const w = await mountPage()
    await flushPromises()
    expect(w.find('[data-testid="svc-kind-sut"]').text()).toContain('被测服务')
    expect(w.find('[data-testid="svc-kind-integration"]').text())
      .toContain('第三方集成')
    expect(w.find('[data-testid="svc-tree-jira"]').exists()).toBe(true)
    expect(w.find('[data-testid="svc-tree-fin-service"]').exists()).toBe(true)
  })

  it('external 别名:显式 base_service 下拉(只列 integration 服务),登记透传', async () => {
    const create = vi.spyOn(api, 'createAlias').mockResolvedValue({} as never)
    const w = await mountPage()
    await flushPromises()
    expect(w.find('[data-testid="alias-baseservice-trigger"]').exists())
      .toBe(false)  // plate 态不出现
    const vm = w.vm as unknown as {
      draft: { kind: string; baseService: string; aliasName: string; baseUrl: string }
    }
    vm.draft.kind = 'external'
    await nextTick()
    const trigger = w.find('[data-testid="alias-baseservice-trigger"]')
    expect(trigger.exists()).toBe(true)
    // 选项集:SelectContent 经 portal 渲染,jsdom 下不自 DOM ——
    // 以组件计算属性断言(与下拉同源 integrationServices)
    const admin = w.vm as unknown as { integrationServices: string[] }
    expect(admin.integrationServices).toEqual(['jira'])
    vm.draft.baseService = 'jira'
    vm.draft.aliasName = 'jira-x'
    vm.draft.baseUrl = 'https://jira.example'
    await nextTick()
    await w.find('[data-testid="alias-save"]').trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledWith(expect.objectContaining({
      kind: 'external', baseService: 'jira',
    }))
  })
})
