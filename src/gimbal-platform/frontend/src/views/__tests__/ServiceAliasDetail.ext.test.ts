/**
 * ServiceAliasDetail — I4(集成线 v2 §3.2):外部接口目录 + query_safe
 * 只读标记开关。核心契约:
 *   - tab 只在 kind=external 的别名上出现(plate 别名/目录服务没有);
 *   - 目录表列出 ext:<alias>.<name> 锚点的结构定义(method/path/标记);
 *   - 开关仅 admin 可见可点:标记(带确认)/撤销 → 调
 *     setExternalQuerySafe 并翻转行内标记(审计在后端落);
 *   - 非 admin 只读展示,无操作列。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ServiceAliasDetail from '@/views/ServiceAliasDetail.vue'
import * as aliasApi from '@/api/service-aliases'
import * as extApi from '@/api/external-endpoints'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/service-aliases', () => ({
  listAliases: vi.fn(),
  listAllAliases: vi.fn(),
}))
vi.mock('@/api/external-endpoints', () => ({
  listExternalEndpoints: vi.fn(),
  setExternalQuerySafe: vi.fn(),
}))
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceNames: vi.fn().mockResolvedValue([]),
  loadCatalogEntries: vi.fn(),
}))
vi.mock('@/components/carry/ServiceBindingEditor.vue', () => ({
  default: {
    name: 'ServiceBindingEditor',
    props: ['serviceKey', 'baseService'],
    template: '<div data-testid="binding-editor-stub" />',
  },
}))
vi.mock('@/utils/errorFallback', () => ({
  showError: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const EXT_ALIAS = 'jira-x'

async function mountDetail(path: string, isAdmin: boolean) {
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
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.currentUser = {
    id: 1, username: 't', display_name: '', role: isAdmin ? 'admin' : 'user',
    is_active: true, created_at: '', updated_at: '',
  } as never
  const w = mount(ServiceAliasDetail, { global: { plugins: [router, pinia] } })
  await flushPromises()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(aliasApi.listAllAliases).mockResolvedValue([
    { aliasName: EXT_ALIAS, baseService: 'jira', kind: 'external',
      baseUrl: 'https://jira', environmentId: null, environmentName: null,
      credentialAlias: null, ownerUserId: null, createdAt: '', updatedAt: '' },
    { aliasName: 'fin-service', baseService: 'fin-service', kind: 'plate',
      baseUrl: null, environmentId: null, environmentName: null,
      credentialAlias: null, ownerUserId: null, createdAt: '', updatedAt: '' },
  ] as never)
  vi.mocked(extApi.listExternalEndpoints).mockResolvedValue([
    { id: 1, aliasName: EXT_ALIAS, name: 'search', title: '搜索',
      method: 'POST', path: '/search', requestSchema: null, auth: 'bearer',
      querySafe: false, notes: null, updatedAt: null },
    { id: 2, aliasName: EXT_ALIAS, name: 'issue-get', title: '查单',
      method: 'GET', path: '/issue/{key}', requestSchema: null, auth: 'none',
      querySafe: false, notes: null, updatedAt: null },
  ] as never)
})

describe('ServiceAliasDetail — 外部接口 query_safe 开关(I4)', () => {
  it('tab 只出现在 external 别名;plate 别名没有', async () => {
    const w = await mountDetail(`/service-admin/${EXT_ALIAS}?tab=endpoints`, true)
    expect(w.text()).toContain('外部接口目录')
    expect(w.text()).toContain('search')
    expect(w.text()).toContain('POST')
    expect(w.find('[data-testid="ext-qs-search"]').text()).toContain('未标记')
    w.unmount()

    const plate = await mountDetail('/service-admin/fin-service', true)
    expect(plate.text()).not.toContain('外部接口目录')
    plate.unmount()
  })

  it('admin:标记(确认后)调 API 并翻转行内标记;撤销不再确认', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(extApi.setExternalQuerySafe).mockResolvedValue({
      id: 1, aliasName: EXT_ALIAS, name: 'search', title: '搜索',
      method: 'POST', path: '/search', requestSchema: null, auth: 'bearer',
      querySafe: true, notes: null, updatedAt: null,
    } as never)
    const w = await mountDetail(`/service-admin/${EXT_ALIAS}?tab=endpoints`, true)
    const btn = w.find('[data-testid="ext-toggle-search"]')
    expect(btn.text()).toContain('标记只读')
    await btn.trigger('click')
    await flushPromises()
    expect(extApi.setExternalQuerySafe).toHaveBeenCalledWith(
      EXT_ALIAS, 'search', true)
    expect(w.find('[data-testid="ext-qs-search"]').text()).toContain('query_safe')
    expect(w.find('[data-testid="ext-toggle-search"]').text()).toContain('撤销只读')
    w.unmount()
  })

  it('标记前 confirm 取消 → 不调 API', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const w = await mountDetail(`/service-admin/${EXT_ALIAS}?tab=endpoints`, true)
    await w.find('[data-testid="ext-toggle-search"]').trigger('click')
    await flushPromises()
    expect(extApi.setExternalQuerySafe).not.toHaveBeenCalled()
    expect(w.find('[data-testid="ext-qs-search"]').text()).toContain('未标记')
    w.unmount()
  })

  it('非 admin:只读展示,无操作列无开关', async () => {
    const w = await mountDetail(`/service-admin/${EXT_ALIAS}?tab=endpoints`, false)
    expect(w.text()).toContain('外部接口目录')
    expect(w.find('[data-testid="ext-toggle-search"]').exists()).toBe(false)
    expect(w.text()).toContain('未标记')
    w.unmount()
  })
})
