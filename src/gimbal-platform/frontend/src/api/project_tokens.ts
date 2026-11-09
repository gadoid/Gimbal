/**
 * api/project_tokens.ts —— authz M2b Q2 项目令牌 client。
 *
 * 契约对齐后端 app/routers/project_tokens.py(前缀 /projects/{pid}/tokens):
 * - 项目令牌 = 以「项目用户」权限访问单个项目的外部调用身份,执行恒用
 *   项目凭证;负责人(holder)= 指定的一位项目管理员;
 * - 门 = 项目管理员 ∨ Admin+(公共项目 409);
 * - 换绑:目标 = 本人立即生效,否则待目标确认(accept / decline 仅目标本人)。
 * 明文与回调签名密钥只在签发 / 重新生成 / 轮换响应里出现一次。
 */
import http from './http'
import type {
  AccessTokenDetail, AccessTokenListItem, ScopePayload, TokenCreatedOut,
  UnsatisfiedTask,
} from './access-tokens'

export interface ProjectTokenHolder {
  projectId: number
  holderId: number | null
  holderName: string | null
  holderPendingId: number | null
  holderPendingName: string | null
  /** 负责人是否合格(存在 / 启用 / 仍是项目管理员);不合格 = 令牌 401 */
  holderValid: boolean
  holderProblem: string | null
}

export type ProjectTokenItem = Omit<AccessTokenListItem, 'kind'> & {
  kind: 'project'
} & ProjectTokenHolder

export type ProjectTokenDetail = Omit<AccessTokenDetail, 'kind'> & {
  kind: 'project'
} & ProjectTokenHolder

export interface ProjectTokenList {
  items: ProjectTokenItem[]
  quota: { used: number; limit: number }
}

export interface ProjectScopeCandidates {
  aliases: string[]
  auths: { id: number; alias: string; slot: string }[]
}

function base(pid: number): string {
  return `/projects/${pid}/tokens`
}

export function listProjectTokens(pid: number): Promise<ProjectTokenList> {
  return http.get<ProjectTokenList>(base(pid)).then((r) => r.data)
}

export function getProjectScopeCandidates(pid: number): Promise<ProjectScopeCandidates> {
  return http.get<ProjectScopeCandidates>(`${base(pid)}/scope-candidates`)
    .then((r) => r.data)
}

export function createProjectToken(pid: number, body: {
  name: string
  ttlDays?: number
  callbackUrl?: string | null
  scope: ScopePayload
  holderId?: number | null
}): Promise<TokenCreatedOut> {
  return http.post<TokenCreatedOut>(base(pid), body).then((r) => r.data)
}

export function getProjectToken(pid: number, id: number): Promise<ProjectTokenDetail> {
  return http.get<ProjectTokenDetail>(`${base(pid)}/${id}`).then((r) => r.data)
}

export function renewProjectToken(pid: number, id: number, ttlDays: number) {
  return http.post<{ id: number; expiresAt: string | null }>(
    `${base(pid)}/${id}/renew`, { ttlDays }).then((r) => r.data)
}

export function regenerateProjectToken(pid: number, id: number): Promise<TokenCreatedOut> {
  return http.post<TokenCreatedOut>(`${base(pid)}/${id}/regenerate`)
    .then((r) => r.data)
}

export function putProjectTokenScope(
  pid: number, id: number, scope: ScopePayload, dryRun = false,
): Promise<{ unsatisfied: UnsatisfiedTask[] }> {
  return http.put<{ unsatisfied: UnsatisfiedTask[] }>(
    `${base(pid)}/${id}/scope`, scope, { params: dryRun ? { dryRun: true } : {} })
    .then((r) => r.data)
}

export function revokeProjectToken(pid: number, id: number) {
  return http.delete<{ id: number; revoked: boolean; pendingTasks: { id: number; name: string }[] }>(
    `${base(pid)}/${id}`).then((r) => r.data)
}

export interface HolderOut {
  id: number
  holderId: number | null
  holderPendingId: number | null
  pending?: boolean
}

export function rebindProjectTokenHolder(pid: number, id: number, userId: number): Promise<HolderOut> {
  return http.put<HolderOut>(`${base(pid)}/${id}/holder`, { userId })
    .then((r) => r.data)
}

export function acceptProjectTokenHolder(pid: number, id: number): Promise<HolderOut> {
  return http.post<HolderOut>(`${base(pid)}/${id}/holder/accept`).then((r) => r.data)
}

export function declineProjectTokenHolder(pid: number, id: number): Promise<HolderOut> {
  return http.post<HolderOut>(`${base(pid)}/${id}/holder/decline`).then((r) => r.data)
}
