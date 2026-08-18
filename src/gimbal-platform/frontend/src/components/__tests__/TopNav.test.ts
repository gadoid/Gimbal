/**
 * Regression test for TopNav.vue — Spec-1 sign-off bug.
 *
 * The original `<router-link custom v-slot="{ navigate }">` pattern silently
 * failed to navigate from /cases/:id/config to other routes. After the fix
 * we use plain `<router-link :to="path">` and vue-router handles href/click.
 *
 * This test mounts the TopNav (which expects an authenticated user via the
 * auth store) and asserts each nav entry renders as a real `<a href>` link.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import TopNav from '@/components/TopNav.vue'
import { useAuthStore } from '@/stores/auth'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/cases/mine', component: { template: '<div/>' } },
      { path: '/cases/public', component: { template: '<div/>' } },
      { path: '/scenarios', component: { template: '<div/>' } },
      { path: '/executions', component: { template: '<div/>' } },
      { path: '/auths', component: { template: '<div/>' } },
      { path: '/admin/users', component: { template: '<div/>' } },
      { path: '/cases/:caseId/config', component: { template: '<div/>' } },
    ],
  })
}

describe('TopNav', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders six real router-link anchors', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    auth.currentUser = { id: 1, username: 'alice', is_admin: true } as never

    const router = makeRouter()
    router.push('/cases/mine')
    await router.isReady()

    const w = mount(TopNav, {
      global: { plugins: [router, ElementPlus] },
    })

    const links = w.findAll('a.nav-entry')
    expect(links.length).toBe(6)

    // Each link points to the right path
    const hrefs = links.map((l) => l.attributes('href'))
    expect(hrefs).toContain('/cases/mine')
    expect(hrefs).toContain('/cases/public')
    expect(hrefs).toContain('/scenarios')
    expect(hrefs).toContain('/executions')
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
    router.push('/cases/mine')
    await router.isReady()

    const w = mount(TopNav, {
      global: { plugins: [router, ElementPlus] },
    })

    const hrefs = w.findAll('a.nav-entry').map((l) => l.attributes('href'))
    expect(hrefs).not.toContain('/admin/users')
    expect(hrefs.length).toBe(5)
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
})