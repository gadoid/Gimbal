/** users.ts — typed wrappers around /api/users/* endpoints. */
import http from './http'
import type { UserPublic } from './auth'

export type UserOut = UserPublic

export interface UserCreateIn {
  username: string
  password: string
  display_name?: string
  is_admin?: boolean
}

export interface UserPatchIn {
  display_name?: string
  is_admin?: boolean
  is_active?: boolean
  new_password?: string
}

export interface ResetPasswordOut {
  user_id: number
  username: string
  new_password: string
}

export function list() {
  return http.get<UserOut[]>('/users').then((r) => r.data)
}

export function create(payload: UserCreateIn) {
  return http.post<UserOut>('/users', payload).then((r) => r.data)
}

export function patch(userId: number, payload: UserPatchIn) {
  return http.patch<UserOut>(`/users/${userId}`, payload).then((r) => r.data)
}

export function resetPassword(userId: number) {
  return http
    .post<ResetPasswordOut>(`/users/${userId}/reset-password`)
    .then((r) => r.data)
}

export function remove(userId: number) {
  return http.delete(`/users/${userId}`).then((r) => r.data)
}
