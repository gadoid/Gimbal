/**
 * Sidebar.vue — v2 left nav (replaces TopNav.vue; ported from TopNav.test.ts).
 * Same behaviors, grouped into 核心工作流/共享资源/后台配置 instead of one
 * flat row of links.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import Sidebar from '@/components/Sidebar.vue'
import { useAuthStore } from '@/stores/auth'
import * as adaptationsApi from '@/api/adaptations'
import { useAdaptationsStore } from '@/stores/adaptations'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/scenarios', component: { template: '<div/>' } },
      { path: '/executions', component: { template: '<div/>' } },
      { path: '/auths', component: { template: '<div/>' } },
      { path: '/adaptations', component: { template: '<div/>' } },
      { path: '/admin/users', component: { template: '<div/>' } },
      { path: '/carry-config', component: { template: '<div/>' } },
      { path: '/constants', component: { template: '<div/>' } },
    ],
  })
}

describe('Sidebar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [], anomalies: [], baselinedNow: 0,
    } as never)
  })

  it('renders seven real router-link anchors across three groups', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    auth.currentUser = { id: 1, username: 'alice', is_admin: true } as never

    const router = makeRouter()
    router.push('/scenarios')
    await router.isReady()

    const w = mount(Sidebar, {
      global: { plugins: [router, ElementPlus] },
    })

    const links = w.findAll('a.nav-entry')
    expect(links.length).toBe(7)

    const hrefs = links.map((l) => l.attributes('href'))
    expect(hrefs).toContain('/scenarios')
    expect(hrefs).toContain('/executions')
    expect(hrefs).toContain('/adaptations')
    expect(hrefs).toContain('/auths')
    expect(hrefs).toContain('/constants')
    expect(hrefs).toContain('/admin/users')
    expect(hrefs).toContain('/carry-config')

    const groupLabels = w.findAll('.nav-section-label').map((n) => n.text())
    expect(groupLabels).toEqual(['核心工作流', '共享资源', '后台配置'])
  })

  it('highlights the active route', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    auth.currentUser = { id: 1, username: 'alice', is_admin: true } as never

    const router = makeRouter()
    router.push('/admin/users')
    await router.isReady()

    const w = mount(Sidebar, {
      global: { plugins: [router, ElementPlus] },
    })

    const active = w.findAll('a.nav-entry.active')
    expect(active.length).toBe(1)
    expect(active[0].attributes('href')).toBe('/admin/users')
  })

  it('hides the admin-only 用户管理/传递字段 entries — and the 后台配置 group — from members', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    auth.currentUser = { id: 1, username: 'alice', is_admin: false } as never

    const router = makeRouter()
    router.push('/scenarios')
    await router.isReady()

    const w = mount(Sidebar, {
      global: { plugins: [router, ElementPlus] },
    })

    const hrefs = w.findAll('a.nav-entry').map((l) => l.attributes('href'))
    expect(hrefs).not.toContain('/admin/users')
    expect(hrefs).not.toContain('/carry-config')
    expect(hrefs.length).toBe(5)

    const groupLabels = w.findAll('.nav-section-label').map((n) => n.text())
    expect(groupLabels).toEqual(['核心工作流', '共享资源'])
  })

  it('does not crash when not authenticated', () => {
    // No currentUser / accessToken
    const router = makeRouter()
    const w = mount(Sidebar, {
      global: { plugins: [router, ElementPlus] },
    })
    // App.vue mounts Sidebar only when isAuthenticated, so we still render
    // a non-empty aside but the auth-aware bits should be empty.
    expect(w.find('.sidebar').exists()).toBe(true)
  })

  it('shows the pending-changes badge for admins only', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'

    const router = makeRouter()
    router.push('/scenarios')
    await router.isReady()

    // admin:watch 静默拉 diff(此处覆写 beforeEach 的空报告 → 1 条 pending)
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [{ endpointId: 'e', fromVersion: '1', toVersion: '2' }],
      anomalies: [],
      baselinedNow: 0,
    } as never)
    auth.currentUser = { id: 1, username: 'alice', is_admin: true } as never
    let w = mount(Sidebar, { global: { plugins: [router, ElementPlus] } })
    await flushPromises()
    expect(w.find('.nav-badge').exists()).toBe(true)
    expect(w.find('.nav-badge').text()).toBe('1')
    w.unmount()

    // member:不发 diff,手工置数也不显示徽章(v-if isAdmin)
    setActivePinia(createPinia())
    // 同一 it 内 admin 半场已调过一次;清计数后断言 member 挂载零调用
    vi.mocked(adaptationsApi.catalogDiff).mockClear()
    const auth2 = useAuthStore()
    auth2.accessToken = 'tok'
    auth2.currentUser = { id: 2, username: 'peon', is_admin: false } as never
    useAdaptationsStore().pendingCount = 3
    w = mount(Sidebar, { global: { plugins: [router, ElementPlus] } })
    await flushPromises()
    expect(w.find('.nav-badge').exists()).toBe(false)
    expect(adaptationsApi.catalogDiff).not.toHaveBeenCalled()
    w.unmount()
  })
})
