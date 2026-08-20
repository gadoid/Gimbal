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