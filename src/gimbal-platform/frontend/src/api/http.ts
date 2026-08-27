/**
 * http.ts — shared axios instance with auth + 401-refresh handling.
 *
 * - baseURL '/api' — the Vite dev proxy forwards to http://127.0.0.1:8000.
 * - Request interceptor pulls the access token from the Pinia auth store
 *   lazily (so module load order doesn't bite us).
 * - Response interceptor: on 401, attempt ONE refresh-token replay;
 *   on refresh failure, clear auth + redirect to /login.
 * - Surface FastAPI's {code, msg} error shape directly so the UI layer
 *   can format/translate without re-parsing.
 */
import axios, { AxiosError, AxiosRequestConfig, AxiosResponse } from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

interface ApiErrorPayload {
  code?: number
  msg?: string
  detail?: { code?: number; msg?: string; message?: string } | string
}

export class ApiError extends Error {
  code: number
  status: number

  constructor(status: number, code: number, msg: string) {
    super(msg)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

function extractErrorPayload(err: AxiosError): ApiErrorPayload {
  const data = err.response?.data
  if (data && typeof data === 'object') {
    return data as ApiErrorPayload
  }
  return {}
}

function summarizeValidationErrors(
  detail: unknown[],
): { code: number; msg: string } {
  // Pydantic v2: detail is an array of {type, loc, msg, input, ctx}.
  // Surface up to 3 field-level errors so the user can see what's wrong.
  const parts: string[] = []
  for (const item of detail) {
    if (!item || typeof item !== 'object') continue
    const loc = Array.isArray((item as { loc?: unknown }).loc)
      ? ((item as { loc: unknown[] }).loc as unknown[])
          .filter((p) => p !== 'body')
          .join('.')
      : ''
    const msg = (item as { msg?: string }).msg || ''
    parts.push(loc ? `${loc}: ${msg}` : msg)
    if (parts.length >= 3) break
  }
  return {
    code: 422,
    msg: parts.length ? parts.join('; ') : '请求参数校验失败',
  }
}

function normalizeError(err: AxiosError): ApiError {
  const status = err.response?.status ?? 0
  const payload = extractErrorPayload(err)
  // FastAPI HTTPException(detail={code, msg}) surfaces as {detail: {code, msg}}
  const detail = payload.detail
  let code = 0
  let msg = err.message || 'Network error'
  if (Array.isArray(detail)) {
    // Pydantic ValidationError → 422 {detail: [{loc, msg, type, ...}]}
    const v = summarizeValidationErrors(detail)
    code = v.code
    msg = v.msg
  } else if (detail && typeof detail === 'object') {
    code = typeof detail.code === 'number' ? detail.code : code
    // 平台错误信封字段是 {code, message};msg 兼容旧格式兜底。
    msg = detail.message ?? detail.msg ?? msg
  } else if (typeof detail === 'string') {
    msg = detail
  } else if (typeof payload.code === 'number') {
    code = payload.code
    msg = payload.msg ?? msg
  }
  return new ApiError(status, code, msg)
}

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// ── Request: inject Bearer token ────────────────────────────────
http.interceptors.request.use((config) => {
  try {
    const auth = useAuthStore()
    if (auth.accessToken) {
      config.headers = config.headers ?? {}
      ;(config.headers as Record<string, string>).Authorization =
        `Bearer ${auth.accessToken}`
    }
  } catch {
    // Pinia not installed yet — leave header absent.
  }
  return config
})

// ── Response: refresh-once on 401 ───────────────────────────────
//
// Refresh lives on the auth store (not a module-level singleton) so the
// lifecycle is owned by the same Pinia instance that owns the tokens.
// Concurrent 401s share one in-flight refresh via the store's
// ``refreshOnce()``; subsequent calls await the same promise.


http.interceptors.response.use(
  (resp: AxiosResponse) => resp,
  async (err: AxiosError) => {
    const original = err.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined
    const status = err.response?.status
    // The refresh call itself must never trigger another refresh: the
    // inner 401 would await refreshOnce() → which returns the very same
    // in-flight outer promise (its finally only runs after resolution)
    // → self-deadlock, the original request hangs forever and the user
    // is never logged out.
    const isRefreshCall =
      !!original && typeof original.url === 'string' && original.url.includes('/auth/refresh')

    if (status === 401 && original && !original._retry && !isRefreshCall) {
      original._retry = true
      const auth = useAuthStore()
      const fresh = await auth.refreshOnce()
      if (fresh) {
        original.headers = original.headers ?? {}
        ;(original.headers as Record<string, string>).Authorization = `Bearer ${fresh}`
        return http.request(original)
      }
      // refresh failed — clear + redirect.  Both are idempotent:
      // ``auth.clear()`` is a no-op on an already-cleared store; the
      // path check guards against duplicate ``router.replace`` calls.
      try {
        auth.clear()
      } catch {
        // ignore
      }
      const target = router.currentRoute.value.fullPath
      if (router.currentRoute.value.path !== '/login') {
        router.replace({ path: '/login', query: { redirect: target } })
      }
    }

    return Promise.reject(normalizeError(err))
  },
)


export default http
