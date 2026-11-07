/**
 * auth store — can() 矩阵(authz W8 新增,dev-plan 测试项)。
 *
 * 表 A 的前端镜像对拍:期望矩阵与后端 tests/authz_expected.yaml(人工
 * 审定快照)保持一致 —— 后端改表 A 而前端漏改时,这里是第一个红灯。
 * 前端判定本身不看角色(can 只查 capabilities),矩阵经 setMe(/auth/me
 * 的原样载荷)注入后逐角色断言。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

/** 与后端表 A(tests/authz_expected.yaml)人工对齐的期望矩阵 */
const EXPECTED: Record<string, string[]> = {
  user: [],
  admin: ['ops.write', 'alias.write', 'platform.alerts'],
  super_admin: ['users.manage', 'ops.write', 'alias.write', 'platform.alerts'],
}
const ALL_CAPS = ['users.manage', 'ops.write', 'alias.write', 'platform.alerts']

describe('auth — can() 三角色矩阵(对齐后端表 A)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  for (const [role, caps] of Object.entries(EXPECTED)) {
    it(`${role}: /auth/me 下发 ${JSON.stringify(caps)}`, () => {
      const auth = useAuthStore()
      auth.setMe({
        user: { id: 1, username: role, display_name: role, role, is_active: true } as never,
        capabilities: caps,
      })
      for (const cap of ALL_CAPS) {
        expect(auth.can(cap), `${role} × ${cap}`).toBe(caps.includes(cap))
      }
    })
  }

  it('setMe 全量落库:capabilities + must_change_password + 快照入档', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'a'; auth.refreshToken = 'r'
    auth.setMe({
      user: { id: 7, username: 'u7', display_name: 'u7', role: 'admin', is_active: true } as never,
      capabilities: ['ops.write'],
      must_change_password: true,
    })
    expect(auth.can('ops.write')).toBe(true)
    expect(auth.mustChangePassword).toBe(true)
    // R11:快照带上能力与强制位 —— 刷新首帧按快照渲染(watch 异步 flush)
    await nextTick()
    const snap = JSON.parse(localStorage.getItem('gimbal-auth') || '{}')
    expect(snap.capabilities).toEqual(['ops.write'])
    expect(snap.mustChangePassword).toBe(true)
  })

  it('旧快照(W8 前,无 capabilities 字段)→ 新 store 实例 can() 恒 false', () => {
    localStorage.setItem('gimbal-auth', JSON.stringify({
      accessToken: 'a', refreshToken: 'r',
      user: { id: 1, username: 'legacy', role: 'member' },
    }))
    const auth = useAuthStore()
    expect(auth.accessToken).toBe('a')          // 会话仍在
    expect(auth.capabilities).toEqual([])       // 能力不猜旧字段
    for (const cap of ALL_CAPS) expect(auth.can(cap)).toBe(false)
    expect(auth.role).toBe('user')              // 更名前角色值按 user 显示
  })

  it('clear() 一并清能力与强制位', () => {
    const auth = useAuthStore()
    auth.accessToken = 'a'; auth.refreshToken = 'r'
    auth.capabilities = ['ops.write']
    auth.mustChangePassword = true
    auth.clear()
    expect(auth.can('ops.write')).toBe(false)
    expect(auth.mustChangePassword).toBe(false)
  })
})
