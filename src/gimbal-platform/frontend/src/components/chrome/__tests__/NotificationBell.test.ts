/**
 * NotificationBell — 弹层管理收口(2026-11-12)。
 *
 * 钉住:① 弹层不再内嵌按 type 开关(偏好管理归个人设置 #notify,
 * 弹层只管通知流水);② 底部动作序 = 查看全部 → 管理通知类型;
 * ③ 点「管理通知类型」关弹层并深链 /profile/account#notify。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import NotificationBell from '@/components/chrome/NotificationBell.vue'
import * as api from '@/api/notifications'

// Popover 壳透传渲染(reka portal/定位在 jsdom 无意义,内容直接铺平)
vi.mock('@/components/ui/popover', () => ({
  Popover: { template: '<div><slot /></div>' },
  PopoverAnchor: { template: '<span><slot /></span>' },
  PopoverTrigger: { template: '<span class="trigger-slot"><slot /></span>' },
  PopoverContent: { template: '<div class="content-slot"><slot /></div>' },
}))

vi.mock('@/api/notifications', () => ({
  unreadCount: vi.fn().mockResolvedValue({ count: 2 }),
  list: vi.fn().mockResolvedValue({ items: [], unread: 2 }),
  markRead: vi.fn().mockResolvedValue({}),
  // 弹层不再读/写偏好(管理在个人设置);留 mock 防误用即可
  getPreferences: vi.fn().mockRejectedValue(new Error('should not be called')),
  putPreferences: vi.fn().mockRejectedValue(new Error('should not be called')),
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/notifications', component: { template: '<div/>' } },
      { path: '/profile/account', component: { template: '<div/>' } },
    ],
  })
}

async function mountBell() {
  const router = makeRouter()
  await router.push('/')
  await router.isReady()
  const w = mount(NotificationBell, { global: { plugins: [router] } })
  await flushPromises()
  return { w, router }
}

describe('NotificationBell — 弹层管理收口', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('弹层无「通知开关」区(偏好管理归个人设置),偏好 API 不被调用', async () => {
    const { w } = await mountBell()
    expect(w.text()).not.toContain('通知开关')
    expect(api.getPreferences).not.toHaveBeenCalled()
    expect(api.putPreferences).not.toHaveBeenCalled()
    w.unmount()
  })

  it('底部动作序:查看全部 → 管理通知类型(查看全部下面)', async () => {
    const { w } = await mountBell()
    const viewAll = w.get('[data-testid="bell-view-all"]')
    const manage = w.get('[data-testid="bell-manage"]')
    // DOM 相邻:管理按钮紧跟查看全部(同一父,且查看全部在前)
    expect(manage.element.previousElementSibling).toBe(viewAll.element)
    w.unmount()
  })

  it('点「管理通知类型」→ 深链 /profile/account#notify', async () => {
    const { w, router } = await mountBell()
    await w.get('[data-testid="bell-manage"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/profile/account')
    expect(router.currentRoute.value.hash).toBe('#notify')
    w.unmount()
  })

  it('查看全部仍进通知中心', async () => {
    const { w, router } = await mountBell()
    await w.get('[data-testid="bell-view-all"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/notifications')
    w.unmount()
  })
})
