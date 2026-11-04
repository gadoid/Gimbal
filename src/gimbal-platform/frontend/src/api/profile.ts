/**
 * api/profile.ts — 个人设置的自服务面。
 *
 * 昵称走 PATCH /users/{self}(member 可自改 display_name);改密走
 * POST /auth/change-password(webhook v4 §3.6:两个可选动作均默认勾选,
 * 返回新 JWT —— 调用方负责把新会话写回 auth store)。
 */
import http from '@/api/http'

export interface ChangePasswordOut {
  access_token: string
  refresh_token: string
}

export function changePassword(
  oldPassword: string, newPassword: string,
  opts?: { invalidateTokens?: boolean; logoutOthers?: boolean },
): Promise<ChangePasswordOut> {
  return http
    .post<ChangePasswordOut>('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
      invalidateTokens: opts?.invalidateTokens ?? true,
      logoutOthers: opts?.logoutOthers ?? true,
    })
    .then((r) => r.data)
}
