/**
 * Projects — M2a S7.1 项目页 IA 回归。
 * 钉住:列表(公共置顶 + Admin+ 新建)、详情页签(场景/用例集/集成
 * 任务/成员按 canManage)、公共项目页签挂原公共页、旧公共深链重定向、
 * 在本项目新建(?projectId= 深链进编排器)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ProjectsView from '@/views/ProjectsView.vue'
import ProjectDetailView from '@/views/ProjectDetailView.vue'
import PublicProjectRedirect from '@/views/PublicProjectRedirect.vue'
import * as projectsApi from '@/api/projects'
import * as composerApi from '@/api/scenario-composer'
import * as suitesApi from '@/api/suites'
import * as integrationApi from '@/api/integration'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/api/projects', () => ({
  listProjects: vi.fn(),
  getProject: vi.fn(),
  createProject: vi.fn(),
  listMembers: vi.fn().mockResolvedValue([]),
  addMember: vi.fn(),
  patchMember: vi.fn(),
  removeMember: vi.fn(),
}))
vi.mock('@/api/scenario-composer', () => ({
  listScenarios: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 }),
}))
vi.mock('@/api/suites', () => ({
  listSuites: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 100 }),
  createSuite: vi.fn(),
}))
vi.mock('@/api/integration', () => ({
  listIntegrationTasks: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/api/handoff', () => ({
  getRoster: vi.fn().mockResolvedValue({ items: [] }),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))
vi.mock('@/utils/errorFallback', () => ({
  showError: vi.fn(),
}))

const PUB = { id: 1, name: '公共', kind: 'public', description: '', memberCount: 0,
  myRole: null, canManage: false }
const MINE = { id: 7, name: '我的项目', kind: 'normal', description: 'd', memberCount: 2,
  myRole: 'member', canManage: false, scenarioCount: 3, suiteCount: 1, taskCount: 2,
  defaultEnvironmentId: null, defaultEnvironmentName: null }

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/projects', component: { template: '<div/>' } },
      { path: '/projects/:id(\\d+)', component: { template: '<div/>' } },
      { path: '/composer/:scenarioId', component: { template: '<div/>' } },
      { path: '/scenarios/mine', component: { template: '<div/>' } },
      { path: '/suites', component: { template: '<div/>' } },
    ],
  })
}

async function mountView(comp: typeof ProjectsView, opts: {
  isAdmin?: boolean; path?: string; router?: Router;
} = {}) {
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  auth.currentUser = {
    id: 1, username: 'alice', display_name: 'Alice',
    role: opts.isAdmin ? 'super_admin' : 'user',
  } as never
  auth.capabilities = opts.isAdmin ? ['users.manage', 'ops.write'] : []
  const router = opts.router ?? makeRouter()
  if (!opts.router) {
    await router.push(opts.path ?? '/projects')
    await router.isReady()
  }
  const w = mount(comp, { global: { plugins: [router] } })
  await flushPromises()
  return w
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(projectsApi.listProjects).mockReset()
  vi.mocked(projectsApi.getProject).mockReset()
})

describe('ProjectsView — 项目列表', () => {
  it('公共项目置顶渲染;普通用户无「新建项目」', async () => {
    // 后端排序保证公共置顶 —— 视图按返回序渲染
    vi.mocked(projectsApi.listProjects).mockResolvedValue([PUB, MINE] as never)
    const w = await mountView(ProjectsView, { isAdmin: false })
    const cards = w.findAll('[data-testid^="prj-card-"]')
    expect(cards.length).toBe(2)
    expect(cards[0].attributes('data-testid')).toBe('prj-card-1')  // 公共置顶(后端序)
    expect(cards[0].find('[data-testid="prj-public-badge"]').exists()).toBe(true)
    expect(w.find('[data-testid="prj-create"]').exists()).toBe(false)
    w.unmount()
  })

  it('Admin+ 有「新建项目」入口', async () => {
    vi.mocked(projectsApi.listProjects).mockResolvedValue([PUB] as never)
    const w = await mountView(ProjectsView, { isAdmin: true })
    expect(w.find('[data-testid="prj-create"]').exists()).toBe(true)
    w.unmount()
  })
})

describe('ProjectDetailView — 详情页签', () => {
  it('普通项目:场景页签按 projectId 拉取,可「在本项目新建」', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(MINE as never)
    const router = makeRouter()
    await router.push('/projects/7')
    await router.isReady()
    const w = await mountView(ProjectDetailView, { isAdmin: false, router })
    expect(w.find('[data-testid="prj-detail-name"]').text()).toBe('我的项目')
    expect(composerApi.listScenarios).toHaveBeenCalledWith(
      expect.objectContaining({ projectId: 7 }))
    expect(w.find('[data-testid="prj-scen-new"]').exists()).toBe(true)
    expect(w.find('[data-testid="prj-tab-members"]').exists()).toBe(false)  // canManage=false
    w.unmount()
  })

  it('canManage:成员页签可见 + 页签计数来自详情端点', async () => {
    const managed = { ...MINE, myRole: 'admin', canManage: true }
    vi.mocked(projectsApi.getProject).mockResolvedValue(managed as never)
    const router = makeRouter()
    await router.push('/projects/7?tab=members')
    await router.isReady()
    const w = await mountView(ProjectDetailView, { isAdmin: false, router })
    expect(w.find('[data-testid="prj-tab-members"]').exists()).toBe(true)
    expect(w.find('[data-testid="prj-members-panel"]').exists()).toBe(true)
    expect(w.find('[data-testid="prj-tab-scenarios"]').text()).toContain('3')
    w.unmount()
  })

  it('公共项目:场景页签挂原公共场景页(visibility=public 口径)', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(PUB as never)
    const router = makeRouter()
    await router.push('/projects/1')
    await router.isReady()
    const w = await mountView(ProjectDetailView, { isAdmin: false, router })
    // 异步组件:等动态 import 落定后公共页挂载(不拉项目过滤列表)
    await vi.dynamicImportSettled()
    await flushPromises()
    expect(w.find('[data-testid="pub-search"]').exists()).toBe(true)
    // 公共页自己的拉取 = visibility=public(兼容别名),不带 projectId
    expect(composerApi.listScenarios).toHaveBeenCalledWith(
      expect.objectContaining({ visibility: 'public' }))
    expect(composerApi.listScenarios).not.toHaveBeenCalledWith(
      expect.objectContaining({ projectId: 1 }))
    expect(w.find('[data-testid="prj-scen-new"]').exists()).toBe(false)  // 公共不可直建
    w.unmount()
  })

  it('非成员/不存在:404 态回落项目列表链接', async () => {
    vi.mocked(projectsApi.getProject).mockRejectedValue(new Error('404'))
    const w = await mountView(ProjectDetailView, { isAdmin: false, path: '/projects/99' })
    expect(w.text()).toContain('项目不存在或无权访问')
    w.unmount()
  })

  it('用例集页签:按 projectId 拉取 + 在本项目新建走 createSuite({projectId})', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(MINE as never)
    vi.mocked(suitesApi.createSuite).mockResolvedValue(
      { suiteId: 11, name: 'x', isDraft: false } as never)
    const router = makeRouter()
    await router.push('/projects/7?tab=suites')
    await router.isReady()
    const w = await mountView(ProjectDetailView, { isAdmin: false, router })
    expect(suitesApi.listSuites).toHaveBeenCalledWith(
      expect.objectContaining({ projectId: 7 }))
    await w.find('[data-testid="prj-suite-new"]').trigger('click')
    await flushPromises()
    expect(suitesApi.createSuite).toHaveBeenCalledWith(
      expect.objectContaining({ projectId: 7 }))
    w.unmount()
  })

  it('集成任务页签:?projectId 过滤', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(MINE as never)
    const router = makeRouter()
    await router.push('/projects/7?tab=tasks')
    await router.isReady()
    const w = await mountView(ProjectDetailView, { isAdmin: false, router })
    expect(integrationApi.listIntegrationTasks).toHaveBeenCalledWith(7)
    w.unmount()
  })
})

describe('PublicProjectRedirect — 旧公共深链兜底', () => {
  it('解析公共项目后 replace 到项目页对应页签', async () => {
    vi.mocked(projectsApi.listProjects).mockResolvedValue([PUB] as never)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/scenarios/public', component: PublicProjectRedirect,
          meta: { tab: 'scenarios' } },
        { path: '/projects/:id(\\d+)', component: { template: '<div/>' } },
      ],
    })
    await router.push('/scenarios/public')
    await router.isReady()
    mount(PublicProjectRedirect, { global: { plugins: [router] } })
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/projects/1?tab=scenarios')
  })

  it('解析失败回落项目列表', async () => {
    vi.mocked(projectsApi.listProjects).mockRejectedValue(new Error('net'))
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/suites/public', component: PublicProjectRedirect,
          meta: { tab: 'suites' } },
        { path: '/projects', component: { template: '<div/>' } },
      ],
    })
    await router.push('/suites/public')
    await router.isReady()
    mount(PublicProjectRedirect, { global: { plugins: [router] } })
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/projects')
  })
})
