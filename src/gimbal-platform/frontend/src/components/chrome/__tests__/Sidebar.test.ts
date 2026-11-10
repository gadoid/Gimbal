/**
 * Sidebar — Phase 1 导航范式更换的回归网(承接 TopNav.test.ts /
 * TopNav.pool.test.ts 的用例,并按四域分组扩展)。
 *
 * 结构基准 = F-sitemap v2:
 * - 置顶「工作台」入口;组标签 场景 / 服务 / 执行中心 / 平台;
 * - 常量池**不在**侧边栏(完整页经工作台深链进入,见 WorkbenchView.test);
 * - 沿用语义:adminOnly 过滤(用户管理/传递字段)、真实 <a href> 导航、
 *   active 高亮。变更适配 pendingCount 徽标随 A-6 清理(2026-10-12)删除。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import Sidebar from '@/components/chrome/Sidebar.vue'
import { useAuthStore } from '@/stores/auth'
import { useSidebarCollapse } from '@/composables/sidebar-collapse'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/home', component: { template: '<div/>' } },
      { path: '/scenarios/mine', component: { template: '<div/>' } },
      { path: '/scenarios/public', component: { template: '<div/>' } },
      { path: '/scenarios/follows', component: { template: '<div/>' } },
      { path: '/executions', component: { template: '<div/>' } },
      { path: '/suites', component: { template: '<div/>' } },
      { path: '/projects', component: { template: '<div/>' } },
      { path: '/auths', component: { template: '<div/>' } },
      { path: '/adaptations', component: { template: '<div/>' } },
      { path: '/admin/users', component: { template: '<div/>' } },
      { path: '/admin/projects', component: { template: '<div/>' } },
      { path: '/carry-config', component: { template: '<div/>' } },
    ],
  })
}

/** authz W8:能力注入取代 is_admin —— superAdmin = 表 A 全能力,
 *  普通用户 = 无能力(nav 的能力门条目全部隐藏)。 */
async function mountSidebar(opts: { isAdmin: boolean; path?: string }) {
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  auth.currentUser = {
    id: 1,
    username: 'alice',
    display_name: 'Alice',
    role: opts.isAdmin ? 'super_admin' : 'user',
  } as never
  auth.capabilities = opts.isAdmin
    ? ['users.manage', 'ops.write', 'alias.write']
    : []

  const router = makeRouter()
  router.push(opts.path ?? '/scenarios/mine')
  await router.isReady()

  const w = mount(Sidebar, { global: { plugins: [router] } })
  await flushPromises()
  return w
}

