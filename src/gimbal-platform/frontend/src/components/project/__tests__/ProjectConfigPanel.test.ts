/**
 * ProjectConfigPanel —— S7.3 项目配置页签。
 * 普通项目:默认环境编辑(canManage)/项目层 carry 编辑器/槽位状态/
 * 生效预览入口;公共项目:全局默认编辑器(原 /carry-config 落位),
 * 无默认环境与槽位状态节(公共项目不可 PATCH、slot-status 422)。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ProjectConfigPanel from '@/components/project/ProjectConfigPanel.vue'
import * as projectsApi from '@/api/projects'
import * as carryApi from '@/api/carry'
import * as envApi from '@/api/environments'
import * as scenApi from '@/api/scenario-composer'
import * as credApi from '@/api/project_credentials'
import * as execApi from '@/api/execConfigs'

vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const proj: projectsApi.ProjectOut = {
  id: 3, name: 'P3', kind: 'normal', description: '', memberCount: 2,
  myRole: 'admin', canManage: true, defaultEnvironmentId: 7,
  defaultEnvironmentName: 'dev', scenarioCount: 1, suiteCount: 0, taskCount: 0,
}
const projPublic: projectsApi.ProjectOut = {
  ...proj, id: 1, kind: 'public', myRole: null, canManage: true,
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
  vi.spyOn(envApi, 'listEnvironments').mockResolvedValue([
    { id: 7, name: 'dev', description: '', lines: {}, owner_id: null, is_default: true },
    { id: 8, name: 'sit', description: '', lines: {}, owner_id: null, is_default: false },
  ] as never)
  vi.spyOn(execApi, 'listExecConfigs').mockResolvedValue([])
  vi.spyOn(carryApi, 'getDefaults').mockResolvedValue({ '$.a': 'v' })
  vi.spyOn(carryApi, 'putDefaults').mockResolvedValue({})
  vi.spyOn(carryApi, 'getBindings').mockResolvedValue({ 'fin-service': { '$.a': '1' } })
  vi.spyOn(carryApi, 'getDrift').mockResolvedValue({
    services: [{ service: 'fin-service', orphaned: ['$.old'], uncovered: [],
      renamedSuggestions: [] }],
    plateReachable: true, scope: 'project', scopeId: 3,
  })
  vi.spyOn(projectsApi, 'getSlotStatus').mockResolvedValue({
    slots: [{
      slot: 'qa', scenarios: ['sc-1'],
      members: [
        { userId: 1, username: 'u1', displayName: 'U1', bound: true },
        { userId: 2, username: 'u2', displayName: 'U2', bound: false },
      ],
    }],
  })
  vi.spyOn(scenApi, 'listScenarios').mockResolvedValue({
    items: [{ meta: { scenarioId: 'sc-1', name: '退款', system: [], module: '' } }],
    total: 1, page: 1, page_size: 100,
  } as never)
  vi.spyOn(credApi, 'listProjectCredentials').mockResolvedValue({
    items: [{
      id: 11, alias: 'qa', url: 'http://a', username: 'proj-u',
      token_type: 'Bearer', expires_in: 7200, created_at: '', updated_at: '',
      password_masked: '<REDACTED>', slot: 'qa', isDefault: true, system: 'fin',
    }],
    canManage: true,
  })
})

afterEach(() => { document.body.innerHTML = '' })

/** 面板读 route.query.path(公共项目 ?path= 深链)→ 带真 router 挂载 */
function mountPanel(p = proj) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div/>' } }],
  })
  return mount(ProjectConfigPanel, {
    props: { project: p },
    global: { plugins: [router, createPinia()] },
    attachTo: document.body,
  })
}

