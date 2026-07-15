/** auth.ts — typed wrappers around /api/auth/* endpoints. */
import http from './http'

export interface UserPublic {
  id: number
  username: string
  display_name: string
  is_admin: boolean
  is_active: boolean
  created_at: string
}

export interface TokenOut {
  access_token: string
  refresh_token: string
  token_type: string
  user: UserPublic
}

export interface MeOut {
  user: UserPublic
}

export function register(payload: {
  username: string
  password: string
  display_name?: string
}) {
  return http.post<TokenOut>('/auth/register', payload).then((r) => r.data)
}

export function login(payload: { username: string; password: string }) {
  return http.post<TokenOut>('/auth/login', payload).then((r) => r.data)
}

export function refresh(payload: { refresh_token: string }) {
  return http.post<TokenOut>('/auth/refresh', payload).then((r) => r.data)
}

export function me() {
  return http.get<MeOut>('/auth/me').then((r) => r.data)
}
