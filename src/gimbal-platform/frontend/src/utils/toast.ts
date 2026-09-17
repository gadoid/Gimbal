/**
 * toast.ts — 全站轻提示单一真源(重构方案 Phase 1 交叉切面)。
 *
 * 接口形状对齐 ElMessage 的四种常用调用,视图层逐批从 element-plus
 * 迁出时调用点零语义损失:
 *   toast.success('x')                 → toast.success('x')
 *   toast.success({ message, duration }) → toast.success({ message, duration })
 *
 * 渲染由 ToastHost(App.vue 挂载的页面级单例)承担;测试一律 mock 本
 * 模块(vi.mock('@/utils/toast')),不再 mock element-plus。
 */
import { reactive } from 'vue'

export type ToastKind = 'success' | 'error' | 'info' | 'warning'

export interface ToastItem {
  id: number
  kind: ToastKind
  message: string
}

/** 兼容 ElMessage 对象形式:{ message, duration? } */
export interface ToastInput {
  message: string
  duration?: number
}

const DEFAULT_DURATION = 3000

export const toastState = reactive({ items: [] as ToastItem[] })

let seq = 0
const timers = new Map<number, ReturnType<typeof setTimeout>>()

export function dismissToast(id: number): void {
  const timer = timers.get(id)
  if (timer) {
    clearTimeout(timer)
    timers.delete(id)
  }
  const index = toastState.items.findIndex((item) => item.id === id)
  if (index !== -1) toastState.items.splice(index, 1)
}

function push(kind: ToastKind, input: string | ToastInput): number {
  const message = typeof input === 'string' ? input : input.message
  const duration =
    (typeof input === 'object' && input.duration) || DEFAULT_DURATION
  const id = ++seq
  toastState.items.push({ id, kind, message })
  timers.set(id, setTimeout(() => dismissToast(id), duration))
  return id
}

export const toast = {
  success: (input: string | ToastInput) => push('success', input),
  error: (input: string | ToastInput) => push('error', input),
  info: (input: string | ToastInput) => push('info', input),
  warning: (input: string | ToastInput) => push('warning', input),
  dismiss: dismissToast,
}
