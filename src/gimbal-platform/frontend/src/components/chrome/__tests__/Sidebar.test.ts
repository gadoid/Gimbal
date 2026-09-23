/**
 * Sidebar — Phase 1 导航范式更换的回归网(承接 TopNav.test.ts /
 * TopNav.pool.test.ts 的用例,并按四域分组扩展)。
 *
 * 结构基准 = F-sitemap v2:
 * - 置顶「工作台」入口;组标签 场景 / 服务 / 执行中心 / 平台;
 * - 常量池**不在**侧边栏(完整页经工作台深链进入,见 WorkbenchView.test);
 * - 沿用语义:adminOnly 过滤(用户管理/传递字段)、适配中心 pendingCount
 *   徽标(仅 admin 且 >0)、真实 <a href> 导航、active 高亮。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import Sidebar from '@/components/chrome/Sidebar.vue'
import { useAuthStore } from '@/stores/auth'
import { useSidebarCollapse } from '@/composables/sidebar-collapse'
import * as adaptationsApi from '@/api/adaptations'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/home', component: { template: '<div/>' } },
      { path: '/scenarios/mine', component: { template: '<div/>' } },
      { path: '/scenarios/public', component: { template: '<div/>' } },
      { path: '/scenarios/follows', component: { template: '<div/>' } },
      { path: '/executions', component: { template: '<div/>' } },
      { path: '/auths', component: { template: '<div/>' } },
      { path: '/adaptations', component: { template: '<div/>' } },
      { path: '/admin/users', component: { template: '<div/>' } },
      { path: '/carry-config', component: { template: '<div/>' } },
    ],
  })
}

async function mountSidebar(opts: { isAdmin: boolean; path?: string }) {
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  auth.currentUser = {
    id: 1,
    username: 'alice',
    display_name: 'Alice',
    is_admin: opts.isAdmin,
  } as never

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
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [], anomalies: [], baselinedNow: 0,
    } as never)
  })

  it('admin 可见全部条目:工作台置顶 + 四组条目齐备', async () => {
    const w = await mountSidebar({ isAdmin: true })
    const links = w.findAll('a.nav-item')
    // 常量池不占侧边栏坑位 → 14 条:工作台/通知(F5)/我的/公共/关注/
    // 认证/传递/适配/画像/服务信息/执行器/执行记录/数据分析/用户。
    // 字段来源分析(E2a 未建)是 span 不是 a;数据分析延后但有自己的
    // 说明页,置灰可点(§4.4)
    expect(links.length).toBe(14)
    const hrefs = links.map((l) => l.attributes('href'))
    expect(hrefs).toEqual([
      '/home', '/notifications',
      '/scenarios/mine', '/scenarios/public', '/scenarios/follows',
      // 服务组(配套方案 §4.1 顺序):画像/服务信息/认证/默认值/适配
      '/services', '/service-admin', '/auths', '/carry-config', '/adaptations',
      // 执行组(执行设计 §0):执行器/执行记录;数据分析置灰保留、可点进说明页
      '/run', '/executions', '/analytics', '/admin/users',
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

  it('组标签为纯文本:场景/服务/执行/平台,不是可点页(F-sitemap + 执行设计 §0)', async () => {
    const w = await mountSidebar({ isAdmin: true })
    const labels = w.findAll('.group-label').map((l) => l.text())
    expect(labels).toEqual(['场景', '服务', '执行', '平台'])
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
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [], anomalies: [], baselinedNow: 0,
    } as never)
  })

  it('member 不见 用户管理/传递字段/服务信息管理,其余 11 条可见', async () => {
    const w = await mountSidebar({ isAdmin: false })
    const hrefs = w.findAll('a.nav-item').map((l) => l.attributes('href'))
    expect(hrefs).not.toContain('/admin/users')
    expect(hrefs).not.toContain('/carry-config')
    expect(hrefs).not.toContain('/service-admin')
    expect(hrefs.length).toBe(11)  // +通知(F5,全员)
    w.unmount()
  })
})

describe('Sidebar — active 高亮', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [], anomalies: [], baselinedNow: 0,
    } as never)
  })

  it('当前路由高亮唯一条目', async () => {
    const w = await mountSidebar({ isAdmin: true, path: '/admin/users' })
    const active = w.findAll('a.nav-item.active')
    expect(active.length).toBe(1)
    expect(active[0].attributes('href')).toBe('/admin/users')
    w.unmount()
  })
})

describe('Sidebar — 适配中心 pendingCount 徽标(沿用 TopNav 语义)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('admin:pending>0 显示徽标数', async () => {
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [{ endpointId: 'e', fromVersion: '1', toVersion: '2' }],
      anomalies: [],
      baselinedNow: 0,
    } as never)
    const w = await mountSidebar({ isAdmin: true, path: '/scenarios/mine' })
    expect(w.find('.nav-badge').exists()).toBe(true)
    expect(w.find('.nav-badge').text()).toBe('1')
    w.unmount()
  })

  it('member:不发 diff,手工置数也不显示(admin-only 徽标)', async () => {
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [], anomalies: [], baselinedNow: 0,
    } as never)
    const w = await mountSidebar({ isAdmin: false, path: '/scenarios/mine' })
    useAuthStore() // pinia 已就绪
    const { useAdaptationsStore } = await import('@/stores/adaptations')
    useAdaptationsStore().pendingCount = 3
    await flushPromises()
    expect(w.find('.nav-badge').exists()).toBe(false)
    w.unmount()
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
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [], anomalies: [], baselinedNow: 0,
    } as never)
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
    // 15 = 14 可点(含置灰可点的数据分析;F5 +通知)+ 1 置灰 span(字段来源分析,§4.4)
    expect(w.findAll('.nav-text').length).toBe(15)
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
    expect(rows.length).toBe(15)   // 14 可点 + 1 置灰 span
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

  it('折叠仍保留一级层次组标签(场景/服务/执行中心/平台)', async () => {
    const w = await mountSidebar({ isAdmin: true })
    await w.find('[data-testid="sb-collapse"]').trigger('click')
    const labels = w.findAll('.group-label').map((l) => l.text())
    expect(labels).toEqual(['场景', '服务', '执行', '平台'])
    w.unmount()
  })

  it('折叠态导航仍可点(真实 <a href> 保留) + 偏好落 localStorage', async () => {
    const w = await mountSidebar({ isAdmin: true })
    await w.find('[data-testid="sb-collapse"]').trigger('click')
    const links = w.findAll('a.nav-item')
    expect(links.length).toBe(14)
    // 配套方案 §4.1 服务组排序:画像/服务信息在前,/auths 从索引 5 移到 7(F5 通知占 0/1 位)
    expect(links[5].attributes('href')).toBe('/services')
    expect(links[7].attributes('href')).toBe('/auths')
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
