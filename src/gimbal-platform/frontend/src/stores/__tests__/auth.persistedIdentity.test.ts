/**
 * auth store — 身份快照的持久化(刷新后第一帧就要有用户名)。
 *
 * 工作台布局 / 关注常驻席 / 执行缓存都按 username 分键,而这些键在组件
 * setup 阶段就要读;只有令牌在档、身份要等 /auth/me,首帧必然落到匿名键
 * 上,用户看到的就是"刷新后设置丢了"。身份随令牌一起入档解决它,
 * 但 status 仍须等 fetchMe 认证 —— 有身份 ≠ 令牌有效。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

const KEY = 'gimbal-auth'
const put = (v: unknown) => localStorage.setItem(KEY, JSON.stringify(v))
const get = () => JSON.parse(localStorage.getItem(KEY) ?? 'null')

describe('auth — 身份快照入档', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('存档带 user → 新 store 实例首帧即有身份(不必等 fetchMe)', () => {
    put({ accessToken: 'a', refreshToken: 'r', user: { id: 3, username: 'alice', display_name: 'Alice', is_admin: true, is_active: true, created_at: 'x' } })
    const auth = useAuthStore()
    expect(auth.currentUser?.username).toBe('alice')
    expect(auth.isAdmin).toBe(true)
    expect(auth.status).toBe('unknown')          // 有身份 ≠ 令牌已认证
  })

  it('身份与令牌变更后一并落盘(持久化走 watch,等一次 flush)', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'a'
    auth.refreshToken = 'r'
    auth.currentUser = { id: 1, username: 'bob', display_name: 'Bob', is_admin: false, is_active: true, created_at: 'x' } as never
    await nextTick()
    expect(get()).toMatchObject({ accessToken: 'a', user: { username: 'bob' } })
  })

  it('clear → 整档移除,不留上一个账号的身份', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'a'
    auth.refreshToken = 'r'
    auth.currentUser = { id: 1, username: 'bob', display_name: 'Bob', is_admin: false } as never
    await nextTick()
    expect(get()?.user?.username).toBe('bob')
    auth.clear()
    await nextTick()
    expect(localStorage.getItem(KEY)).toBeNull()
    expect(auth.currentUser).toBeNull()
  })

  it('旧版存档(只有令牌)/ 身份形状不对 → 回落为无身份,不炸', () => {
    put({ accessToken: 'a', refreshToken: 'r' })
    expect(useAuthStore().currentUser).toBeNull()

    localStorage.clear()
    put({ accessToken: 'a', refreshToken: 'r', user: { display_name: '缺用户名' } })
    const auth = useAuthStore()
    expect(auth.currentUser).toBeNull()
    expect(auth.accessToken).toBe('a')           // 令牌照常恢复
  })
})
