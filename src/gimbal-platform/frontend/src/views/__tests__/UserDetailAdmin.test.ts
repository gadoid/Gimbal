/** UserDetailAdmin — 用户管理 → 用户页(点行钻取)。
 * 契约:按路由 :id 取用户(GET /users/{id});标题 = 昵称∨用户名 +
 * 角色/状态 pill;概览 tab 默认(基础信息),访问令牌 tab 才挂
 * TokensSection(admin 定属主,按 owner 取数,惰性);用户不存在 →
 * 空态 + 返回入口。 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import UserDetailAdmin from '@/views/UserDetailAdmin.vue'
import * as usersApi from '@/api/users'
import * as tokenApi from '@/api/access-tokens'

vi.mock('@/api/users', () => ({
  get: vi.fn(),
}))
vi.mock('@/api/access-tokens', () => ({
  listAccessTokens: vi.fn(),
  getAccessToken: vi.fn(),
  getScopeCandidates: vi.fn(),
  createAccessToken: vi.fn(),
  putTokenScope: vi.fn(),
  renewAccessToken: vi.fn(),
  regenerateAccessToken: vi.fn(),
  putTokenCallback: vi.fn(),
  rotateCallbackSecret: vi.fn(),
  invalidateAccessToken: vi.fn(),
  revokeAccessToken: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const USER = {
  id: 2, username: 'alice', display_name: 'Alice Chen',
  role: 'user', is_active: true, created_at: '2026-02-01T00:00:00Z',
}

async function mountAt(path: string) {
  const router: Router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin/users', component: { template: '<div />' } },
      { path: '/admin/users/:id(\\d+)', component: UserDetailAdmin },
      { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
    ],
  })
  await router.push(path)
  const w = mount(UserDetailAdmin, {
    global: { plugins: [createPinia(), router] },
  })
  await flushPromises()
  return Object.assign(w, { router })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  vi.mocked(usersApi.get).mockResolvedValue(USER as never)
  vi.mocked(tokenApi.listAccessTokens).mockResolvedValue({
    items: [], quota: { used: 0, limit: 5 },
  } as never)
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('UserDetailAdmin — 用户页', () => {
  it('默认概览 tab:取用户、标题/面包屑/基础信息,令牌区不取数(惰性)', async () => {
    const w = await mountAt('/admin/users/2')
    expect(usersApi.get).toHaveBeenCalledWith(2)
    expect(w.find('[data-testid="udt-title"]').text()).toBe('Alice Chen')
    expect(w.text()).toContain('用户管理')
    expect(w.text()).toContain('alice')
    expect(w.find('[data-testid="udt-overview"]').text()).toContain('Alice Chen')
    expect(w.find('[data-testid="udt-overview"]').text()).toContain('2026-02-01')
    expect(tokenApi.listAccessTokens).not.toHaveBeenCalled()
    w.unmount()
  })

  it('切到访问令牌 tab → TokensSection 定属主取数(owner=2)', async () => {
    const w = await mountAt('/admin/users/2')
    // reka TabsTrigger 在 jsdom 打不开(PointerEvent 语义,同 Select)
    // —— 直改 tab 状态验证挂载与取数链路
    ;(w.vm as unknown as { tab: string }).tab = 'tokens'
    await flushPromises()
    expect(tokenApi.listAccessTokens).toHaveBeenCalledWith('personal', {
      all: true, owner: 2, status: undefined,
    })
    expect(w.text()).toContain('Alice Chen 的访问令牌')
    w.unmount()
  })

  it('display_name 缺省回落用户名;角色/状态 pill 在场', async () => {
    vi.mocked(usersApi.get).mockResolvedValue(
      { ...USER, display_name: '', role: 'admin', is_active: false } as never)
    const w = await mountAt('/admin/users/2')
    expect(w.find('[data-testid="udt-title"]').text()).toBe('alice')
    expect(w.text()).toContain('管理员')
    expect(w.text()).toContain('○ 停用')
    w.unmount()
  })

  it('用户不存在(404)→ 空态,不取令牌', async () => {
    vi.mocked(usersApi.get).mockRejectedValue(
      Object.assign(new Error('用户不存在'), { status: 404 }))
    const w = await mountAt('/admin/users/999')
    expect(w.text()).toContain('找不到该用户')
    expect(tokenApi.listAccessTokens).not.toHaveBeenCalled()
    expect(w.find('[data-testid="udt-back"]').exists()).toBe(true)
    w.unmount()
  })

  it('返回按钮 → /admin/users(列表 syncUrl 态由此恢复)', async () => {
    const w = await mountAt('/admin/users/2')
    await w.find('[data-testid="udt-back"]').trigger('click')
    await flushPromises()
    expect(w.router.currentRoute.value.path).toBe('/admin/users')
    w.unmount()
  })
})
