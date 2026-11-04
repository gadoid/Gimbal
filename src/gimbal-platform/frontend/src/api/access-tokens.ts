/**
 * access-tokens.ts — 访问令牌 API(webhook v4 §5.1)。
 *
 * 一组接口管个人与平台两类令牌;三处入口(个人设置、集成页平台令牌、
 * 用户管理页 admin 视图)复用同一组接口与组件。明文与回调签名密钥只
 * 在创建/重新生成/轮换响应里出现一次(D10)。
 */
import http from '@/api/http'

export type TokenKind = 'personal' | 'platform'
export type TokenStatus = 'active' | 'expired' | 'invalidated' | 'revoked'

export interface AccessTokenListItem {
  id: number
  kind: TokenKind
  name: string
  tokenHint: string
  status: TokenStatus
  invalidatedReason: string | null
  invalidationNote: string | null
  expiresAt: string | null
  invalidatedAt: string | null
  revokedAt: string | null
  lastUsedAt: string | null
  createdAt: string | null
  callbackUrl: string | null
  callbackSecretSet: boolean
  /** 派生提示:已设回调但密钥不可用(FERNET_KEY 轮换)→ 请轮换 */
  signingKeyUsable: boolean | null
  scopeCounts: { aliases: number; auths: number }
  taskCounts: { total: number; unsatisfied: number }
  /** admin `all=1` 视图附带 */
  ownerId?: number
  ownerName?: string
  /** 平台令牌列表附带:签发人(created_by;签发人已删/属主个人令牌不带) */
  issuerName?: string
}

export interface TokenListEnvelope {
  items: AccessTokenListItem[]
  quota: { used: number; limit: number }
}

export interface ScopeCandidate {
  alias: string
}

export interface AuthCandidate {
  id: number
  alias: string
}

export interface ScopeCandidates {
  aliases: string[]
  auths: AuthCandidate[]
}

export interface ScopePayload {
  aliases: string[]
  authIds: number[]
}

export interface TokenCreatedOut {
  id: number
  /** 一次性明文(gtk_…);关闭对话框后无法再查看 */
  token: string
  callbackSecret?: string | null
  expiresAt?: string | null
}

export interface TokenScopeMissingItem {
  kind: 'alias' | 'auth'
  name: string
  deleted: boolean
}

export interface TokenTaskPrecheck {
  id: number
  name: string
  cronText: string
  triggerCron: string
  satisfied: boolean
  missing: TokenScopeMissingItem[]
  hint: string
}

export interface TokenRecentCall {
  id: number
  action: string
  at: string | null
  denied: boolean
  reason?: string | null
  scenarioName?: string | null
  fn?: string | null
  executionId?: number | null
  clientRef?: string | null
  status?: string
  outOfScope?: boolean
}

export interface AccessTokenDetail extends AccessTokenListItem {
  scope: { aliases: string[]; auths: AuthCandidate[] }
  tasks: TokenTaskPrecheck[]
  recentCalls: TokenRecentCall[]
}

export interface UnsatisfiedTask {
  id: number
  name: string
  missing: TokenScopeMissingItem[]
}

export function listAccessTokens(
  kind: TokenKind, opts?: { all?: boolean; owner?: number; status?: TokenStatus },
): Promise<TokenListEnvelope> {
  return http
    .get<TokenListEnvelope>('/access-tokens', {
      params: { kind, all: opts?.all || undefined,
                owner: opts?.owner, status: opts?.status },
    })
    .then((r) => r.data)
}

export function getScopeCandidates(kind: TokenKind): Promise<ScopeCandidates> {
  return http
    .get<ScopeCandidates>('/access-tokens/scope-candidates', {
      params: { kind },
    })
    .then((r) => r.data)
}

export function createAccessToken(body: {
  kind: TokenKind
  name: string
  ttlDays: number
  callbackUrl?: string | null
  scope: ScopePayload
}): Promise<TokenCreatedOut> {
  return http.post<TokenCreatedOut>('/access-tokens', body).then((r) => r.data)
}

export function getAccessToken(id: number): Promise<AccessTokenDetail> {
  return http.get<AccessTokenDetail>(`/access-tokens/${id}`).then((r) => r.data)
}

export function putTokenScope(
  id: number, scope: ScopePayload, dryRun = false,
): Promise<{ unsatisfied: UnsatisfiedTask[] }> {
  return http
    .put<{ unsatisfied: UnsatisfiedTask[] }>(`/access-tokens/${id}/scope`,
      scope, { params: dryRun ? { dryRun: 1 } : {} })
    .then((r) => r.data)
}

export function renewAccessToken(id: number, ttlDays: number): Promise<{ id: number; expiresAt: string | null }> {
  return http
    .post(`/access-tokens/${id}/renew`, { ttlDays })
    .then((r) => r.data)
}

export function regenerateAccessToken(id: number): Promise<TokenCreatedOut> {
  return http.post<TokenCreatedOut>(`/access-tokens/${id}/regenerate`)
    .then((r) => r.data)
}

export function putTokenCallback(
  id: number, url: string | null,
): Promise<{ id: number; callbackUrl: string | null; callbackSecret?: string | null }> {
  return http
    .put(`/access-tokens/${id}/callback`, { url })
    .then((r) => r.data)
}

export function rotateCallbackSecret(id: number): Promise<{ id: number; callbackSecret: string }> {
  return http
    .post(`/access-tokens/${id}/callback-secret/rotate`)
    .then((r) => r.data)
}

export function invalidateAccessToken(
  id: number, note?: string,
): Promise<{ id: number; status: TokenStatus }> {
  return http
    .post(`/access-tokens/${id}/invalidate`, { note: note ?? null })
    .then((r) => r.data)
}

export function revokeAccessToken(id: number): Promise<{
  id: number; revoked: boolean
  pendingTasks: { id: number; name: string }[]
}> {
  return http.delete(`/access-tokens/${id}`).then((r) => r.data)
}
