/**
 * useFollowLayout — 关注页常驻席契约:上限、播种、拖拽换位,以及
 * **prune 回收死席位**。
 * 后端 starred 只有布尔位,常驻序是纯客户端偏好;取消关注 / 删除场景后
 * 残留 id 若不剪掉,会继续占用 PINNED_MAX 预算 —— 常驻区只渲染交集,
 * 用户于是撞上"上限 5 个"却看不到任何占位卡,且没有逃生入口。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useFollowLayout, PINNED_MAX } from '@/composables/useFollowLayout'

const LS_KEY = 'gimbal.scenario-follows.pinned'

describe('useFollowLayout — 常驻席', () => {
  beforeEach(() => { localStorage.clear() })

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
    expect(JSON.parse(localStorage.getItem(LS_KEY)!)).toEqual(['p-1', 'p-2'])
    expect(l.pin('x')).toBe(true)                  // 剪完就有空位
  })

  it('prune 无变化时不写盘(否则首访的空集会抢在 seed 前建 key)', () => {
    const l = useFollowLayout()
    l.pinned.value = []
    l.prune(['a', 'b'])
    expect(localStorage.getItem(LS_KEY)).toBeNull()
  })

  it('move 插到 target 之前;target=null 追加末尾', () => {
    const l = useFollowLayout()
    l.pinned.value = ['a', 'b', 'c']
    l.move('c', 'a')
    expect(l.pinned.value).toEqual(['c', 'a', 'b'])
    l.move('c', null)
    expect(l.pinned.value).toEqual(['a', 'b', 'c'])
  })
})
