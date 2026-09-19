/**
 * useFollowLayout — 关注页常驻席契约:上限、播种、拖拽换位、按用户分键,
 * 以及 **prune 回收死席位**。
 *
 * 后端 starred 只有布尔位,常驻序是纯客户端偏好;两个必须守住的性质:
 * 1) 取消关注 / 删场景后残留 id 不得继续占用 PINNED_MAX 预算 —— 常驻区
 *    只渲染交集,否则用户撞上"上限 5 个"却看不到任何占位卡,没有逃生口;
 * 2) 存档按用户名分键,同机换账号不得串台。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useFollowLayout, PINNED_MAX } from '@/composables/useFollowLayout'
import { useAuthStore } from '@/stores/auth'

const as = (username: string) => {
  useAuthStore().currentUser = { id: 1, username, display_name: username, is_admin: false } as never
}
const keyOf = (username: string) => `gimbal.scenario-follows.pinned:${username}`

describe('useFollowLayout — 常驻席', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    as('alice')
  })

  it('pin 到上限拒收,unpin 腾位后可再 pin', () => {
    const l = useFollowLayout()
    l.pinned.value = []
    for (let i = 0; i < PINNED_MAX; i++) expect(l.pin(`s${i}`)).toBe(true)
    expect(l.pin('overflow')).toBe(false)
    l.unpin('s0')
    expect(l.pin('overflow')).toBe(true)
  })

  it('seed 只在无存档时生效(用户主动清空常驻不得被复活)', () => {
    const l = useFollowLayout()
    l.pinned.value = []
    l.seed(['a', 'b'])
    expect(l.pinned.value).toEqual(['a', 'b'])
    l.unpin('a')
    l.unpin('b')
    l.seed(['c', 'd'])
    expect(l.pinned.value).toEqual([])
  })

  it('prune 剪掉不再关注的残留 id 并释放预算(落盘)', () => {
    const l = useFollowLayout()
    // 5 席里 3 席是已取消关注的死 id
    l.pinned.value = ['gone-1', 'gone-2', 'gone-3', 'p-1', 'p-2']
    expect(l.pin('x')).toBe(false)                 // 死席位把它堵死了
    l.prune(['p-1', 'p-2', 'x'])
    expect(l.pinned.value).toEqual(['p-1', 'p-2'])
    expect(JSON.parse(localStorage.getItem(keyOf('alice'))!)).toEqual(['p-1', 'p-2'])
    expect(l.pin('x')).toBe(true)                  // 剪完就有空位
  })

  it('prune 无变化时不写盘(否则首访的空集会抢在 seed 前建 key)', () => {
    const l = useFollowLayout()
    l.pinned.value = []
    l.prune(['a', 'b'])
    expect(localStorage.getItem(keyOf('alice'))).toBeNull()
  })

  it('move 插到 target 之前;target=null 追加末尾', () => {
    const l = useFollowLayout()
    l.pinned.value = ['a', 'b', 'c']
    l.move('c', 'a')
    expect(l.pinned.value).toEqual(['c', 'a', 'b'])
    l.move('c', null)
    expect(l.pinned.value).toEqual(['a', 'b', 'c'])
  })

  it('存档按用户名分键,换账号不串台', () => {
    const alice = useFollowLayout()
    alice.pinned.value = []
    alice.seed(['a1', 'a2'])
    expect(localStorage.getItem(keyOf('alice'))).not.toBeNull()
    expect(localStorage.getItem(keyOf('bob'))).toBeNull()

    as('bob')
    const bob = useFollowLayout()
    expect(bob.pinned.value).toEqual([])           // 没继承 alice 的常驻序
    bob.pinned.value = ['b1']
    bob.move('b1', null)
    expect(JSON.parse(localStorage.getItem(keyOf('bob'))!)).toEqual(['b1'])
    expect(JSON.parse(localStorage.getItem(keyOf('alice'))!)).toEqual(['a1', 'a2'])
  })

  // 刷新后的第一帧 currentUser 还是 null(/auth/me 在 App.onMounted 里跑),
  // 这时任何一次读写都可能落到 `...pinned:` 这个匿名键上 —— 用户看到的
  // 就是「刷新后常驻席顺序丢了」。所以身份未知时必须一个键都不碰。
  it('身份未就位 → seed/pin 只改内存,不建匿名键', () => {
    useAuthStore().currentUser = null
    const l = useFollowLayout()
    l.pinned.value = []
    l.seed(['a', 'b'])
    l.pin('c')
    expect(l.pinned.value).toEqual(['c'])          // 本次会话内仍然可用
    expect(localStorage.length).toBe(0)            // 但没往 localStorage 写任何东西
  })

  it('身份晚于首帧到位 → whenReady 后读回该用户存档,seed 落对键', async () => {
    localStorage.setItem(keyOf('carol'), JSON.stringify(['x', 'y']))
    useAuthStore().currentUser = null
    const l = useFollowLayout()
    const ready = l.whenReady()

    as('carol')                                    // 模拟 fetchMe 回来
    await nextTick()
    await expect(ready).resolves.toBe('carol')
    expect(l.pinned.value).toEqual(['x', 'y'])     // 读回的是 carol 的存档
    l.seed(['n1', 'n2'])                           // 已有存档 → 播种不覆盖
    expect(l.pinned.value).toEqual(['x', 'y'])
    expect(localStorage.getItem(keyOf('carol'))).toBe(JSON.stringify(['x', 'y']))
  })
})
