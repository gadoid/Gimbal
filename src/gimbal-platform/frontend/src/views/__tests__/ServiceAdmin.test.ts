/**
 * ServiceAdmin.vue — 服务信息管理(P1 唯一净新增页面):
 *   - 左栏系统→服务两层树(只到服务级),右侧数字 = 已登记别名数;
 *   - 顶部分组 chip 筛选(不选服务跨服务筛,选了服务在服务内筛);
 *   - 「服务级默认」行 = aliasName === baseService 的真实行打 tag;
 *   - 登记/编辑/删除走 api;admin 写面。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ServiceAdmin from '@/views/ServiceAdmin.vue'
import * as api from '@/api/service-aliases'
import * as authApi from '@/api/auth_sessions'
import * as catalog from '@/utils/catalog-services'
import * as confirmModule from '@/utils/confirmAction'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const aliases: api.ServiceAliasRow[] = [
  { aliasName: 'fin-service', baseService: 'fin-service', groupTag: null,
    credentialAlias: null, ownerUserId: null, createdAt: '', updatedAt: '' },
  { aliasName: 'fin-service-uat', baseService: 'fin-service', groupTag: '测试',
    credentialAlias: 'uat-cred', ownerUserId: null, createdAt: '', updatedAt: '' },
  { aliasName: 'wms-service-pre', baseService: 'wms-service', groupTag: '预发',
    credentialAlias: null, ownerUserId: 7, createdAt: '', updatedAt: '' },
]

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  vi.spyOn(api, 'listAliases').mockResolvedValue(aliases)
  vi.spyOn(authApi, 'list').mockResolvedValue([
    { alias: 'uat-cred' } as never,
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

it('登记调用 createAlias 并重载;编辑回填且别名不可改', async () => {
  const create = vi.spyOn(api, 'createAlias').mockResolvedValue(aliases[1])
  const w = await mountPage()
  await w.find('[data-testid="alias-name-input"]').setValue('mall-service-prod')
  await w.find('[data-testid="alias-group-input"]').setValue('生产')
  await w.find('[data-testid="alias-save"]').trigger('click')
  await flushPromises()
  expect(create).toHaveBeenCalledWith({
    aliasName: 'mall-service-prod', groupTag: '生产', credentialAlias: null,
  })
  expect(api.listAliases).toHaveBeenCalledTimes(2)

  await w.find('[data-testid="alias-edit-fin-service-uat"]').trigger('click')
  const nameInput = w.find('[data-testid="alias-name-input"]')
  expect((nameInput.element as HTMLInputElement).value).toBe('fin-service-uat')
  expect((nameInput.element as HTMLInputElement).disabled).toBe(true)
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
