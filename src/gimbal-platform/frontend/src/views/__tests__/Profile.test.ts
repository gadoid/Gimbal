/**
 * Profile — 个人设置页(P2-1)。
 * 钉住:昵称自改走 PATCH /users/{self};改密走 /auth/change-password
 * 且旧密码错误有人话;通知偏好开关入面板。
 */
import { describe, it, expect, beforeAll, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import Profile from '@/views/Profile.vue'
import { useAuthStore } from '@/stores/auth'
import * as profileApi from '@/api/profile'
import * as usersApi from '@/api/users'
import * as notificationsApi from '@/api/notifications'

vi.mock('@/api/profile', () => ({
  changePassword: vi.fn(),
  // P3 身份卡数据面:/me/summary
  getSummary: vi.fn().mockResolvedValue({}),
}))
vi.mock('@/api/users', () => ({ patch: vi.fn() }))
vi.mock('@/api/notifications', () => ({
  getPreferences: vi.fn().mockResolvedValue({ off: [] }),
  putPreferences: vi.fn().mockResolvedValue({ off: [] }),
  NOTIFICATION_TYPE_LABELS: {
    execution_finished: '执行完成', announcement: '平台公告',
  },
}))
// P2 令牌区块(TokensSection)不能打真网络
vi.mock('@/api/access-tokens', () => ({
  listAccessTokens: vi.fn().mockResolvedValue(
    { items: [], quota: { used: 0, limit: 5 } }),
  getScopeCandidates: vi.fn().mockResolvedValue({ aliases: [], auths: [] }),
}))

// P2 锚点分区的滚动高亮用 IntersectionObserver(jsdom 不提供,给空实现)
beforeAll(() => {
  if (!('IntersectionObserver' in globalThis)) {
    class IO {
      observe(): void { /* noop */ }
      unobserve(): void { /* noop */ }
      disconnect(): void { /* noop */ }
      takeRecords(): IntersectionObserverEntry[] { return [] }
    }
    ;(globalThis as Record<string, unknown>).IntersectionObserver = IO
  }
})

function mountPage() {
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  auth.currentUser = {
    id: 7, username: 'alice', display_name: 'Alice', role: 'user',
    is_active: true, is_admin: false,
  } as never
  // P2 锚点分区后页面含 RouterLink(令牌深链等)→ 注入 router
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:all(.*)', component: { template: '<div/>' } }],
  })
  return mount(Profile, {
    global: {
      plugins: [router],
      stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
    },
  })
}

describe('Profile — 个人设置(P2-1)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // clearAllMocks 会清掉工厂里的默认返回值 —— 重建
    vi.mocked(notificationsApi.getPreferences).mockResolvedValue({ off: [] })
    vi.mocked(notificationsApi.putPreferences).mockResolvedValue({ off: [] })
  })

  it('昵称自改:PATCH /users/{self} 只带 display_name', async () => {
    vi.mocked(usersApi.patch).mockResolvedValue({
      id: 7, username: 'alice', display_name: 'Alice2', role: 'user',
      is_active: true, created_at: 'x',
    } as never)
    const w = mountPage()
    await flushPromises()
    await w.find('[data-testid="profile-display-name"]').setValue('Alice2')
    await w.find('[data-testid="profile-save-name"]').trigger('submit')
    await flushPromises()
    expect(usersApi.patch).toHaveBeenCalledWith(7, { display_name: 'Alice2' })
    w.unmount()
  })

  it('改密:changePassword(old, new);旧密码错给出人话', async () => {
    vi.mocked(profileApi.changePassword).mockRejectedValue(
      Object.assign(new Error('422 bad_old_password'), { status: 422 }))
    const w = mountPage()
    await flushPromises()
    await w.find('[data-testid="profile-old-pw"]').setValue('wrong-old')
    await w.find('[data-testid="profile-new-pw"]').setValue('NewPass-123')
    await w.find('[data-testid="profile-change-pw"]').trigger('submit')
    await flushPromises()
    expect(profileApi.changePassword).toHaveBeenCalledWith(
      'wrong-old', 'NewPass-123',
      // v4 D12:改密两个勾选默认开(令牌失效 + 退出其他会话)
      { invalidateTokens: true, logoutOthers: true })
    expect(w.text()).toContain('旧密码不正确')
    w.unmount()
  })

  it('通知偏好:开关切换写回 putPreferences', async () => {
    const w = mountPage()
    await flushPromises()
    expect(notificationsApi.getPreferences).toHaveBeenCalled()
    // Switch(radix)点击即翻转 → emit update:modelValue(真实用户路径)
    const sw = w.find('[data-testid="profile-pref-announcement"]')
    await sw.trigger('click')
    await flushPromises()
    expect(notificationsApi.putPreferences).toHaveBeenCalledWith(['announcement'])
    w.unmount()
  })
})
