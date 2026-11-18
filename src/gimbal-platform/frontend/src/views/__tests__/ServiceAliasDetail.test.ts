/**
 * ServiceAliasDetail.vue — 键详情/服务子页(registry 重构 P2-B.1 条目化):
 *   - 服务模式(param=服务名,主档 ∪ 目录):概览 + 身份条目 tab(服务端
 *     分页 + 行内搜索;登记带 环境/ref 维度)+ 说明(主档 description 门面)
 *     + 字段默认值(canManage);
 *   - 条目模式(param=条目名):概览(条目信息含 账户装载 行)+ 地址就绪
 *     矩阵(API 地址 + 实例登录口/版本线)+ 账户装载 tab(凭证管理反查
 *     深链 ?tab=credential);返回按钮按能力分流。
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
import * as servicesApi from '@/api/services'
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
/** 主档:fin-service 受管(fin 系统)/ jira 第三方(jira 系统)。 */
const SVC_ROWS: servicesApi.ServiceRow[] = [
  { name: 'fin-service', system: 'fin', kind: 'plate', abbr: '', description: '',
    inCatalog: true, createdAt: '', updatedAt: '' },
  { name: 'jira', system: 'jira', kind: 'external', abbr: '', description: '',
    inCatalog: false, createdAt: '', updatedAt: '' },
]
const ALIAS_ROWS: aliasApi.ServiceAliasRow[] = [
  { aliasName: 'fin-service-uat', baseService: 'fin-service', kind: 'plate',
    slot: 'uat-slot', envId: 1, refMode: 'default', refUsername: null,
    display: '', createdAt: '', updatedAt: '' },
]
/** listAliases 按服务端语义:base 精确 + q 子串 + 分页(身份条目注册表)。 */
const FACES: aliasApi.ServiceAliasRow[] = [
  { aliasName: 'fin-service', baseService: 'fin-service', kind: 'plate',
    slot: null, envId: 1, refMode: 'default', refUsername: null,
    display: '', createdAt: '', updatedAt: '' },
  { aliasName: 'fin-service-uat', baseService: 'fin-service', kind: 'plate',
    slot: 'uat-slot', envId: 1, refMode: 'username', refUsername: 'bot',
    display: 'uat-slot', createdAt: '', updatedAt: '' },
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
  vi.spyOn(servicesApi, 'listServices').mockResolvedValue({
    services: SVC_ROWS, unregistered: [], plateReachable: true,
  })
  vi.spyOn(servicesApi, 'listInstances').mockResolvedValue([])
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

// ── 服务模式:身份条目注册表 ────────────────────────────────────
describe('ServiceAliasDetail — 服务模式(身份条目子页)', () => {
  it('挂载即按服务取条目分页 + 说明回显;faces tab 内容可达(含环境/账户装载列)', async () => {
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
    // 新列:环境名 + ref 用户名(条目化口径)
    expect(w.get('[data-testid="faces-table"]').text()).toContain('测试')
    expect(w.get('[data-testid="faces-table"]').text()).toContain('用户名 bot')
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

  it('canManage:登记表单(sut 派生)→ createAlias 带 envId/refMode', async () => {
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
    // 环境缺省 = 平台默认环境(测试)
    expect((w.get('[data-testid="face-env"]').element as HTMLSelectElement).value).toBe('1')
    await w.get('[data-testid="face-suffix"]').setValue('prod2')
    await w.get('[data-testid="face-slot"]').setValue('maker')
    await w.get('[data-testid="face-save"]').trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledWith({
      aliasName: 'fin-service-prod2', display: 'maker',
      kind: 'plate', baseService: null,
      envId: 1, refMode: 'default',
    })
    w.unmount()
  })

  it('integration 服务的登记 → kind external + 显式 baseService;ref 用户名带出 refUsername', async () => {
    setAuth(true)
    const create = vi.spyOn(aliasApi, 'createAlias')
      .mockResolvedValue(ALIAS_ROWS[0])
    const { w } = await mountAt('/service-admin/jira')
    pokeTab(w, 'faces')
    await flushPromises()
    await w.get('[data-testid="faces-open-create"]').trigger('click')
    await w.get('[data-testid="face-suffix"]').setValue('x')
    await w.get('[data-testid="face-ref-mode"]').setValue('username')
    await w.get('[data-testid="face-ref-username"]').setValue('bot')
    await w.get('[data-testid="face-save"]').trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledWith(expect.objectContaining({
      aliasName: 'jira-x', kind: 'external', baseService: 'jira',
      envId: 1, refMode: 'username', refUsername: 'bot',
    }))
    w.unmount()
  })

  it('编辑 → patchAlias(aliasName, {display, refMode, refUsername});环境是实体键不可改', async () => {
    setAuth(true)
    const patch = vi.spyOn(aliasApi, 'patchAlias')
      .mockResolvedValue(FACES[1])
    const { w } = await mountAt('/service-admin/fin-service')
    pokeTab(w, 'faces')
    await flushPromises()
    await w.get('[data-testid="face-edit-fin-service-uat"]').trigger('click')
    const suffix = w.get('[data-testid="face-suffix"]')
    expect((suffix.element as HTMLInputElement).value).toBe('uat')
    expect((suffix.element as HTMLInputElement).disabled).toBe(true)   // 主键不可改
    expect((w.get('[data-testid="face-env"]').element as HTMLSelectElement).disabled)
      .toBe(true)   // 环境是实体键,不可改
    expect((w.get('[data-testid="face-ref-mode"]').element as HTMLSelectElement).value)
      .toBe('username')   // 回显既有 ref
    expect((w.get('[data-testid="face-ref-username"]').element as HTMLInputElement).value)
      .toBe('bot')
    await w.get('[data-testid="face-slot"]').setValue('maker2')
    await w.get('[data-testid="face-ref-mode"]').setValue('default')
    await w.get('[data-testid="face-save"]').trigger('click')
    await flushPromises()
    expect(patch).toHaveBeenCalledWith('fin-service-uat', {
      display: 'maker2', refMode: 'default', refUsername: null,
    })
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

// ── 条目模式回归 ────────────────────────────────────────────────
describe('ServiceAliasDetail — 条目模式', () => {
  it('条目键:头部徽标(环境/ref)+ 账户装载 tab;返回按钮按能力分流', async () => {
    setAuth(true)
    const { w, router } = await mountAt('/service-admin/fin-service-uat')
    expect(w.text()).toContain('身份条目详情')
    expect((w.vm as unknown as { isAliasMode: boolean }).isAliasMode).toBe(true)
    expect(w.find('[data-testid="faces-q"]').exists()).toBe(false)
    // 头部徽标新口径:环境 + ref(槽位徽标已退役)
    expect(w.get('[data-testid="env-badge"]').text()).toBe('环境 测试')
    expect(w.get('[data-testid="ref-mode-badge"]').text()).toBe('ref 默认')
    // 概览:账户装载行(ref 语义)
    expect(w.get('[data-testid="alias-overview"]').text()).toContain('账户装载')
    // 账户装载 tab(凭证管理反查深链落点)
    pokeTab(w, 'credential')
    await flushPromises()
    expect(w.get('[data-testid="cred-ref-line"]').text()).toContain('ref 默认')
    expect(w.get('[data-testid="open-auths"]').text()).toContain('凭证管理')
    await w.get('[data-testid="back-admin"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/service-admin')
    w.unmount()
  })

  it('地址就绪矩阵:API 地址 + 实例登录口/版本线三面齐读', async () => {
    setAuth(true)
    vi.spyOn(depApi, 'listDeployments').mockResolvedValue([
      { id: 1, baseService: 'fin-service', envId: 1, baseUrl: 'https://fin.example/api' },
    ] as never)
    vi.spyOn(servicesApi, 'listInstances').mockResolvedValue([
      { system: 'fin', envId: 1, envName: '测试', groupId: 'g-fin-1',
        tags: ['测试'],
        loginUrl: 'https://fin.example/auth', line: '1.0', note: '', updatedAt: null },
    ])
    const { w } = await mountAt('/service-admin/fin-service-uat')
    const matrix = w.get('[data-testid="alias-ready-matrix"]').text()
    expect(matrix).toContain('https://fin.example/api')   // deployments
    expect(w.get('[data-testid="ready-login-测试"]').text())
      .toContain('https://fin.example/auth')              // 实例登录口
    expect(matrix).toContain('1.0')                        // 实例版本线
    w.unmount()
  })

  it('实例缺席 → 登录口列显缺(admin 深链服务注册)', async () => {
    setAuth(true)
    const { w } = await mountAt('/service-admin/fin-service-uat')
    const matrix = w.get('[data-testid="alias-ready-matrix"]').text()
    expect(matrix).toContain('去服务注册')
    expect(w.find('[data-testid="ready-login-测试"]').exists()).toBe(false)
    w.unmount()
  })

  it('普通用户条目键:返回落凭证管理(不撞路由守卫)', async () => {
    setAuth(false)
    const { w, router } = await mountAt('/service-admin/fin-service-uat')
    await w.get('[data-testid="back-admin"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/auths')
    w.unmount()
  })
})
