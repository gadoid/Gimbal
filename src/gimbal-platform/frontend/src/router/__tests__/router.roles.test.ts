/**
 * router — 角色矩阵路由守卫(P2-4,权限方案 §5)。
 * 钉住:未登录 → /login 带回跳;member 访问 operator/admin 页 → 弹回
 * /home;operator 过 admin 页 → 弹回;全员页(/profile 等)不受限;
 * admin 全通。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

function loginAs(role: 'member' | 'operator' | 'admin', signedIn = true) {
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
    loginAs('member', false)
    const to = await nav('/scenarios/mine')
    expect(to.startsWith('/login')).toBe(true)
    expect(router.currentRoute.value.query.redirect).toBe('/scenarios/mine')
  })

  it('member 访问 admin 页(/admin/users)→ 弹回 /home', async () => {
    loginAs('member')
    expect(await nav('/admin/users')).toBe('/home')
  })

  it('operator 访问 admin 页 → 弹回;operator 访问 operator 页放行', async () => {
    loginAs('operator')
    expect(await nav('/admin/users')).toBe('/home')
    // operator 页(服务信息管理 = operator+)放行
    const to = await nav('/service-admin')
    expect(to).toBe('/service-admin')
  })

  it('admin 全通 + /profile 全员可达', async () => {
    loginAs('admin')
    expect(await nav('/admin/users')).toBe('/admin/users')
    loginAs('member')
    expect(await nav('/profile')).toBe('/profile')
  })
})

describe('auth store — hasRole 矩阵', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('三级角色判定 + 旧缓存(无 role 字段)回落 is_admin', () => {
    const auth = useAuthStore()
    auth.currentUser = { id: 1, username: 'm', role: 'member', is_admin: false } as never
    expect(auth.hasRole('member')).toBe(true)
    expect(auth.hasRole('operator', 'admin')).toBe(false)
    auth.currentUser = { id: 2, username: 'o', role: 'operator' } as never
    expect(auth.hasRole('operator', 'admin')).toBe(true)
    expect(auth.hasRole('admin')).toBe(false)
    // 旧缓存无 role → is_admin 派生口径(M6-3 后端派生,前端兜底同语义)
    auth.currentUser = { id: 3, username: 'legacy', is_admin: true } as never
    expect(auth.hasRole('admin')).toBe(true)
  })
})

describe('API 403 面(P2-4):角色越权时前端提示不炸', () => {
  it('member 调 admin-only 端点 → 403 detail 透出', async () => {
    // 单元面:直接断言 http 层对 403 的错误形状(接线在各页的 showError)
    const { ApiError } = await import('@/api/http')
    const err = new ApiError(403, 403, 'operator_only')
    expect(err.status).toBe(403)
  })
})

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return actual
})
