/**
 * ServiceAliasDetail.vue — 键详情/服务子页(2026-11-13 承接身份面注册):
 *   - 服务模式(param=目录服务名):概览 + 身份面 tab(服务端分页 +
 *     行内搜索;登记/编辑槽位/删除仅 canManage)+ 说明(service_meta
 *     展示/编辑)+ 字段默认值(canManage);
 *   - 别名模式(param=身份面):概览 + 字段默认值 + 凭证;返回按钮按
 *     能力分流(admin → 服务注册,普通用户 → 认证管理)。
 * jsdom:reka TabsTrigger 打不开 → 直改 vm.activeTab;DropdownMenu 不涉及。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, getActivePinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ServiceAliasDetail from '@/views/ServiceAliasDetail.vue'
import * as aliasApi from '@/api/service-aliases'
import * as envApi from '@/api/environments'
import * as depApi from '@/api/deployments'
import * as metaApi from '@/api/service-meta'
import * as catalog from '@/utils/catalog-services'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@/components/carry/ServiceBindingEditor.vue', () => ({
  default: { name: 'ServiceBindingEditor', template: '<div data-testid="binding-editor" />' },
}))

const ENVS = [
  { id: 1, name: '测试', description: '', lines: {}, owner_id: null, is_default: true },
]
const ALIAS_ROWS: aliasApi.ServiceAliasRow[] = [
  { aliasName: 'fin-service-uat', baseService: 'fin-service', kind: 'plate',
    slot: 'uat-slot', createdAt: '', updatedAt: '' },
]
/** listAliases 按服务端语义:base 精确 + q 子串 + 分页(身份面注册表)。 */
const FACES: aliasApi.ServiceAliasRow[] = [
  { aliasName: 'fin-service', baseService: 'fin-service', kind: 'plate',
    slot: null, createdAt: '', updatedAt: '' },
  { aliasName: 'fin-service-uat', baseService: 'fin-service', kind: 'plate',
    slot: 'uat-slot', createdAt: '', updatedAt: '' },
]

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  vi.spyOn(aliasApi, 'listAllAliases').mockResolvedValue(ALIAS_ROWS)
  vi.spyOn(aliasApi, 'listAliases').mockImplementation(async (args) => {
    let items = args?.base
      ? FACES.filter((a) => a.baseService === args.base) : [...FACES]
    if (args?.q) {
      const q = args.q.toLowerCase()
      items = items.filter((a) => a.aliasName.toLowerCase().includes(q)
        || (a.slot ?? '').toLowerCase().includes(q))
    }
    const page = args?.page ?? 1
    const size = args?.page_size ?? 100
    return {
      items: items.slice((page - 1) * size, page * size),
      total: items.length, page, pageSize: size,
    }
  })
  vi.spyOn(envApi, 'listEnvironments').mockResolvedValue(ENVS)
  vi.spyOn(depApi, 'listDeployments').mockResolvedValue([])
  vi.spyOn(metaApi, 'listServiceMeta').mockResolvedValue([
    { serviceName: 'fin-service', description: '交易核心服务,负责订单/支付', updatedAt: null },
  ])
  vi.spyOn(catalog, 'loadCatalogServiceNames').mockResolvedValue([
    'fin-service', 'jira', 'wms-service',
  ])
  vi.spyOn(catalog, 'loadCatalogServiceRows').mockResolvedValue([
    { name: 'fin-service', system: 'fin', endpointCount: 3, kind: 'sut' },
    { name: 'jira', system: 'jira', endpointCount: 2, kind: 'integration' },
  ])
})

afterEach(() => {
  document.body.innerHTML = ''
})

function setAuth(canManage: boolean): void {
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  auth.currentUser = {
    id: 1, username: 'u', role: canManage ? 'super_admin' : 'user',
  } as never
  auth.capabilities = canManage ? ['ops.write'] : []
}

async function mountAt(path: string): Promise<{ w: ReturnType<typeof mount>; router: Router }> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/service-admin', component: { template: '<div />' } },
      { path: '/service-admin/:alias', component: ServiceAliasDetail },
      { path: '/auths', component: { template: '<div />' } },
      { path: '/services/:name', component: { template: '<div />' } },
    ],
  })
  await router.push(path)
  await router.isReady()
  // 复用 beforeEach 的 active pinia(setAuth 写的就是它)
  const w = mount(ServiceAliasDetail, {
    global: { plugins: [getActivePinia()!, router] },
  })
  await flushPromises()
  return { w: w as unknown as ReturnType<typeof mount>, router }
}

function pokeTab(w: ReturnType<typeof mount>, value: string): void {
  ;(w.vm as unknown as { activeTab: string }).activeTab = value
}