describe('Sidebar — 四域分组结构(F-sitemap 基准)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('admin 可见全部条目:工作台置顶 + 六组条目齐备', async () => {
    const w = await mountSidebar({ isAdmin: true })
    const links = w.findAll('a.nav-item')
    // 常量池不占侧边栏坑位;M2a S7.1 IA 修正:公共场景/公共用例集并入
    // 公共项目,「项目管理」收编进「项目」一级入口(−3 +1 = 17 条)。
    // 字段来源分析(E2a 未建)是 span 不是 a;数据分析延后但有自己的
    // 说明页,置灰可点(§4.4)
    expect(links.length).toBe(16)  // S7.3:−默认值
    const hrefs = links.map((l) => l.attributes('href'))
    expect(hrefs).toEqual([
      '/home', '/notifications',
      '/scenarios/follows', '/scenarios/mine',
      // 2026-11-10 IA:场景集并入「我的」组(原「用例集」组退役)
      '/suites',
      // 项目组(S7.1 一级入口:公共项目置顶 + 我参与的)
      '/projects',
      // 服务组(S7.3:默认值页退役 → 全局默认在公共项目「配置」页签)
      '/services', '/service-admin', '/auths', '/adaptations',
      // 执行组:执行器/执行记录/数据分析(置灰保留、可点进说明页);
      // 集成组:集成(从执行组迁出)
      '/run', '/executions', '/analytics',
      '/integrations',
      '/admin/users',
      // M2a S2.3:部署地址(Admin+);项目管理已收编 /projects
      '/admin/deployments',
    ])
    w.unmount()
  })

  it('§4.4 两态:字段来源分析 = 置灰 span;数据分析 = 置灰 <a>(点进说明页)', async () => {
    const w = await mountSidebar({ isAdmin: true })
    const fieldTrace = w.findAll('.nav-item').find((n) => n.text().includes('字段来源分析'))
    expect(fieldTrace).toBeTruthy()
    expect(fieldTrace!.element.tagName).toBe('SPAN')
    expect(fieldTrace!.classes()).toContain('opacity-[.42]')
    const analytics = w.findAll('a.nav-item').find((n) => n.text().includes('数据分析'))
    expect(analytics).toBeTruthy()
    expect(analytics!.attributes('href')).toBe('/analytics')
    expect(analytics!.classes()).toContain('opacity-[.42]')
    w.unmount()
  })

  it('组标签为纯文本:我的/项目/服务/执行/集成/平台,不是可点页(S7.1 IA:项目一级入口;2026-11-10:「用例集」并入「我的」)', async () => {
    const w = await mountSidebar({ isAdmin: true })
    const labels = w.findAll('.group-label').map((l) => l.text())
    expect(labels).toEqual(['我的', '项目', '服务', '执行', '集成', '平台'])
    // 组标签不得是链接
    for (const label of w.findAll('.group-label')) {
      expect(label.element.tagName).toBe('SPAN')
    }
    w.unmount()
  })

  it('常量池不在侧边栏(工作台卡片 + 深链承接)', async () => {
    const w = await mountSidebar({ isAdmin: true })
    expect(w.text()).not.toContain('常量池')
    w.unmount()
  })

  it('每条目渲染真实 <a href> 且带图标(签名回归:导航必须可点)', async () => {
    const w = await mountSidebar({ isAdmin: true })
    for (const link of w.findAll('a.nav-item')) {
      expect(link.attributes('href')).toBeTruthy()
      expect(link.find('.nav-icon').exists()).toBe(true)
    }
    w.unmount()
  })
})

describe('Sidebar — adminOnly 过滤(沿用 TopNav 语义)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('无能力者不见 用户管理/传递字段/服务信息管理,其余 13 条可见', async () => {
    const w = await mountSidebar({ isAdmin: false })
    const hrefs = w.findAll('a.nav-item').map((l) => l.attributes('href'))
    expect(hrefs).not.toContain('/admin/users')
    expect(hrefs).not.toContain('/carry-config')  // S7.3:默认值页退役
    expect(hrefs).not.toContain('/service-admin')
    expect(hrefs).toContain('/projects')  // S7.1:项目入口全员可见
    expect(hrefs.length).toBe(13)  // S7.3:默认值本就 cap-gated 不在,计数不变  // S7.3:−默认值(全局默认迁公共项目配置)
    w.unmount()
  })
})

describe('Sidebar — active 高亮', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('当前路由高亮唯一条目', async () => {
    const w = await mountSidebar({ isAdmin: true, path: '/admin/users' })
    const active = w.findAll('a.nav-item.active')
    expect(active.length).toBe(1)
    expect(active[0].attributes('href')).toBe('/admin/users')
    w.unmount()
  })

  it('S7.1 IA:公共场景/公共用例集/项目管理入口已退役(并入项目)', async () => {
    const w = await mountSidebar({ isAdmin: true })
    const hrefs = w.findAll('a.nav-item').map((l) => l.attributes('href'))
    expect(hrefs).not.toContain('/scenarios/public')
    expect(hrefs).not.toContain('/suites/public')
    expect(hrefs).not.toContain('/admin/projects')
    w.unmount()
  })

  it('前缀让位不影响父路径自身:/suites 页仍高亮「场景集」', async () => {
    const w = await mountSidebar({ isAdmin: true, path: '/suites' })
    const active = w.findAll('a.nav-item.active')
    expect(active.length).toBe(1)
    expect(active[0].attributes('href')).toBe('/suites')
    w.unmount()
  })
})

describe('Sidebar — 身份徽章', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('身份徽章在场(P2-1 起登出收进下拉;compact 态保留快捷登出)', async () => {
    const w = await mountSidebar({ isAdmin: true })
    // 展开态:身份徽章 = 下拉触发器(个人设置/登出在菜单内)
    expect(w.find('[data-testid="user-badge-trigger"]').exists()).toBe(true)
    expect(w.find('.username').text()).toBe('Alice')
    w.unmount()
  })
})

