/**
 * toast.ts — 单元测试(fake timers 驱动自动消退)。
 * 渲染端 ToastHost 不在此测:组件仅消费 toastState,行为真源在模块。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { toast, toastState, dismissToast } from '@/utils/toast'

describe('toast', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    toastState.items.splice(0)
    vi.useRealTimers()
  })

  it('四种 kind 入栈(新消息置顶),duration 到点自动消退(默认 3000)', () => {
    toast.success('ok')
    toast.error('bad')
    toast.info('hint')
    toast.warning('care')
    // unshift:最新在顶
    expect(toastState.items.map((i) => i.kind)).toEqual(['warning', 'info', 'error', 'success'])

    vi.advanceTimersByTime(2999)
    expect(toastState.items).toHaveLength(4)
    vi.advanceTimersByTime(1)
    expect(toastState.items).toHaveLength(0)
  })

  it('对象形式 { message, duration }(CaseComposer 长提示迁移)', () => {
    toast.success({ message: '已加入断言管理', duration: 4000 })
    expect(toastState.items[0]).toMatchObject({ kind: 'success', message: '已加入断言管理' })

    vi.advanceTimersByTime(3000)
    expect(toastState.items).toHaveLength(1)
    vi.advanceTimersByTime(1000)
    expect(toastState.items).toHaveLength(0)
  })

  it('dismiss 可提前移除且清定时器(不重复触发)', () => {
    const id = toast.info('stay')
    expect(toastState.items).toHaveLength(1)
    dismissToast(id)
    expect(toastState.items).toHaveLength(0)
    expect(() => vi.advanceTimersByTime(5000)).not.toThrow()
  })

  it('新消息置顶(与 ElMessage 堆叠方向一致)', () => {
    toast.success('a')
    toast.error('b')
    expect(toastState.items.map((i) => i.message)).toEqual(['b', 'a'])
  })

  it('duration:0 = 常驻不自动关(对齐 ElMessage)', () => {
    toast.warning({ message: 'sticky', duration: 0 })
    vi.advanceTimersByTime(60_000)
    expect(toastState.items).toHaveLength(1)
    dismissToast(toastState.items[0].id)
    expect(toastState.items).toHaveLength(0)
  })
})
