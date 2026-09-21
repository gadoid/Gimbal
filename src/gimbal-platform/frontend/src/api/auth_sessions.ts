/** auth_sessions.ts — typed wrappers around /api/auths/* endpoints. */
import http from './http'

export interface AuthSession {
  id: number
  alias: string
  url: string
  username: string
  token_type: string
  expires_in: number
  created_at: string
  updated_at: string
  password_masked: string
  /** 反查双计数(配套方案 §1.2):N 别名 / N 场景(模板∪方案绑定,快照不计)。 */
  alias_ref_count?: number
  scenario_ref_count?: number
}

/** 反查面板(配套方案 §1.3):四类引用,读时实时扫。 */
export interface AliasRefItem {
  alias_name: string
  base_service: string
  group_tag: string | null
}

/** kinds ⊆ {template, scheme, snapshot}(snake 契约对齐后端 auth schema)。 */
export interface ScenarioRefItem {
  scenario_id: string
  name: string
  kinds: string[]
  /** 与 DELETE 409 同口径的拦截预告:本人场景的 template/scheme 才阻断。 */
  owner_id: number
}

export interface AuthReferences {
  alias_refs: AliasRefItem[]
  scenario_refs: { visible: ScenarioRefItem[]; hidden_count: number }
}

export interface AuthSessionCreateIn {
  alias: string
  url: string
  username: string
  password: string
  token_type?: string
  expires_in?: number
}

export interface AuthSessionPatchIn {
  url?: string
  username?: string
  password?: string
  token_type?: string
  expires_in?: number
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

/** 反查面板数据:谁在用这个凭证名(别名绑定 + 场景引用,可见性过滤在后端)。 */
export function getReferences(alias: string) {
  return http.get<AuthReferences>(
    `/auths/${encodeURIComponent(alias)}/references`).then((r) => r.data)
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