describe('Sidebar — 整体折叠(« 钮:56px 图标轨道)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // 折叠态是模块级共享 ref + localStorage:每组用例前归位展开态
    localStorage.clear()
    const { collapsed } = useSidebarCollapse()
    collapsed.value = false
  })

  afterEach(() => {
    const { collapsed } = useSidebarCollapse()
    collapsed.value = false
    localStorage.clear()
  })

  it('默认展开:brand 带 platform 文字 + 折叠钮在场', async () => {
    const w = await mountSidebar({ isAdmin: true })
    expect(w.find('aside').classes()).toContain('w-[200px]')
    expect(w.text()).toContain('platform')
    expect(w.find('[data-testid="sb-collapse"]').exists()).toBe(true)
    // 17 可点(含置灰可点的数据分析)+ 1 置灰 span(字段来源分析,§4.4)
    expect(w.findAll('.nav-text').length).toBe(17)  // S7.3:−默认值
    w.unmount()
  })

  it('点 « 折叠:56px 图标轨道 — 无文字,图标 title 提示功能名', async () => {
    const w = await mountSidebar({ isAdmin: true })
    await w.find('[data-testid="sb-collapse"]').trigger('click')

    const aside = w.find('aside')
    expect(aside.classes()).toContain('w-[56px]')
    expect(aside.classes()).not.toContain('w-[200px]')
    // 折叠后不保留文字:brand 文字与条目文字全消失
    expect(w.text()).not.toContain('platform')
    expect(w.findAll('.nav-text').length).toBe(0)
    // 二级按钮只留图标;悬浮 title = 功能名
    const rows = w.findAll('.row')
    expect(rows.length).toBe(17)   // 16 可点 + 1 置灰 span(S7.3 −默认值)
    for (const row of rows) {
      expect(row.attributes('title')).toBeTruthy()
      expect(row.find('.nav-icon').exists()).toBe(true)
    }
    expect(w.find('[title="认证管理"]').exists()).toBe(true)
    expect(w.find('[title="工作台"]').exists()).toBe(true)
    // 折叠后切换钮方向翻转(展开入口)
    expect(w.find('[data-testid="sb-collapse"]').exists()).toBe(false)
    expect(w.find('[data-testid="sb-expand"]').exists()).toBe(true)
    w.unmount()
  })

  it('折叠仍保留一级层次组标签(我的/项目/服务/执行/集成/平台)', async () => {
    const w = await mountSidebar({ isAdmin: true })
    await w.find('[data-testid="sb-collapse"]').trigger('click')
    const labels = w.findAll('.group-label').map((l) => l.text())
    expect(labels).toEqual(['我的', '项目', '服务', '执行', '集成', '平台'])
    w.unmount()
  })

  it('折叠态导航仍可点(真实 <a href> 保留) + 偏好落 localStorage', async () => {
    const w = await mountSidebar({ isAdmin: true })
    await w.find('[data-testid="sb-collapse"]').trigger('click')
    const links = w.findAll('a.nav-item')
    expect(links.length).toBe(16)  // S7.3:−默认值
    // 场景集随「我的」组第三位(F5 通知占 0/1 位):suites=4 / 项目=5 / services=6
    expect(links[4].attributes('href')).toBe('/suites')
    expect(links[5].attributes('href')).toBe('/projects')
    expect(links[6].attributes('href')).toBe('/services')
    expect(localStorage.getItem('chrome.sidebar.collapsed:v1')).toBe('1')
    w.unmount()
  })

  it('折叠偏好跨"刷新"保持(composable 重导出读 localStorage)', async () => {
    localStorage.setItem('chrome.sidebar.collapsed:v1', '1')
    vi.resetModules()
    const { useSidebarCollapse: freshCollapse } = await import('@/composables/sidebar-collapse')
    expect(freshCollapse().collapsed.value).toBe(true)
    // 归位共享 ref,避免污染后续用例(重置后的模块是同一注册表实例)
    freshCollapse().collapsed.value = false
  })
})