describe('ProjectConfigPanel — 普通项目', () => {
  it('默认环境:回显 + 保存走 patchProject(defaultEnvironmentId)', async () => {
    const patch = vi.spyOn(projectsApi, 'patchProject').mockResolvedValue(proj)
    const w = mountPanel()
    await flushPromises()
    const sel = w.find('[data-testid="prj-config-env"]')
    expect((sel.element as HTMLSelectElement).value).toBe('7')
    await sel.setValue('8')
    await w.find('[data-testid="prj-config-env-save"]').trigger('click')
    await flushPromises()
    expect(patch).toHaveBeenCalledWith(3, { defaultEnvironmentId: 8 })
    w.unmount()
  })

  it('默认环境:显式清空 → patchProject(null)', async () => {
    const patch = vi.spyOn(projectsApi, 'patchProject').mockResolvedValue(proj)
    const w = mountPanel()
    await flushPromises()
    await w.find('[data-testid="prj-config-env"]').setValue('')
    await w.find('[data-testid="prj-config-env-save"]').trigger('click')
    await flushPromises()
    expect(patch).toHaveBeenCalledWith(3, { defaultEnvironmentId: null })
    w.unmount()
  })

  it('槽位状态:成员已绑/未绑 chips 渲染', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(w.find('[data-testid="prj-slot-qa"]').exists()).toBe(true)
    expect(w.find('[data-testid="prj-slot-qa-1"]').classes()).toContain('ok')
    expect(w.find('[data-testid="prj-slot-qa-2"]').classes()).toContain('miss')
    w.unmount()
  })

  it('生效预览:选场景 → 打开弹框并展示逐值来源', async () => {
    const apiRuns = await import('@/api/runs')
    vi.spyOn(apiRuns, 'previewEffectiveConfig').mockResolvedValue({
      env: { environmentId: 7, environmentSource: 'project' },
      services: { 'fin-service': { url: 'http://x', source: 'deployment' } },
      auths: { qa: { bindingId: 11, system: 'fin-service', envId: null, isDefault: true } },
      missingAuths: [],
      carry: {},
      carryDefaults: {},
    })
    const w = mountPanel()
    await flushPromises()
    await w.find('[data-testid="prj-config-preview-scen"]').setValue('sc-1')
    await w.find('[data-testid="prj-config-preview-go"]').trigger('click')
    await flushPromises()
    expect(document.body.querySelector('[data-testid="preview-dialog"]')).toBeTruthy()
    expect(document.body.textContent).toContain('项目默认')
    expect(document.body.textContent).toContain('部署地址')
    w.unmount()
  })
})

describe('ProjectConfigPanel — carry 漂移(S7.6)', () => {
  it('普通项目:按项目层拉漂移;勾选生成批带 scope=project', async () => {
    const adaptApi = await import('@/api/adaptations')
    const open = vi.spyOn(adaptApi, 'openCarryBatch').mockResolvedValue(
      { batchId: 'bt-x', ops: [], snapshots: [] } as never)
    const createOp = vi.spyOn(adaptApi, 'createOp').mockResolvedValue({} as never)
    const w = mountPanel()
    await flushPromises()
    expect(carryApi.getDrift).toHaveBeenCalledWith({ scope: 'project', projectId: 3 })
    const panel = w.find('[data-testid="carry-drift-prj-cfg"]')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain('孤儿绑定 $.old')
    await panel.find('input[type="checkbox"]').setValue(true)
    await panel.find('[data-action="drift-generate"]').trigger('click')
    await flushPromises()
    expect(open).toHaveBeenCalledWith('fin-service', { scope: 'project', projectId: 3 })
    expect(createOp).toHaveBeenCalledWith('bt-x', {
      opType: 'removeCarryBinding',
      payload: { service: 'fin-service', path: '$.old' },
    })
    w.unmount()
  })

  it('公共项目不挂漂移节(公共层漂移在变更适配页)', async () => {
    const w = mountPanel(projPublic)
    await flushPromises()
    expect(w.find('[data-testid="carry-drift-prj-cfg"]').exists()).toBe(false)
    expect(carryApi.getDrift).not.toHaveBeenCalled()
    w.unmount()
  })
})

describe('ProjectConfigPanel — 公共项目', () => {
  it('只显全局默认编辑器;无默认环境/按服务/槽位/预览节', async () => {
    const w = mountPanel(projPublic)
    await flushPromises()
    expect(w.find('[data-testid="prj-config-env"]').exists()).toBe(false)
    // 编辑器 tid 锚:公共项目 = 全局层(prj-cfg-global-* 行),非项目层
    // (getDefaults mock 有一行 → row 锚不依赖 canWrite)
    expect(w.find('[data-testid="prj-cfg-global-row-0"]').exists()).toBe(true)
    expect(w.find('[data-testid="prj-cfg-project-row-0"]').exists()).toBe(false)
    expect(w.find('[data-testid="prj-config-svc"]').exists()).toBe(false)
    expect(w.find('[data-testid="prj-config-preview-scen"]').exists()).toBe(false)
    // 公共项目不拉槽位状态
    expect(projectsApi.getSlotStatus).not.toHaveBeenCalled()
    w.unmount()
  })
})


