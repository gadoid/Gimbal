/**
 * ServiceAdmin.vue — 服务信息管理(P1 唯一净新增页面):
 *   - 左栏系统→服务两层树(只到服务级),右侧数字 = 已登记别名数;
 *   - 「默认面」行 = aliasName === baseService 的真实行打 tag;
 *   - 登记/编辑/删除走 api;admin 写面。
 *
 * authz M2a S6「别名瘦身」:baseUrl/环境归属/凭证别名/个人归属退役 —
 * 表列只剩 别名/所属服务/声明槽位/操作,登记不再需要 URL;分组(环境)
 * chips 已移除。这里同步改写:URL 必填断言改为「无 URL 即可登记」,
 * 槽位(slot)编辑钉住。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import ServiceAdmin from '@/views/ServiceAdmin.vue'
import * as api from '@/api/service-aliases'
import * as catalog from '@/utils/catalog-services'
import * as confirmModule from '@/utils/confirmAction'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const aliases: api.ServiceAliasRow[] = [
  { aliasName: 'fin-service', baseService: 'fin-service', kind: 'plate', slot: null,
    createdAt: '', updatedAt: '' },
  { aliasName: 'fin-service-uat', baseService: 'fin-service', kind: 'plate', slot: 'uat-slot',
    createdAt: '', updatedAt: '' },
  { aliasName: 'wms-service-pre', baseService: 'wms-service', kind: 'plate', slot: null,
    createdAt: '', updatedAt: '' },
]

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  vi.spyOn(api, 'listAllAliases').mockResolvedValue(aliases)
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

it('默认面行打 tag;槽位列展示声明值(M2a S6:URL/归属/环境列退役)', async () => {
  const w = await mountPage()
  const finRow = w.find('[data-testid="alias-row-fin-service"]').text()
  expect(finRow).toContain('默认面')
  expect(w.find('[data-testid="alias-row-fin-service-uat"]').text()).not.toContain('默认面')
  // 槽位列:声明值显示,未声明显示占位
  expect(w.find('[data-testid="alias-row-fin-service-uat"]').text()).toContain('uat-slot')
  expect(w.find('[data-testid="alias-row-fin-service"]').text()).toContain('未声明')
  // M2a S6 退役列不再渲染
  expect(w.text()).not.toContain('团队共享')
  expect(w.text()).not.toContain('未归属环境')
  expect(w.text()).not.toContain('凭证别名')
})

it('点树选服务 → 只看该服务(M2a S6:分组 chips 已随环境归属退役)', async () => {
  const w = await mountPage()
  await w.find('[data-testid="svc-tree-fin-service"]').trigger('click')
  expect(w.findAll('[data-testid^="alias-row-"]')).toHaveLength(2)
  // 分组(环境)chips 不再渲染
  expect(w.find('[data-testid="alias-chip-测试"]').exists()).toBe(false)
  expect(w.text()).not.toContain('未分组')
})

it('登记调用 createAlias 并重载(M2a S6:不需要 URL;不带退役字段)', async () => {
  const create = vi.spyOn(api, 'createAlias').mockResolvedValue(aliases[1])
  const w = await mountPage()
  await w.find('[data-testid="svc-tree-fin-service"]').trigger('click')
  await w.find('[data-testid="alias-name-input"]').setValue('prod2')
  // M2a S6:创建别名不再要求 URL —— 没填 URL 登记钮也可点
  expect((w.find('[data-testid="alias-save"]').element as HTMLButtonElement).disabled).toBe(false)
  await w.find('[data-testid="alias-slot-input"]').setValue('maker')
  await w.find('[data-testid="alias-save"]').trigger('click')
  await flushPromises()
  expect(create).toHaveBeenCalledWith({
    aliasName: 'fin-service-prod2', slot: 'maker', kind: 'plate', baseService: null,
  })
  expect(api.listAllAliases).toHaveBeenCalledTimes(2)

  await w.find('[data-testid="alias-edit-fin-service-uat"]').trigger('click')
  const nameInput = w.find('[data-testid="alias-name-input"]')
  expect((nameInput.element as HTMLInputElement).value).toBe('uat')
  expect((nameInput.element as HTMLInputElement).disabled).toBe(true)
  // 槽位回填
  expect((w.find('[data-testid="alias-slot-input"]').element as HTMLInputElement).value)
    .toBe('uat-slot')
})

it('编辑别名:patch 只送 slot(清空 = null);退役字段不出现', async () => {
  const patch = vi.spyOn(api, 'patchAlias').mockResolvedValue(aliases[0])
  const w = await mountPage()
  await w.find('[data-testid="alias-edit-fin-service-uat"]').trigger('click')
  await w.find('[data-testid="alias-slot-input"]').setValue('maker2')
  await w.find('[data-testid="alias-save"]').trigger('click')
  await flushPromises()
  expect(patch).toHaveBeenCalledWith('fin-service-uat', { slot: 'maker2' })
  // 清空槽位 → slot null(声明撤销)
  await w.find('[data-testid="alias-edit-fin-service-uat"]').trigger('click')
  await w.find('[data-testid="alias-slot-input"]').setValue('')
  await w.find('[data-testid="alias-save"]').trigger('click')
  await flushPromises()
  expect(patch).toHaveBeenLastCalledWith('fin-service-uat', { slot: null })
})

it('前缀槽常驻:未选显「服务」占位;点选只换槽文字、后缀随身;取消选中剥前缀;编辑态槽显所属服务', async () => {
  const create = vi.spyOn(api, 'createAlias').mockResolvedValue(aliases[1])
  const w = await mountPage()
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
  // 选回并保存:提交完整全串(无 URL 要求,不填槽位 → null)
  await w.find('[data-testid="svc-tree-fin-service"]').trigger('click')
  await w.find('[data-testid="alias-save"]').trigger('click')
  await flushPromises()
  expect(create).toHaveBeenCalledWith({
    aliasName: 'fin-service-uat2', slot: null, kind: 'plate', baseService: null,
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
    vi.spyOn(catalog, 'loadCatalogEntries').mockResolvedValue([
      { service: 'fin-service', system: 'fin', kind: 'sut' },
      { service: 'fin-report-service', system: 'fin', kind: 'sut' },
      { service: 'wms-service', system: 'wms', kind: 'sut' },
      { service: 'jira', system: 'jira', kind: 'integration' },
      { service: 'jira', system: 'jira', kind: 'integration' },
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
    const create = vi.spyOn(api, 'createAlias').mockResolvedValue({ } as never)
    const w = await mountPage()
    await flushPromises()
    expect(w.find('[data-testid="alias-baseservice-trigger"]').exists())
      .toBe(false)  // plate 态不出现
    const vm = w.vm as unknown as {
      draft: { kind: string; baseService: string; aliasName: string }
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
    await nextTick()
    await w.find('[data-testid="alias-save"]').trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledWith(expect.objectContaining({
      kind: 'external', baseService: 'jira',
    }))
  })
})
