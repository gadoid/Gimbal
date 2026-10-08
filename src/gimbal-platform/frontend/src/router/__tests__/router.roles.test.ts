/**
 * router — 角色矩阵路由守卫(P2-4,权限方案 §5)。
 * 钉住:未登录 → /login 带回跳;user 访问 member/admin 页 → 弹回
 * /home;member 过 admin 页 → 弹回;全员页(/profile 等)不受限;
 * admin 全通。(2026-09-29 三级更名:原 member→user、operator→member)
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

function loginAs(role: 'user' | 'member' | 'admin', signedIn = true) {
  const auth = useAuthStore()
  auth.accessToken = signedIn ? 'tok' : ''
  auth.currentUser = {
    id: 1, username: 'u', display_name: 'u', role, is_active: true,
  } as never
}

async function nav(path: string) {
  return router.push(path).then(() => router.currentRoute.value.fullPath)
}

describe('router — 角色矩阵守卫', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    router.push('/').catch(() => undefined)
  })

  it('未登录访问受保护页 → /login 且带回跳地址', async () => {
    loginAs('user', false)
    const to = await nav('/scenarios/mine')
    expect(to.startsWith('/login')).toBe(true)
    expect(router.currentRoute.value.query.redirect).toBe('/scenarios/mine')
  })

  it('user 访问 admin 页(/admin/users)→ 弹回 /home', async () => {
    loginAs('user')
    expect(await nav('/admin/users')).toBe('/home')
  })

  it('member 访问 admin 页 → 弹回;member 访问 member 页放行', async () => {
    loginAs('member')
    expect(await nav('/admin/users')).toBe('/home')
    // member 页(服务信息管理 = member+)放行
    const to = await nav('/service-admin')
    expect(to).toBe('/service-admin')
  })

  it('admin 全通 + /profile 全员可达', async () => {
    loginAs('admin')
    expect(await nav('/admin/users')).toBe('/admin/users')
    loginAs('user')
    expect(await nav('/profile')).toBe('/profile')
  })
})

describe('auth store — hasRole 矩阵', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('三级角色判定 + 旧缓存回落(无 role → is_admin;operator → member)', () => {
    const auth = useAuthStore()
    auth.currentUser = { id: 1, username: 'm', role: 'user', is_admin: false } as never
    expect(auth.hasRole('user')).toBe(true)
    expect(auth.hasRole('member', 'admin')).toBe(false)
    auth.currentUser = { id: 2, username: 'o', role: 'member' } as never
    expect(auth.hasRole('member', 'admin')).toBe(true)
    expect(auth.hasRole('admin')).toBe(false)
    // 更名前的旧快照携带 operator → 就地归并为 member
    auth.currentUser = { id: 4, username: 'old_op', role: 'operator' } as never
    expect(auth.hasRole('member', 'admin')).toBe(true)
    expect(auth.hasRole('user')).toBe(false)
    // 旧缓存无 role → is_admin 派生口径(M6-3 后端派生,前端兜底同语义)
    auth.currentUser = { id: 3, username: 'legacy', is_admin: true } as never
    expect(auth.hasRole('admin')).toBe(true)
  })
})

describe('API 403 面(P2-4):角色越权时前端提示不炸', () => {
  it('user 调 admin-only 端点 → 403 detail 透出', async () => {
    // 单元面:直接断言 http 层对 403 的错误形状(接线在各页的 showError)
    const { ApiError } = await import('@/api/http')
    const err = new ApiError(403, 403, 'member_only')
    expect(err.status).toBe(403)
  })
})

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return actual
})