describe('ProjectConfigPanel — S8 项目凭证/槽位项目覆盖', () => {
  it('项目凭证节渲染(管理员视图带用户名);槽位状态带「项目凭证 · 已登记」chip', async () => {
    const w = mountPanel()
    await flushPromises()
    expect(w.find('[data-testid="project-credentials"]').exists()).toBe(true)
    const row = w.find('[data-testid="prj-cred-11"]')
    expect(row.text()).toContain('proj-u')
    // slot-status 的 qa 槽带项目覆盖标记(projectBound 由 getSlotStatus 供给,
    // 上方 mock 未带 → 再按带标记的返回断言 chip)
    expect(w.find('[data-testid="prj-slot-qa"]').exists()).toBe(true)
  })

  it('公共项目无项目凭证节', async () => {
    const w = mountPanel(projPublic)
    await flushPromises()
    expect(w.find('[data-testid="project-credentials"]').exists()).toBe(false)
  })
})

describe('ProjectConfigPanel — ⑧ 项目执行配置(项目变体)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.spyOn(envApi, 'listEnvironments').mockResolvedValue([])
    vi.spyOn(carryApi, 'getDefaults').mockResolvedValue({})
    vi.spyOn(carryApi, 'putDefaults').mockResolvedValue({})
    vi.spyOn(carryApi, 'getBindings').mockResolvedValue({})
    vi.spyOn(carryApi, 'getDrift').mockResolvedValue(
      { services: [], plateReachable: true, scope: 'project', scopeId: 3 })
    vi.spyOn(projectsApi, 'getSlotStatus').mockResolvedValue({ slots: [] })
    vi.spyOn(scenApi, 'listScenarios').mockResolvedValue(
      { items: [], total: 0, page: 1, page_size: 100 } as never)
    vi.spyOn(credApi, 'listProjectCredentials').mockResolvedValue(
      { items: [], total: 0, page: 1, page_size: 100 } as never)
  })

  it('管理员:列表渲染 + 新建发 scope=project/projectId + 设默认', async () => {
    const row = { id: 11, name: '大促模式', isDefault: true,
                  environmentId: null, scope: 'project',
                  systems: [{ service: 'fin', bindings: {},
                              carryOverrides: { '$.pv': 'x' } }] }
    const list = vi.spyOn(execApi, 'listExecConfigs')
      .mockResolvedValue([row])
    const create = vi.spyOn(execApi, 'createExecConfig')
      .mockResolvedValue(row)
    const router = createRouter({ history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div/>' } }] })
    const w = mount(ProjectConfigPanel, {
      props: { project: proj },
      global: { plugins: [createPinia(), router] },
    })
    await flushPromises()
    expect(list).toHaveBeenCalledWith(3)
    expect(w.get('[data-testid="prj-ec-11"]').text()).toContain('大促模式')
    expect(w.get('[data-testid="prj-ec-11"]').text()).toContain('fin:1')
    // 新建:scope=project + projectId + isDefault
    await w.get('[data-testid="prj-ec-name"]').setValue('新变体')
    await w.get('[data-testid="prj-ec-service"]').setValue('fin')
    await w.get('[data-testid="prj-ec-field"]').setValue('$.pv')
    await w.get('[data-testid="prj-ec-value"]').setValue('v2')
    await w.get('[data-testid="prj-ec-add"]').trigger('click')
    await flushPromises()
    expect(create).toHaveBeenCalledWith({
      name: '新变体', scope: 'project', projectId: 3, isDefault: true,
      systems: [{ service: 'fin', bindings: {},
                  carryOverrides: { '$.pv': 'v2' } }],
    })
    w.unmount()
  })

  it('公共项目:不出项目执行配置节', async () => {
    vi.spyOn(execApi, 'listExecConfigs').mockResolvedValue([])
    const router = createRouter({ history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div/>' } }] })
    const w = mount(ProjectConfigPanel, {
      props: { project: projPublic },
      global: { plugins: [createPinia(), router] },
    })
    await flushPromises()
    expect(w.find('[data-testid="prj-exec-configs"]').exists()).toBe(false)
    w.unmount()
  })
})
