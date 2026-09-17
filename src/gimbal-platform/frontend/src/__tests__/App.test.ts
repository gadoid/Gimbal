/**
 * App.vue — 三态 chrome 切换(评审补充的测试缺口)。
 *
 * 未认证 → 无 chrome(登录/注册裸渲染);认证 + meta.chromeMode
 * 'collapsed' → 收拢顶条无侧栏;默认 'full' → 侧边栏两栏。
 * 配套 router.meta.test.ts 钉住真实路由表的 chromeMode 标注。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '@/App.vue'
import { useAuthStore } from '@/stores/auth'

function makeRouter(initial: string) {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: { template: '<div class="login-page"/>' } },
      { path: '/home', component: { template: '<div/>' }, meta: { requiresAuth: true } },
      { path: '/scenarios', component: { template: '<div/>' }, meta: { requiresAuth: true } },
      { path: '/constants', component: { template: '<div/>' }, meta: { requiresAuth: true, chromeMode: 'collapsed' } },
    ],
  })
}

async function mountApp(path: string, opts: { authed: boolean }) {
  const auth = useAuthStore()
  if (opts.authed) {
    auth.accessToken = 'tok'
    auth.currentUser = { id: 1, username: 'alice', display_name: 'Alice', is_admin: false } as never
  }
  const router = makeRouter(path)
  router.push(path)
  await router.isReady()
  const w = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return w
}

describe('App — 三态 chrome', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('未认证:无侧栏、无收拢顶条(登录页裸渲染)', async () => {
    const w = await mountApp('/login', { authed: false })
    expect(w.find('.sidebar').exists()).toBe(false)
    expect(w.find('.collapsed-topbar').exists()).toBe(false)
    expect(w.find('.login-page').exists()).toBe(true)
    w.unmount()
  })

  it('认证 + full(默认):侧边栏在场、内容区让位 200px', async () => {
    const w = await mountApp('/scenarios', { authed: true })
    expect(w.find('.sidebar').exists()).toBe(true)
    expect(w.find('.collapsed-topbar').exists()).toBe(false)
    w.unmount()
  })

  it('认证 + collapsed(/constants):收拢顶条在场、无侧栏、面包屑指向常量池', async () => {
    const w = await mountApp('/constants', { authed: true })
    expect(w.find('.sidebar').exists()).toBe(false)
    expect(w.find('.collapsed-topbar').exists()).toBe(true)
    expect(w.find('.collapsed-topbar').text()).toContain('常量池')
    w.unmount()
  })
})
