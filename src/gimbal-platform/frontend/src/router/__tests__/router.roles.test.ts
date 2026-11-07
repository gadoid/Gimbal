/**
 * router — 能力矩阵路由守卫(authz W8;原 P2-4 角色矩阵的换代)。
 * 钉住:未登录 → /login 带回跳;无能力者访问 requiresCap 页 → 弹回
 * /home;持能力者放行;全员页(/profile 等)不受限;super_admin(表 A
 * 全能力)全通。能力来自 /auth/me.capabilities(store.can 查它,
 * 角色字面量已清零)。
 * 另钉 authz W6 只能改密门:must_change_password → 一切页面重定向
 * /change-password(带 redirect),改密位复位后放行。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

/** 与后端表 A(tests/authz_expected.yaml)对齐的期望矩阵(人工审定)。 */
const CAPS_BY_ROLE: Record<string, string[]> = {
  user: [],
  admin: ['ops.write', 'alias.write'],
  super_admin: ['users.manage', 'ops.write', 'alias.write'],
}

function loginAs(role: keyof typeof CAPS_BY_ROLE = 'user', signedIn = true) {
  const auth = useAuthStore()
  auth.accessToken = signedIn ? 'tok' : ''
  auth.currentUser = {
    id: 1, username: 'u', display_name: 'u', role, is_active: true,
  } as never
  auth.capabilities = CAPS_BY_ROLE[role]
}

async function nav(path: string) {
  return router.push(path).then(() => router.currentRoute.value.fullPath)
}

describe('router — 能力矩阵守卫(authz W8)', () => {
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

  it('user(无能力)访问 users.manage / ops.write 页 → 均弹回 /home', async () => {
    loginAs('user')
    expect(await nav('/admin/users')).toBe('/home')
    expect(await nav('/service-admin')).toBe('/home')
  })

  it('admin(ops.write)访问 ops 页放行、users.manage 页弹回', async () => {
    loginAs('admin')
    expect(await nav('/admin/users')).toBe('/home')
    // 服务信息管理 = ops.write(原 member+ 更名面)
    expect(await nav('/service-admin')).toBe('/service-admin')
  })

  it('ops.write 持有者可达别名详情页;无能力者弹回(后端按 admin ∨ 属主' +
     '放行入站管理;路由守卫与后端表 A 对拍)', async () => {
    loginAs('admin')
    expect(await nav('/service-admin/agent-sys')).toBe('/service-admin/agent-sys'
    )
    loginAs('user')
    // 换一个路由参数,避免同路径重复导航被 vue-router 短路、守卫不再执行
    expect(await nav('/service-admin/other-sys')).toBe('/home')
  })

  it('super_admin(表 A 全能力)全通 + /profile 全员可达', async () => {
    loginAs('super_admin')
    expect(await nav('/admin/users')).toBe('/admin/users')
    loginAs('user')
    // 子页面化:/profile 空子路径重定向到账号子页 —— 可达性断言落到重定向目标
    expect(await nav('/profile')).toBe('/profile/account')
    expect(await nav('/profile#notify')).toBe('/profile/account#notify')
  })
})

describe('router — authz W6 只能改密门', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    router.push('/').catch(() => undefined)
  })

  it('must_change_password 为真 → 一切页面重定向 /change-password(带回跳)', async () => {
    loginAs('user')
    const auth = useAuthStore()
    auth.mustChangePassword = true
    await nav('/scenarios/mine')
    expect(router.currentRoute.value.path).toBe('/change-password')
    expect(router.currentRoute.value.query.redirect).toBe('/scenarios/mine')
    // 改密页本身放行(唯一出口;不再追加 redirect 嵌套)
    await nav('/change-password')
    expect(router.currentRoute.value.path).toBe('/change-password')
  })

  it('改密位复位(fetchMe 成功路径)→ 原目标放行', async () => {
    loginAs('user')
    const auth = useAuthStore()
    auth.mustChangePassword = true
    await nav('/scenarios/mine')
    auth.mustChangePassword = false
    expect(await nav('/scenarios/mine')).toBe('/scenarios/mine')
  })
})

describe('auth store — can() 矩阵与旧快照迁移(authz W8)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('can() 按 capabilities 判定,与角色字段无关', () => {
    const auth = useAuthStore()
    auth.currentUser = { id: 1, username: 'm', role: 'user' } as never
    auth.capabilities = ['ops.write']
    expect(auth.can('ops.write')).toBe(true)
    expect(auth.can('users.manage')).toBe(false)
    // 能力列表为空 = 全不可(角色字段不参与判定)
    auth.capabilities = []
    expect(auth.can('ops.write')).toBe(false)
  })

  it('旧快照(W8 前)无 capabilities → can() 恒 false;role 兜底显示 user', () => {
    const auth = useAuthStore()
    // 旧快照形态:role 可能还是更名前的 'member'/'operator',且带已停发的
    // is_admin 派生位 —— 二者都不得授予任何能力
    auth.currentUser = { id: 2, username: 'old', role: 'member', is_admin: true } as never
    expect(auth.can('users.manage')).toBe(false)
    expect(auth.can('ops.write')).toBe(false)
    expect(auth.role).toBe('user')
  })
})
