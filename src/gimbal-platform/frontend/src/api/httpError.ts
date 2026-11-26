/**
 * httpError.ts — 错误形状单源(与 axios 实例零耦合)。
 *
 * 评审五轮 P2-7:``ApiError`` / ``httpStatusOf`` 自 http.ts 上提到本
 * 模块 —— 本文件不 import 任何东西(http.ts 顶部挂 axios/@/stores/auth/
 * @/router 整条链),单测可以**直接消费真实错误模块**(此前只能以
 * vi.hoisted 同形类模拟,测试与实现的同构性靠人保)。http.ts 转发导出,
 * 既有 ``from '@/api/http'`` 调用点不受影响。
 */

interface ApiErrorPayload {
  code?: number
  msg?: string
  detail?: { code?: number | string; msg?: string; message?: string } | string
}

export class ApiError extends Error {
  /** 归一错误码:数值(平台信封/HTTP 码)或字符串 detail.code
   *  (query-views 域错误码如 sut_auth_expired,2026-09-07 spec §7.5)。 */
  code: number | string
  status: number
  /** 结构化 detail 的原样引用(如 copy 409 的 {code, suggestion});
   *  字符串/数组/缺省 detail 时为 undefined。 */
  detail?: Record<string, unknown>

  constructor(
    status: number, code: number | string, msg: string,
    detail?: Record<string, unknown>,
  ) {
    super(msg)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }

  /** B5 切片 1:字符串错误码 typed 判等 —— ``code`` 参数收
   *  ``ApiErrorCode``(契约生成 union),拼写错编译期暴露;
   *  数值商务码/未登记串照常返回 false(运行时事实优先)。 */
  hasCode(code: import('./generated/errorCodes').ApiErrorCode): boolean {
    return this.code === code
  }
}

export function httpStatusOf(e: unknown): number | undefined {
  if (e instanceof ApiError) return e.status
  const anyErr = e as { status?: number; response?: { status?: number } } | null
  return anyErr?.status ?? anyErr?.response?.status
}

export type { ApiErrorPayload }
