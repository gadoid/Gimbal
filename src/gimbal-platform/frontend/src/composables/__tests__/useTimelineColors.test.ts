/**
 * useTimelineColors — 时间线「事件类型 → 圆点颜色」映射的默认值与存档。
 *
 * 配色是个人偏好,不是业务数据,所以守两条:
 * 1) 按用户名分键,同机换账号不串台;身份未就位(刷新首帧)时一个键都不碰,
 *    否则会落到匿名键,带身份再读就是"我配的色没了";
 * 2) 存档里的非法值(手改 / 色板收缩)回落默认,不渲染出透明圆点。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

const KEY = (u: string) => `gimbal.workbench.timeline-colors:${u}`
const as = (username: string) => {
  useAuthStore().currentUser = { id: 1, username, display_name: username, is_admin: false } as never
}

/** 配色是 module 作用域单例:每条用例重取一份模块才互不污染。 */
async function fresh() {
  vi.resetModules()
  const mod = await import('@/composables/useTimelineColors')
  return mod
}

describe('useTimelineColors', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    as('alice')
  })

  it('默认三类各一色,互不重复', async () => {
    const { DEFAULT_TIMELINE_COLORS, DOT_PALETTE, useTimelineColors } = await fresh()
    const c = useTimelineColors()
    expect(new Set(Object.values(DEFAULT_TIMELINE_COLORS)).size).toBe(3)
    for (const kind of ['execution', 'scenario', 'adaptation'] as const) {
      expect(DOT_PALETTE).toContain(c.colorOf(kind) as never)
    }
  })

  it('setColor 即时生效并按用户名落盘', async () => {
    const { useTimelineColors } = await fresh()
    const c = useTimelineColors()
    c.setColor('execution', 'var(--avatar-7)')
    expect(c.colorOf('execution')).toBe('var(--avatar-7)')
    expect(JSON.parse(localStorage.getItem(KEY('alice'))!)).toMatchObject({
      execution: 'var(--avatar-7)',
    })
  })

  it('色板外的值拒收(不渲染透明点)', async () => {
    const { useTimelineColors, DEFAULT_TIMELINE_COLORS } = await fresh()
    const c = useTimelineColors()
    c.setColor('scenario', 'rebeccapurple')
    expect(c.colorOf('scenario')).toBe(DEFAULT_TIMELINE_COLORS.scenario)
    expect(localStorage.getItem(KEY('alice'))).toBeNull()
  })

  it('刷新后读回自己的配色;损坏/越界值回落默认', async () => {
    localStorage.setItem(KEY('alice'), JSON.stringify({ execution: 'var(--avatar-5)', adaptation: 'nope' }))
    const { useTimelineColors, DEFAULT_TIMELINE_COLORS } = await fresh()
    const c = useTimelineColors()
    expect(c.colorOf('execution')).toBe('var(--avatar-5)')
    expect(c.colorOf('adaptation')).toBe(DEFAULT_TIMELINE_COLORS.adaptation)   // 非法值 → 默认
  })

  it('换账号不串台', async () => {
    const alice = (await fresh()).useTimelineColors()
    alice.setColor('adaptation', 'var(--avatar-6)')

    as('bob')
    const bob = (await fresh()).useTimelineColors()
    const { DEFAULT_TIMELINE_COLORS } = await fresh()
    expect(bob.colorOf('adaptation')).toBe(DEFAULT_TIMELINE_COLORS.adaptation)
    expect(localStorage.getItem(KEY('bob'))).toBeNull()
    expect(JSON.parse(localStorage.getItem(KEY('alice'))!)).toMatchObject({ adaptation: 'var(--avatar-6)' })
  })

  it('身份未就位 → 不写匿名键;身份到位后 setColor 落对键', async () => {
    useAuthStore().currentUser = null
    const { useTimelineColors } = await fresh()
    const c = useTimelineColors()
    c.setColor('execution', 'var(--avatar-8)')
    expect(c.colorOf('execution')).toBe('var(--avatar-8)')   // 内存里已经改了
    expect(Object.keys(localStorage)).toHaveLength(0)        // 但一个键都没落

    as('alice')
    await nextTick()
    c.setColor('execution', 'var(--avatar-8)')
    expect(JSON.parse(localStorage.getItem(KEY('alice'))!)).toMatchObject({ execution: 'var(--avatar-8)' })
  })

  it('reset 回到默认并覆盖存档', async () => {
    localStorage.setItem(KEY('alice'), JSON.stringify({ execution: 'var(--avatar-1)' }))
    const { useTimelineColors, DEFAULT_TIMELINE_COLORS } = await fresh()
    const c = useTimelineColors()
    expect(c.colorOf('execution')).toBe('var(--avatar-1)')
    c.reset()
    expect(c.colorOf('execution')).toBe(DEFAULT_TIMELINE_COLORS.execution)
    expect(JSON.parse(localStorage.getItem(KEY('alice'))!)).toEqual(DEFAULT_TIMELINE_COLORS)
  })
})
