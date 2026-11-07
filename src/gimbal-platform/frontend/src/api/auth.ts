/** auth.ts — typed wrappers around /api/auth/* endpoints. */
import http from './http'

export interface UserPublic {
  id: number
  username: string
  display_name: string
  /** 已废弃的派生位(后端保留仅为旧缓存兜底,W8 起前端不再消费) */
  is_admin: boolean
  /** 三级角色(authz W1 更名:user | admin | super_admin);仅作展示,
   *  权限判定一律走 MeOut.capabilities 的 can()(W8) */
  role?: 'user' | 'admin' | 'super_admin'
  /** 通知 roleVersion 比对源(ISO);旧快照缺省 */
  updated_at?: string | null
  is_active: boolean
  /** D32:系统用户(__platform__)标记;用户管理行防御停用/删除入口 */
  is_system?: boolean
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
  /** 表 A 求出的能力列表(authz W2;前端 can() 的唯一依据,W8) */
  capabilities?: string[]
  /** 管理员重置密码后的强制改密位(authz W6;路由守卫跳 /change-password) */
  must_change_password?: boolean
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
