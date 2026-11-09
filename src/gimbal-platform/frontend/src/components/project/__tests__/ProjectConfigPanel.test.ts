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
  vi.spyOn(carryApi, 'getDefaults').mockResolvedValue({ '$.a': 'v' })
  vi.spyOn(carryApi, 'putDefaults').mockResolvedValue({})
  vi.spyOn(carryApi, 'getBindings').mockResolvedValue({ 'fin-service': { '$.a': '1' } })
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
