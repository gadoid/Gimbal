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
  listDataSets: vi.fn().mockResolvedValue([{ datasetId: 'd1' }]),
  runScenario: vi.fn().mockResolvedValue({ runId: 'r-1' }),
}))
vi.mock('@/api/suites', () => ({
  listSuites: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 12 }),
  createSuite: vi.fn(),
  runSuite: vi.fn().mockResolvedValue({}),
}))
vi.mock('@/api/integration', () => ({
  listIntegrationTasks: vi.fn().mockResolvedValue([]),
  runIntegrationTask: vi.fn().mockResolvedValue({ result: { status: 'ok', durationMs: 5, error: '' } }),
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
      // 头卡「执行历史 / 监控指标」跳转落点(stitch 重建)
      { path: '/executions', component: { template: '<div/>' } },
      { path: '/analytics', component: { template: '<div/>' } },
      { path: '/suites/:rest(.*)', component: { template: '<div/>' } },
      { path: '/scenarios/:rest(.*)', component: { template: '<div/>' } },
      { path: '/integrations/:rest(.*)', component: { template: '<div/>' } },
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

describe('ProjectDetailView — stitch 重建(2026-11-18)', () => {
  // ── fixtures:普通项目三页签的行级形态 ──────────────────────────
  const SCEN = {
    meta: {
      scenarioId: 'sc-1', name: '订单创建', description: '下单主链路', module: '订单',
      priority: 1, author: 'alice', owner: 'alice', tags: [] as string[], system: ['fin'],
      updateTime: '2026-11-01T10:00:00Z',
    },
    dataSetCount: 1, schemeCount: 0, stepCount: 3, varCount: 0,
    tags: ['回归'], starred: false, visibility: 'private' as const, projectId: 7,
  }
  const SUITE = {
    suiteId: 11, name: '电商主链路', description: '正向交易回归', visibility: 'private',
    projectId: 7, mode: 'chain', memberCount: 5, rev: 1, isDraft: true,
    createdAt: null, updatedAt: null, latestRun: { passed: 3, failed: 0 }, ownerName: 'alice',
  }
  const TASK = {
    id: 42, name: '每日凌晨冒烟', ownerId: 1, mine: true, canManage: true,
    visibility: 'project', projectId: 7, targetType: 'scenario', scenarioId: 'sc-1', suiteId: null,
    schemeId: null, targetSystem: 'fin', triggerCron: '', cronText: '每天 02:00', resultPolicy: '',
    cardTemplate: '', removed: false,
    instance: {
      state: 'running', enabled: true, lastRunAt: null, lastError: '', pausedReason: '',
      nextRunAt: '2026-11-19T02:00:00Z', failStreak: 0, runStatus: 'ok', checkStatus: 'none',
      checkMessage: '', checkChangedAt: null,
    },
  }

  async function mountTab(tab: string, mocks: {
    scen?: unknown; suite?: unknown; task?: unknown[]; project?: unknown;
  }) {
    if (mocks.project) vi.mocked(projectsApi.getProject).mockResolvedValue(mocks.project as never)
    else vi.mocked(projectsApi.getProject).mockResolvedValue(MINE as never)
    if (mocks.scen !== undefined) {
      vi.mocked(composerApi.listScenarios).mockResolvedValue(
        { items: [mocks.scen], total: 1, page: 1, pageSize: 20 } as never)
    }
    if (mocks.suite !== undefined) {
      vi.mocked(suitesApi.listSuites).mockResolvedValue(
        { items: [mocks.suite], total: 1, page: 1, pageSize: 12 } as never)
    }
    if (mocks.task !== undefined) {
      vi.mocked(integrationApi.listIntegrationTasks).mockResolvedValue(mocks.task as never)
    }
    const router = makeRouter()
    await router.push(`/projects/7?tab=${tab}`)
    await router.isReady()
    const w = await mountView(ProjectDetailView, { isAdmin: false, router })
    return { w, router }
  }

  it('头卡:统计三格 + 可见性徽章 + 执行历史/监控指标跳转', async () => {
    const { w, router } = await mountTab('scenarios', { scen: SCEN })
    expect(w.find('[data-testid="prj-vis-badge"]').text()).toContain('成员可见')
    const stats = w.find('[data-testid="prj-stats"]').text()
    expect(stats).toContain('用例场景')
    expect(stats).toContain('3')       // scenarioCount
    expect(stats).toContain('1')       // suiteCount
    expect(stats).toContain('2')       // memberCount
    await w.find('[data-testid="prj-metrics"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/analytics')
    w.unmount()
  })

  it('场景表:星标/优先级/标签/筛选;⋯ 执行走 数据集全集 + 无 schemeId', async () => {
    const { w } = await mountTab('scenarios', { scen: SCEN })
    expect(w.find('[data-testid="prj-scen-name-sc-1"]').text()).toBe('订单创建')
    expect(w.find('.star-btn').exists()).toBe(true)
    expect(w.find('[data-testid="prj-scen-priority"]').exists()).toBe(true)
    expect(w.find('[data-testid="prj-scen-starred"]').exists()).toBe(true)
    expect(w.text()).toContain('P1')
    expect(w.text()).toContain('回归')
    // ⋯ 菜单 teleport 到 body:执行 = listDataSets 全集 + runScenario
    await w.find('[data-testid="prj-scen-more-sc-1"]').trigger('click')
    await flushPromises()
    const run = document.body.querySelector('[data-testid="prj-scen-run-sc-1"]') as HTMLElement
    expect(run).toBeTruthy()
    run.click()
    await flushPromises()
    expect(composerApi.runScenario).toHaveBeenCalledWith(
      expect.objectContaining({ scenarioId: 'sc-1', dataSetIds: ['d1'] }))
    w.unmount()
  })

  it('用例集卡片流:模式/草稿/统计/发布者;执行走 runSuite', async () => {
    const { w } = await mountTab('suites', { suite: SUITE })
    const card = w.find('[data-testid="prj-suite-11"]')
    expect(card.exists()).toBe(true)
    expect(card.text()).toContain('串联编排')
    expect(card.text()).toContain('草稿')
    expect(card.text()).toContain('过 3 / 败 0')
    expect(card.text()).toContain('alice')
    await w.find('[data-testid="prj-suite-run-11"]').trigger('click')
    await flushPromises()
    expect(suitesApi.runSuite).toHaveBeenCalledWith(11)
    w.unmount()
  })

  it('集成任务表:TASK 标识 / Cron 触发徽章 / 下次触发 / 状态', async () => {
    const { w } = await mountTab('tasks', { task: [TASK] })
    const row = w.find('[data-testid="prj-task-42"]')
    expect(row.text()).toContain('TASK-42')
    expect(row.text()).toContain('定时调度 (Cron)')
    expect(row.text()).toContain('下次')
    expect(row.text()).toContain('运行中')
    w.unmount()
  })

  it('集成任务:原型 _3 的状态筛选 Tab + 搜索(客户端)', async () => {
    const paused = { ...TASK, id: 43, name: '契约校对', instance: {
      ...TASK.instance, state: 'paused', nextRunAt: null,
    } }
    const { w } = await mountTab('tasks', { task: [TASK, paused] })
    expect(w.find('[data-testid="prj-task-filter-all"]').text()).toContain('2')
    expect(w.find('[data-testid="prj-task-filter-running"]').text()).toContain('1')
    expect(w.find('[data-testid="prj-task-filter-paused"]').text()).toContain('1')

    await w.find('[data-testid="prj-task-filter-paused"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="prj-task-42"]').exists()).toBe(false)
    expect(w.find('[data-testid="prj-task-43"]').exists()).toBe(true)

    await w.find('[data-testid="prj-task-filter-all"]').trigger('click')
    await w.find('[data-testid="prj-task-q"]').setValue('TASK-43')
    await flushPromises()
    expect(w.find('[data-testid="prj-task-42"]').exists()).toBe(false)
    expect(w.find('[data-testid="prj-task-43"]').exists()).toBe(true)
    w.unmount()
  })

  it('加入申请 pending → 页签红徽章', async () => {
    const { w } = await mountTab('scenarios', {
      project: { ...MINE, pendingPromotions: 2 },
    })
    const cnt = w.find('[data-testid="prj-tab-promotions"]').find('.cnt.alert')
    expect(cnt.exists()).toBe(true)
    expect(cnt.text()).toBe('2')
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
