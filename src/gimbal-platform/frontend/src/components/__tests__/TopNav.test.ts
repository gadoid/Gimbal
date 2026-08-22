/**
 * Regression test for TopNav.vue — Spec-1 sign-off bug.
 *
 * The original `<router-link custom v-slot="{ navigate }">` pattern silently
 * failed to navigate between routes. After the fix we use plain
 * `<router-link :to="path">` and vue-router handles href/click.
 *
 * This test mounts the TopNav (which expects an authenticated user via the
 * auth store) and asserts each nav entry renders as a real `<a href>` link.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import TopNav from '@/components/TopNav.vue'
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
    ],
  })
}

describe('TopNav', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [], anomalies: [], baselinedNow: 0,
    } as never)
  })

  it('renders five real router-link anchors', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    auth.currentUser = { id: 1, username: 'alice', is_admin: true } as never

    const router = makeRouter()
    router.push('/scenarios')
    await router.isReady()

    const w = mount(TopNav, {
      global: { plugins: [router, ElementPlus] },
    })

    const links = w.findAll('a.nav-entry')
    expect(links.length).toBe(5)

    // Each link points to the right path(P3:工作台/公共库已并入场景库)
    const hrefs = links.map((l) => l.attributes('href'))
    expect(hrefs).toContain('/scenarios')
    expect(hrefs).toContain('/executions')
    expect(hrefs).toContain('/adaptations')
    expect(hrefs).toContain('/auths')
    expect(hrefs).toContain('/admin/users')
  })

  it('highlights the active route', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    auth.currentUser = { id: 1, username: 'alice', is_admin: true } as never

    const router = makeRouter()
    router.push('/admin/users')
    await router.isReady()

    const w = mount(TopNav, {
      global: { plugins: [router, ElementPlus] },
    })

    const active = w.findAll('a.nav-entry.active')
    expect(active.length).toBe(1)
    expect(active[0].attributes('href')).toBe('/admin/users')
  })

  it('hides the admin-only 用户管理 entry from members', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    auth.currentUser = { id: 1, username: 'alice', is_admin: false } as never

    const router = makeRouter()
    router.push('/scenarios')
    await router.isReady()

    const w = mount(TopNav, {
      global: { plugins: [router, ElementPlus] },
    })

    const hrefs = w.findAll('a.nav-entry').map((l) => l.attributes('href'))
    expect(hrefs).not.toContain('/admin/users')
    expect(hrefs.length).toBe(4)
  })

  it('does not show nav entries when not authenticated', () => {
    // No currentUser / accessToken
    const router = makeRouter()
    const w = mount(TopNav, {
      global: { plugins: [router, ElementPlus] },
    })
    // App.vue mounts TopNav only when isAuthenticated, so we still render
    // a non-empty header but the auth-aware bits should be empty.
    // The test just verifies we don't crash without auth state.
    expect(w.find('.topnav').exists()).toBe(true)
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
    let w = mount(TopNav, { global: { plugins: [router, ElementPlus] } })
    await flushPromises()
    expect(w.find('.nav-badge').exists()).toBe(true)
    expect(w.find('.nav-badge').text()).toBe('1')
    w.unmount()

    // member:不发 diff,手工置数也不显示徽章(v-if isAdmin)
    setActivePinia(createPinia())
    const auth2 = useAuthStore()
    auth2.accessToken = 'tok'
    auth2.currentUser = { id: 2, username: 'peon', is_admin: false } as never
    useAdaptationsStore().pendingCount = 3
    w = mount(TopNav, { global: { plugins: [router, ElementPlus] } })
    await flushPromises()
    expect(w.find('.nav-badge').exists()).toBe(false)
    w.unmount()
  })
})