// ── 服务模式:身份面注册表 ──────────────────────────────────────
describe('ServiceAliasDetail — 服务模式(身份面子页)', () => {
  it('挂载即按服务取身份面分页 + 说明回显;faces tab 内容可达', async () => {
    setAuth(false)
    const { w } = await mountAt('/service-admin/fin-service')
    expect(aliasApi.listAliases).toHaveBeenCalledWith({
      base: 'fin-service', q: undefined, page: 1, page_size: 10,
    })
    expect(w.text()).toContain('交易核心服务')
    pokeTab(w, 'faces')
    await flushPromises()
    expect(w.get('[data-testid="faces-table"]').text()).toContain('fin-service-uat')
    expect(w.find('[data-testid="face-row-fin-service"]').exists()).toBe(true)
    expect((w.vm as unknown as { faces: { total: number } }).faces.total).toBe(2)
    w.unmount()
  })

  it('faces 行内搜索 → q 下推(300ms 防抖)', async () => {
    setAuth(false)
    const { w } = await mountAt('/service-admin/fin-service')
    pokeTab(w, 'faces')
    await flushPromises()
    await w.get('[data-testid="faces-q"]').setValue('uat')
    await new Promise((r) => setTimeout(r, 400))
    await flushPromises()
    expect(aliasApi.listAliases).toHaveBeenLastCalledWith({
      base: 'fin-service', q: 'uat', page: 1, page_size: 10,
    })
    w.unmount()
  })

  it('canManage:登记表单(sut 派生)→ createAlias({kind:"plate", baseService:null})', async () => {
    setAuth(true)
    const create = vi.spyOn(aliasApi, 'createAlias')
      .mockResolvedValue(ALIAS_ROWS[0])
    const { w } = await mountAt('/service-admin/fin-service')
    pokeTab(w, 'faces')
    await flushPromises()
    await w.get('[data-testid="faces-open-create"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="faces-form"]').exists()).toBe(true)
    expect((w.find('[data-testid="face-save"]').element as HTMLButtonElement).disabled)
      .toBe(true)   // 没写后缀不可提交
    await w.get('[data-testid="face-suffix"]').setValue('prod2')
    await w.get('[data-testid="face-slot"]').setValue('maker')
    await w.get('[data-testid="face-save"]').trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledWith({
      aliasName: 'fin-service-prod2', slot: 'maker',
      kind: 'plate', baseService: null,
    })
    w.unmount()
  })

  it('integration 服务的登记 → kind external + 显式 baseService', async () => {
    setAuth(true)
    const create = vi.spyOn(aliasApi, 'createAlias')
      .mockResolvedValue(ALIAS_ROWS[0])
    const { w } = await mountAt('/service-admin/jira')
    pokeTab(w, 'faces')
    await flushPromises()
    await w.get('[data-testid="faces-open-create"]').trigger('click')
    await w.get('[data-testid="face-suffix"]').setValue('x')
    await w.get('[data-testid="face-save"]').trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledWith(expect.objectContaining({
      aliasName: 'jira-x', kind: 'external', baseService: 'jira',
    }))
    w.unmount()
  })

  it('编辑槽位 → patchAlias(aliasName, {slot});清空 = null', async () => {
    setAuth(true)
    const patch = vi.spyOn(aliasApi, 'patchAlias')
      .mockResolvedValue(ALIAS_ROWS[0])
    const { w } = await mountAt('/service-admin/fin-service')
    pokeTab(w, 'faces')
    await flushPromises()
    await w.get('[data-testid="face-edit-fin-service-uat"]').trigger('click')
    const suffix = w.get('[data-testid="face-suffix"]')
    expect((suffix.element as HTMLInputElement).value).toBe('uat')
    expect((suffix.element as HTMLInputElement).disabled).toBe(true)   // 主键不可改
    expect((w.get('[data-testid="face-slot"]').element as HTMLInputElement).value)
      .toBe('uat-slot')
    await w.get('[data-testid="face-slot"]').setValue('maker2')
    await w.get('[data-testid="face-save"]').trigger('click')
    await flushPromises()
    expect(patch).toHaveBeenCalledWith('fin-service-uat', { slot: 'maker2' })
    w.unmount()
  })

  it('说明编辑 → putServiceMeta(key, text)并回显', async () => {
    setAuth(true)
    vi.spyOn(metaApi, 'putServiceMeta').mockResolvedValue(
      { serviceName: 'fin-service', description: '新说明', updatedAt: null })
    const { w } = await mountAt('/service-admin/fin-service')
    await w.get('[data-testid="svc-desc-edit"]').trigger('click')
    await w.get('[data-testid="svc-desc-input"]').setValue('新说明')
    await w.get('[data-testid="svc-desc-save"]').trigger('click')
    await flushPromises()
    expect(metaApi.putServiceMeta).toHaveBeenCalledWith('fin-service', '新说明')
    expect(w.get('[data-testid="svc-desc-fin-service"]').text()).toContain('新说明')
    w.unmount()
  })

  it('普通用户:登记/编辑/删除/说明编辑全部不在场(读面仍可用)', async () => {
    setAuth(false)
    const { w } = await mountAt('/service-admin/fin-service')
    expect(w.find('[data-testid="faces-open-create"]').exists()).toBe(false)
    expect(w.find('[data-testid="svc-desc-edit"]').exists()).toBe(false)
    pokeTab(w, 'faces')
    await flushPromises()
    expect(w.find('[data-testid="face-row-fin-service-uat"]').exists()).toBe(true)
    expect(w.find('[data-testid="face-edit-fin-service-uat"]').exists()).toBe(false)
    expect(w.find('[data-testid="face-del-fin-service-uat"]').exists()).toBe(false)
    w.unmount()
  })
})

// ── 别名模式回归 ────────────────────────────────────────────────
describe('ServiceAliasDetail — 别名模式', () => {
  it('别名键:无 faces tab,凭证 tab 在场;返回按钮按能力分流', async () => {
    setAuth(true)
    const { w, router } = await mountAt('/service-admin/fin-service-uat')
    expect(w.text()).toContain('别名详情')
    expect((w.vm as unknown as { isAliasMode: boolean }).isAliasMode).toBe(true)
    expect(w.find('[data-testid="faces-q"]').exists()).toBe(false)
    expect(w.text()).toContain('凭证')
    await w.get('[data-testid="back-admin"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/service-admin')
    w.unmount()
  })

  it('普通用户别名键:返回落认证管理(不撞路由守卫)', async () => {
    setAuth(false)
    const { w, router } = await mountAt('/service-admin/fin-service-uat')
    await w.get('[data-testid="back-admin"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/auths')
    w.unmount()
  })
})
