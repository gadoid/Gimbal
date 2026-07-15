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
  detail?: { code?: number; msg?: string } | string
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

function normalizeError(err: AxiosError): ApiError {
  const status = err.response?.status ?? 0
  const payload = extractErrorPayload(err)
  // FastAPI HTTPException(detail={code, msg}) surfaces as {detail: {code, msg}}
  const detail = payload.detail
  let code = 0
  let msg = err.message || 'Network error'
  if (detail && typeof detail === 'object') {
    code = typeof detail.code === 'number' ? detail.code : code
    msg = detail.msg ?? msg
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
let refreshInFlight: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  const auth = useAuthStore()
  if (!auth.refreshToken) return null
  refreshInFlight = (async () => {
    try {
      const resp = await axios.post('/api/auth/refresh', {
        refresh_token: auth.refreshToken,
      })
      const data = resp.data as {
        access_token: string
        refresh_token: string
      }
      auth.setTokens(data.access_token, data.refresh_token)
      return data.access_token
    } catch {
      return null
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

http.interceptors.response.use(
  (resp: AxiosResponse) => resp,
  async (err: AxiosError) => {
    const original = err.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined
    const status = err.response?.status

    if (status === 401 && original && !original._retry) {
      original._retry = true
      const fresh = await refreshAccessToken()
      if (fresh) {
        original.headers = original.headers ?? {}
        ;(original.headers as Record<string, string>).Authorization = `Bearer ${fresh}`
        return http.request(original)
      }
      // refresh failed — clear + redirect
      try {
        const auth = useAuthStore()
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
