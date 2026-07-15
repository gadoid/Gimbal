/**
 * errors.ts — Spec-2-11 unified error handling.
 *
 * Wraps `axios.isAxiosError` + non-2xx responses into a single shape:
 *   { status, code, message }
 *
 * Plus a helper `toUserMessage` that maps HTTP status → friendly toast text
 * (Chinese-first since UI is Chinese; falls back to API detail).
 */
import axios, { AxiosError } from 'axios'

export interface NormalizedError {
  status: number | null
  code: string | null
  message: string
}

export function normalizeError(e: unknown): NormalizedError {
  if (axios.isAxiosError(e)) {
    const ax = e as AxiosError<{ detail?: string | object; code?: number }>
    const status = ax.response?.status ?? null
    const data = ax.response?.data
    let code: string | null = null
    let message: string = ax.message
    if (data && typeof data === 'object') {
      if ('detail' in data) {
        const d = data.detail
        if (typeof d === 'string') {
          message = d
        } else if (d && typeof d === 'object' && 'msg' in d) {
          code = String((d as { code?: number }).code ?? '')
          message = String((d as { msg?: string }).msg ?? ax.message)
        }
      }
      if ('code' in data) code = String((data as { code?: number }).code ?? code ?? '')
    }
    return { status, code, message }
  }
  if (e instanceof Error) return { status: null, code: null, message: e.message }
  return { status: null, code: null, message: String(e) }
}

/** Map normalized error → user-friendly Chinese toast message. */
export function toUserMessage(e: unknown, fallback: string = '操作失败'): string {
  const ne = normalizeError(e)
  if (ne.status === null) {
    // Network error: server unreachable
    if (/network|timeout|aborted/i.test(ne.message)) {
      return '网络错误：无法连接后端'
    }
    return ne.message || fallback
  }
  if (ne.status >= 500) {
    return '服务器错误：' + (ne.message || '请稍后重试')
  }
  if (ne.status === 401) return '请先登录'
  if (ne.status === 403) return '没有权限：' + ne.message
  if (ne.status === 404) return '未找到：' + ne.message
  if (ne.status === 409) return '冲突：' + ne.message
  if (ne.status === 422) return '参数错误：' + ne.message
  return ne.message || fallback
}

/** Convenience: extract the most useful message for store.lastError. */
export function lastErrorMessage(e: unknown): string {
  return normalizeError(e).message
}