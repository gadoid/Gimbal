/**
 * api/profile.ts — 个人设置(P2-1)的自服务面。
 *
 * 昵称走 PATCH /users/{self}(member 可自改 display_name);改密走
 * POST /auth/change-password(旧密码核验在后端)。
 */
import http from '@/api/http'

export function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  return http
    .post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
    .then(() => undefined)
}
