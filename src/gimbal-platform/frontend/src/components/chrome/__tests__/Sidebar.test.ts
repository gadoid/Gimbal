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
      { path: '/scenarios', component: { template: '<div/>' } },
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
  router.push(opts.path ?? '/scenarios')
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
    // 常量池不占侧边栏坑位 → 7 条:工作台/场景库/认证/传递/适配/执行/用户
    expect(links.length).toBe(7)
    const hrefs = links.map((l) => l.attributes('href'))
    expect(hrefs).toEqual([
      '/home', '/scenarios', '/auths', '/carry-config', '/adaptations', '/executions', '/admin/users',
    ])
    w.unmount()
  })

  it('组标签为纯文本:场景/服务/执行中心/平台,不是可点页(F-sitemap)', async () => {
    const w = await mountSidebar({ isAdmin: true })
    const labels = w.findAll('.group-label').map((l) => l.text())
    expect(labels).toEqual(['场景', '服务', '执行中心', '平台'])
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

  it('member 不见 用户管理/传递字段,其余 5 条可见', async () => {
    const w = await mountSidebar({ isAdmin: false })
    const hrefs = w.findAll('a.nav-item').map((l) => l.attributes('href'))
    expect(hrefs).not.toContain('/admin/users')
    expect(hrefs).not.toContain('/carry-config')
    expect(hrefs.length).toBe(5)
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
    const w = await mountSidebar({ isAdmin: true, path: '/scenarios' })
    expect(w.find('.nav-badge').exists()).toBe(true)
    expect(w.find('.nav-badge').text()).toBe('1')
    w.unmount()
  })

  it('member:不发 diff,手工置数也不显示(admin-only 徽标)', async () => {
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [], anomalies: [], baselinedNow: 0,
    } as never)
    const w = await mountSidebar({ isAdmin: false, path: '/scenarios' })
    useAuthStore() // pinia 已就绪
    const { useAdaptationsStore } = await import('@/stores/adaptations')
    useAdaptationsStore().pendingCount = 3
    await flushPromises()
    expect(w.find('.nav-badge').exists()).toBe(false)
    w.unmount()
  })

  it('登出按钮在场(身份与登出迁到侧栏底部)', async () => {
    const w = await mountSidebar({ isAdmin: true })
    expect(w.find('.logout-btn').exists()).toBe(true)
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
    expect(w.findAll('.nav-text').length).toBe(7)
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
    expect(rows.length).toBe(7)
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
    expect(labels).toEqual(['场景', '服务', '执行中心', '平台'])
    w.unmount()
  })

  it('折叠态导航仍可点(真实 <a href> 保留) + 偏好落 localStorage', async () => {
    const w = await mountSidebar({ isAdmin: true })
    await w.find('[data-testid="sb-collapse"]').trigger('click')
    const links = w.findAll('a.nav-item')
    expect(links.length).toBe(7)
    expect(links[2].attributes('href')).toBe('/auths')
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
