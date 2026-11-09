/**
 * 项目角色展示(authz M2b Q1):admin 项目管理员 / member 成员 /
 * user 项目用户(只读 + 执行)。列表 / 详情徽章与成员下拉共用。
 */
import type { ProjectRole } from '@/api/projects'

export const PROJECT_ROLE_LABEL: Record<ProjectRole, string> = {
  admin: '项目管理员', member: '成员', user: '项目用户',
}

export function projectRoleLabel(role: string | null | undefined): string {
  if (!role) return ''
  return PROJECT_ROLE_LABEL[role as ProjectRole] ?? role
}
