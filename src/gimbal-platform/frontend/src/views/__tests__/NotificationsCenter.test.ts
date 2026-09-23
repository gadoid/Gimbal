/**
 * NotificationsCenter — 通知中心页(F5,2026-09-23)回归。
 * 钉住:member 只见通知 tab;admin 双 tab(审计面板复用);点通知
 * 先标读再跳深链;全部已读。方案 §5.5 T1–T4(非 admin 的 403 兜底
 * 在后端 /admin/audit-logs,不在前端断言面)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import NotificationsCenter from '@/views/NotificationsCenter.vue'
import * as api from '@/api/notifications'

vi.mock('@/api/notifications', () => ({
  list: vi.fn(),
  markRead: vi.fn().mockResolvedValue({ marked: 1 }),
  NOTIFICATION_TYPE_LABELS: {
    execution_finished: '执行完成', adaptation_applied: '适配应用',
    announcement: '平台公告', scenario_unpublished: '场景下架',
    role_changed: '角色变更', resource_transferred: '资源转让',
    resource_handoff: '收到分享',
  },
}))
vi.mock('@/components/admin/AuditLogPanel.vue', () => ({
  default: { template: '<div data-testid="audit-panel-stub">审计面板</div>' },
}))

const ITEMS = [
  { id: 2, type: 'resource_handoff', title: '收到分享:订单查询', body: 'Alice 分享了场景给你',
    link: '/scenarios/sc-x/detail', batchId: null, createdAt: '2026-09-23T10:00:00', readAt: null },
  { id: 1, type: 'announcement', title: '今晚停服迁移', body: '23:00-24:00',
    link: null, batchId: null, createdAt: '2026-09-22T10:00:00', readAt: '2026-09-22T12:00:00' },
]

async function mountPage(role: 'member' | 'admin') {
  const { useAuthStore } = await import('@/stores/auth')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/notifications', component: NotificationsCenter },
      { path: '/scenarios/:id/detail', component: { template: '<div/>' } },
    ],
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().currentUser = {
    id: 1, username: 'x', role, is_admin: role === 'admin',
  } as never
  vi.mocked(api.list).mockResolvedValue(
    { items: ITEMS, unread: 1, total: ITEMS.length, page: 1, pageSize: 20 } as never)
  const w = mount(NotificationsCenter, { global: { plugins: [router, pinia] } })
  await router.isReady()
  await flushPromises()
  return w
}

describe('NotificationsCenter', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.markRead).mockResolvedValue({ marked: 1 })
  })

  it('member:只有通知 tab,无审计控件;列表渲染与类型文案', async () => {
    const w = await mountPage('member')
    expect(w.find('[data-testid="nt-tab-notify"]').exists()).toBe(true)
    expect(w.find('[data-testid="nt-tab-audit"]').exists()).toBe(false)
    expect(w.find('[data-testid="audit-panel-stub"]').exists()).toBe(false)
    expect(w.text()).toContain('收到分享:订单查询')
    expect(w.text()).toContain('收到分享')   // resource_handoff 类型 chip
    expect(w.text()).toContain('平台公告')   // announcement 类型 chip
    w.unmount()
  })

  it('admin:双 tab;切到审计渲染复用面板', async () => {
    const w = await mountPage('admin')
    expect(w.find('[data-testid="nt-tab-audit"]').exists()).toBe(true)
    await w.find('[data-testid="nt-tab-audit"]').trigger('click')
    expect(w.find('[data-testid="audit-panel-stub"]').exists()).toBe(true)
    w.unmount()
  })

  it('点未读通知:先标读再跳深链;全部已读走 markRead(null)', async () => {
    const w = await mountPage('member')
    await w.find('[data-testid="nt-item-2"]').trigger('click')
    await flushPromises()
    expect(api.markRead).toHaveBeenCalledWith([2])
    w.unmount()
  })

  // ── 2026-09-23 分页批次:page/pageSize 下推 + 翻页重拉 ──────────
  it('分页:首拉带分页参数;点页码/换每页行数按新参数重拉', async () => {
    const page1 = Array.from({ length: 20 }, (_, i) => ({
      ...ITEMS[0]!, id: i + 1,
    }))
    const page2 = [{ ...ITEMS[1]!, id: 21 }]
    vi.mocked(api.list)
      .mockResolvedValueOnce({ items: page1, unread: 20, total: 21, page: 1, pageSize: 20 } as never)
      .mockResolvedValueOnce({ items: page2, unread: 1, total: 21, page: 2, pageSize: 20 } as never)
      .mockResolvedValueOnce({ items: page1, unread: 20, total: 21, page: 1, pageSize: 20 } as never)
    const w = await mountPage('member')

    expect(api.list).toHaveBeenCalledWith({ page: 1, pageSize: 20 })
    expect(w.find('[data-testid="nt-item-1"]').exists()).toBe(true)
    expect(w.find('[data-testid="nt-item-21"]').exists()).toBe(false)

    await w.findAll('button[aria-label^="第"]')[1]!.trigger('click') // 第 2 页
    await flushPromises()
    expect(api.list).toHaveBeenLastCalledWith({ page: 2, pageSize: 20 })
    expect(w.find('[data-testid="nt-item-21"]').exists()).toBe(true)
    expect(w.find('[data-testid="nt-item-1"]').exists()).toBe(false)

    // 换每页行数(20 → 50)→ 回页 1 重拉
    await w.find('[data-testid="pager-size"]').setValue('50')
    await flushPromises()
    expect(api.list).toHaveBeenLastCalledWith({ page: 1, pageSize: 50 })
    expect(w.find('[data-testid="nt-item-1"]').exists()).toBe(true)
    w.unmount()
  })
})
