/**
 * api/project_credentials.ts —— authz M2a S8 项目凭证 client。
 *
 * 契约对齐后端 app/routers/project_credentials.py:
 * - 项目凭证 = 归属项目的槽位绑定;只有项目管理员(∨ Admin+)能写,
 *   成员只读且**无用户名**(username='',密码恒掩码;无明文出口);
 * - 公共项目 409 public_project_no_credentials(无成员,凭证无意义)。
 */
import http from './http'
import type { AuthSession, AuthSessionCreateIn, AuthSessionPatchIn, TestResult } from './auth_sessions'

export interface ProjectCredentialList {
  items: AuthSession[]
  /** 请求者能否维护(项目管理员 ∨ Admin+)—— 前端据此显隐写面 */
  canManage: boolean
}

function base(projectId: number): string {
  return `/projects/${projectId}/credentials`
}

export function listProjectCredentials(projectId: number): Promise<ProjectCredentialList> {
  return http.get<ProjectCredentialList>(base(projectId)).then((r) => r.data)
}

export function createProjectCredential(
  projectId: number, payload: AuthSessionCreateIn,
): Promise<AuthSession> {
  return http.post<AuthSession>(base(projectId), payload).then((r) => r.data)
}

export function patchProjectCredential(
  projectId: number, id: number, payload: AuthSessionPatchIn,
): Promise<AuthSession> {
  return http.patch<AuthSession>(`${base(projectId)}/${id}`, payload)
    .then((r) => r.data)
}

export function setProjectCredentialDefault(
  projectId: number, id: number,
): Promise<AuthSession> {
  return http.post<AuthSession>(`${base(projectId)}/${id}/default`)
    .then((r) => r.data)
}

export function removeProjectCredential(
  projectId: number, id: number,
): Promise<void> {
  return http.delete(`${base(projectId)}/${id}`).then(() => undefined)
}

export function testProjectCredential(
  projectId: number, id: number,
): Promise<TestResult> {
  return http.post<TestResult>(`${base(projectId)}/${id}/test`)
    .then((r) => r.data)
}
