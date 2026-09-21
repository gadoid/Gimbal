/**
 * Profile — 个人设置页(P2-1)。
 * 钉住:昵称自改走 PATCH /users/{self};改密走 /auth/change-password
 * 且旧密码错误有人话;通知偏好开关入面板。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Profile from '@/views/Profile.vue'
import { useAuthStore } from '@/stores/auth'
import * as profileApi from '@/api/profile'
import * as usersApi from '@/api/users'
import * as notificationsApi from '@/api/notifications'

vi.mock('@/api/profile', () => ({ changePassword: vi.fn() }))
vi.mock('@/api/users', () => ({ patch: vi.fn() }))
vi.mock('@/api/notifications', () => ({
  getPreferences: vi.fn().mockResolvedValue({ off: [] }),
  putPreferences: vi.fn().mockResolvedValue({ off: [] }),
  NOTIFICATION_TYPE_LABELS: {
    execution_finished: '执行完成', announcement: '平台公告',
  },
}))

function mountPage() {
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  auth.currentUser = {
    id: 7, username: 'alice', display_name: 'Alice', role: 'member',
    is_active: true, is_admin: false,
  } as never
  return mount(Profile)
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
      id: 7, username: 'alice', display_name: 'Alice2', role: 'member',
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
    expect(profileApi.changePassword).toHaveBeenCalledWith('wrong-old', 'NewPass-123')
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
