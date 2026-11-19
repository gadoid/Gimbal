/**
 * auth_sessions.ts — typed wrappers around /api/auths/* endpoints.
 *
 * registry 重构(P1-8):凭证=账户实体(auth_accounts)。四元组
 * (owner|project, system, env, username) 唯一,密码一份 —— 改密一处、
 * 所有装载它的身份条目/场景同时生效。url/alias/slot 字段退役:
 * 登录地址在环境×系统实例(services/instances),装载在身份条目
 * (service-aliases,ref 引用账户)。username 不可改(实体键)。
 */
import http from './http'

export interface AuthSession {
  id: number
  /** 系统名(与 Plate 侧一致;账户的 system 维度,跨服务共享登录) */
  system: string
  /** 账户归属环境(必填;无环境的执行无从解析身份) */
  envId: number
  username: string
  token_type: string
  expires_in: number
  created_at: string
  updated_at: string
  password_masked: string
  isDefault?: boolean
  /** 账号级字段(${slot.X.field} 消费) */
  accountFields?: Record<string, unknown>
  /** 回显:实例登录口(环境×系统唯一;缺席='') */
  loginUrl?: string
  /** 反查双计数:N 身份条目 / N 场景(模板∪方案绑定,快照不计) */
  identityRefCount?: number
  scenarioRefCount?: number
}

/** 反查面板(配套方案 §1.3):引用面,读时实时扫。 */
export interface IdentityRefItem {
  aliasName: string
  baseService: string
  envId: number
  refMode: string
  refUsername: string | null
}

/** kinds ⊆ {template, snapshot}(snake 契约对齐后端 auth schema)。 */
export interface ScenarioRefItem {
  scenarioId: string
  name: string
  kinds: string[]
  /** 与 DELETE 409 同口径的拦截预告:本人场景的 template/scheme 才阻断。 */
  ownerId: number
}

export interface AuthReferences {
  identityRefs: IdentityRefItem[]
  scenarioRefs: { visible: ScenarioRefItem[]; hidden_count: number }
}

export interface AuthSessionCreateIn {
  system: string
  envId: number
  username: string
  password: string
  token_type?: string
  expires_in?: number
  accountFields?: Record<string, unknown>
  isDefault?: boolean
}

/** username/system/env 是账户实体键 —— 不可改;能改的只有密码与展示属性。 */
export interface AuthSessionPatchIn {
  password?: string
  token_type?: string
  expires_in?: number
  accountFields?: Record<string, unknown>
  isDefault?: boolean
}

export interface TestResult {
  ok: boolean
  status_code: number | null
  message: string
}

/** M4 Page 信封 + 全量类型计数(metaText 的服务端供给)。 */
export interface AuthsPage {
  items: AuthSession[]
  total: number
  page: number
  pageSize: number
  tokenTypeCounts: Record<string, number>
}

export function list(params?: {
  q?: string
  token_type?: string
  page?: number
  page_size?: number
}) {
  return http
    .get<AuthsPage>('/auths', { params })
    .then((r) => r.data)
}

/** 全量便利(小池消费方):单页 200 取回 items —— 凭证池量级远小于上限。 */
export function listAll() {
  return list({ page: 1, page_size: 200 }).then((p) => p.items)
}

export function create(payload: AuthSessionCreateIn) {
  return http.post<AuthSession>('/auths', payload).then((r) => r.data)
}

export function patch(id: number, payload: AuthSessionPatchIn) {
  return http.patch<AuthSession>(`/auths/${id}`, payload).then((r) => r.data)
}

export function remove(id: number) {
  return http.delete(`/auths/${id}`).then(() => undefined)
}

/** 置为该 system 的默认账户(0059 起默认按 (池, system) 唯一,
 * 同 system 旧默认原子清除 —— 跨环境共用同一个默认账户)。 */
export function setDefault(id: number) {
  return http.post<AuthSession>(`/auths/${id}/default`).then((r) => r.data)
}

/** 反查面板数据:谁在装载这个账户(身份条目 + 场景引用,可见性过滤在后端)。 */
export function getReferences(id: number) {
  return http.get<AuthReferences>(
    `/auths/${id}/references`).then((r) => r.data)
}

export function testConnection(id: number) {
  return http.post<TestResult>(`/auths/${id}/test`).then((r) => r.data)
}

export interface AuthSessionSecrets extends AuthSession {
  password: string
}

/** 详情;includeSecrets=true 时后端附解密明文密码(内网测试环境策略,
 *  2026-08-25 认证改造设计 — 供场景配置页快照拷贝)。 */
export function get(
  id: number,
  includeSecrets = false,
): Promise<AuthSession | AuthSessionSecrets> {
  return http
    .get<AuthSession | AuthSessionSecrets>(`/auths/${id}`, {
      params: includeSecrets ? { include_secrets: true } : undefined,
    })
    .then((r) => r.data)
}
