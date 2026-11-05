/**
 * Profile — 个人设置 · 子页面结构(原型 Main/Tokens/CardSettings)。
 * 钉住:账号页昵称自改走 PATCH /users/{self};改密走 /auth/change-password
 * 且旧密码错误有人话;通知偏好开关入面板;'' 重定向吞掉旧锚点深链
 * (#tokens → /profile/tokens,#card → /profile/card)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import Profile from '@/views/Profile.vue'
import ProfileAccount from '@/views/ProfileAccount.vue'
import { useAuthStore } from '@/stores/auth'
import * as profileApi from '@/api/profile'
import * as usersApi from '@/api/users'
import * as notificationsApi from '@/api/notifications'

vi.mock('@/api/profile', () => ({
  changePassword: vi.fn(),
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
// TokensSection 不能打真网络
vi.mock('@/api/access-tokens', () => ({
  listAccessTokens: vi.fn().mockResolvedValue(
    { items: [], quota: { used: 0, limit: 5 } }),
  getScopeCandidates: vi.fn().mockResolvedValue({ aliases: [], auths: [] }),
}))

function mountAccount() {
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  auth.currentUser = {
    id: 7, username: 'alice', display_name: 'Alice', role: 'user',
    is_active: true, is_admin: false,
  } as never
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:all(.*)', component: { template: '<div/>' } }],
  })
  return mount(ProfileAccount, { global: { plugins: [router] } })
}

describe('ProfileAccount — 账号与通知子页(原型 Main)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(notificationsApi.getPreferences).mockResolvedValue({ off: [] })
    vi.mocked(notificationsApi.putPreferences).mockResolvedValue({ off: [] })
  })

  it('昵称自改:PATCH /users/{self} 只带 display_name', async () => {
    vi.mocked(usersApi.patch).mockResolvedValue({
      id: 7, username: 'alice', display_name: 'Alice2', role: 'user',
      is_active: true, created_at: 'x',
    } as never)
    const w = mountAccount()
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
    const w = mountAccount()
    await flushPromises()
    await w.find('[data-testid="profile-old-pw"]').setValue('wrong-old')
    await w.find('[data-testid="profile-new-pw"]').setValue('NewPass-123')
    await w.find('[data-testid="profile-change-pw"]').trigger('submit')
    await flushPromises()
    expect(profileApi.changePassword).toHaveBeenCalledWith(
      'wrong-old', 'NewPass-123',
      { invalidateTokens: true, logoutOthers: true })
    expect(w.text()).toContain('旧密码不正确')
    w.unmount()
  })

  it('通知偏好:开关切换写回 putPreferences', async () => {
    const w = mountAccount()
    await flushPromises()
    expect(notificationsApi.getPreferences).toHaveBeenCalled()
    const sw = w.find('[data-testid="profile-pref-announcement"]')
    await sw.trigger('click')
    await flushPromises()
    expect(notificationsApi.putPreferences).toHaveBeenCalledWith(['announcement'])
    w.unmount()
  })
})

describe('Profile 布局与重定向(子页面化)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  function mkRouter(start: string) {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{
        path: '/profile',
        component: Profile,
        children: [
          {
            path: '',
            redirect: (to: { hash: string }) => ({
              path: to.hash === '#tokens' ? '/profile/tokens'
                : to.hash === '#card' ? '/profile/card'
                  : '/profile/account',
              hash: '',
            }),
          },
          { path: 'account', component: ProfileAccount },
          { path: 'tokens', component: { template: '<div data-testid="page-tokens"/>' } },
          { path: 'card', component: { template: '<div data-testid="page-card"/>' } },
        ],
      }],
    })
    router.push(start)
    return router.isReady().then(() => router)
  }

  it.each([
    ['/profile#tokens', '/profile/tokens'],
    ['/profile#card', '/profile/card'],
    ['/profile', '/profile/account'],
    ['/profile#notify', '/profile/account'],
  ])('旧深链 %s → %s', async (from, to) => {
    const router = await mkRouter(from)
    expect(router.currentRoute.value.fullPath).toBe(to)
  })

  it('布局:头 + 分区导航四项,按路由高亮', async () => {
    const router = await mkRouter('/profile/tokens')
    const auth = useAuthStore()
    auth.accessToken = 'tok'
    auth.currentUser = {
      id: 7, username: 'alice', display_name: 'Alice', role: 'member',
      is_active: true, is_admin: false,
    } as never
    const w = mount(Profile, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.text()).toContain('个人设置')
    expect(w.text()).toContain('alice · 成员')
    const nav = w.find('nav[aria-label="个人设置分区"]')
    expect(nav.text()).toContain('账号')
    expect(nav.text()).toContain('访问令牌')
    expect(nav.text()).toContain('工作台身份卡')
    expect(nav.text()).toContain('通知')
    // 当前 tokens 子页渲染(桩 RouterView 由 vue-router 注入真实子路由)
    expect(w.find('[data-testid="page-tokens"]').exists()).toBe(true)
    w.unmount()
  })
})
