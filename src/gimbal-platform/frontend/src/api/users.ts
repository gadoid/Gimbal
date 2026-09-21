/** users.ts — typed wrappers around /api/users/* endpoints. */
import http from './http'
import type { UserPublic } from './auth'

export type UserOut = UserPublic

export interface UserCreateIn {
  username: string
  password: string
  display_name?: string
  is_admin?: boolean
  role?: 'member' | 'operator' | 'admin'
}

export interface UserPatchIn {
  display_name?: string
  role?: 'member' | 'operator' | 'admin'
  is_active?: boolean
  new_password?: string
}

export interface ResetPasswordOut {
  user_id: number
  username: string
  new_password: string
}

/** M4 Page 信封(§6.3)。 */
export interface UsersPage {
  items: UserOut[]
  total: number
  page: number
  pageSize: number
}

export function list(params?: {
  q?: string
  role?: string
  page?: number
  page_size?: number
}) {
  return http.get<UsersPage>('/users', { params }).then((r) => r.data)
}

/** 全量便利(编排 users-card 等小池消费方)。 */
export function listAll() {
  return list({ page: 1, page_size: 200 }).then((p) => p.items)
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

/** 删除用户(P2-2 处置三选一;缺省 publicize)。 */
export function remove(
  userId: number,
  disposal?: { disposal: 'publicize' | 'transfer' | 'purge'; transfer_to?: number },
) {
  return http
    .delete(`/users/${userId}`, { data: disposal })
    .then((r) => r.data)
}
