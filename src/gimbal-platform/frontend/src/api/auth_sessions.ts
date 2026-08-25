/** auth_sessions.ts — typed wrappers around /api/auths/* endpoints. */
import http from './http'

export interface AuthSession {
  id: number
  alias: string
  url: string
  username: string
  token_type: string
  expires_in: number
  created_at: string
  updated_at: string
  password_masked: string
}

export interface AuthSessionCreateIn {
  alias: string
  url: string
  username: string
  password: string
  token_type?: string
  expires_in?: number
}

export interface AuthSessionPatchIn {
  url?: string
  username?: string
  password?: string
  token_type?: string
  expires_in?: number
}

export interface TestResult {
  ok: boolean
  status_code: number | null
  message: string
}

export function list() {
  return http.get<AuthSession[]>('/auths').then((r) => r.data)
}

export function create(payload: AuthSessionCreateIn) {
  return http.post<AuthSession>('/auths', payload).then((r) => r.data)
}

export function patch(id: number, payload: AuthSessionPatchIn) {
  return http.patch<AuthSession>(`/auths/${id}`, payload).then((r) => r.data)
}

export function remove(id: number) {
  return http.delete(`/auths/${id}`).then(() => undefined)
}

export function testConnection(id: number) {
  return http.post<TestResult>(`/auths/${id}/test`).then((r) => r.data)
}

export interface AuthSessionSecrets extends AuthSession {
  password: string
}

/** 详情;includeSecrets=true 时后端附解密明文密码(内网测试环境策略,
 *  2026-08-25 认证改造设计 — 供场景配置页快照拷贝)。 */
export function get(
  id: number,
  includeSecrets = false,
): Promise<AuthSession | AuthSessionSecrets> {
  return http
    .get<AuthSession | AuthSessionSecrets>(`/auths/${id}`, {
      params: includeSecrets ? { include_secrets: true } : undefined,
    })
    .then((r) => r.data)
}