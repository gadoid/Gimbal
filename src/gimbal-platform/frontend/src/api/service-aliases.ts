/**
 * api/service-aliases.ts — 服务别名注册表 API client(服务画像方案 §4.1 基础层)。
 *
 * 读全员 / 写 admin;注册校验强约束(裸声明不猜,plate 宕机期间不能
 * 登记 —— 后端 409)。credentialAlias 引用**执行者本人**的凭证池
 * (auth_sessions.alias,owner 隔离),不是全局凭证名。
 *
 * V5(B):groupTag 已退役,归属环境经 environmentId 外键指向
 * environments 表(展示名 environmentName 由列表接口 join 带出)。
 */
import http from '@/api/http'

export interface ServiceAliasRow {
  aliasName: string
  baseService: string
  /** F4 方案 B:环境级端点默认层(NULL = 不提供;唯一权威,改一处全局生效) */
  baseUrl: string | null
  /** V5(B):归属环境(id → environments;NULL = 未归属) */
  environmentId: number | null
  environmentName: string | null
  credentialAlias: string | null
  ownerUserId: number | null
  /** 三态接入(P1.0):plate 受管(目录派生强约束)| external 第三方
   * (无版本管理,别名即服务本体;不触发预览/不阻塞集成,单独统计) */
  kind: 'plate' | 'external'
  /** 入站与回调(webhook 设计 v3 P1):secret 只回「是否已设」,密文不外露 */
  inboundEnabled: boolean
  callbackEnabled: boolean
  callbackPath: string | null
  callbackSecretSet: boolean
  createdAt: string | null
  updatedAt: string | null
}

/** M4 Page 信封(§6.3)。 */
export interface AliasPage {
  items: ServiceAliasRow[]
  total: number
  page: number
  pageSize: number
}

export function listAliases(
  params?: { base?: string; q?: string; page?: number; page_size?: number },
): Promise<AliasPage> {
  return http
    .get<AliasPage>('/service-aliases', { params })
    .then(({ data }) => data)
}

/** 全量便利(画像页/工作台卡等小池消费方)。 */
export function listAllAliases(base?: string): Promise<ServiceAliasRow[]> {
  return listAliases({ base, page: 1, page_size: 200 }).then((p) => p.items)
}

export function createAlias(input: {
  aliasName: string
  /** 必填(2026-09-23):别名 = 环境端点登记,后端缺省 422 */
  baseUrl: string
  environmentId?: number | null
  credentialAlias?: string | null
  /** 三态接入(P1.0):缺省 plate(目录派生强约束);external 跳过
   * 目录校验(第三方服务,别名即服务本体) */
  kind?: 'plate' | 'external'
  /** b2.5:external 须显式 base_service(plate kind=integration 的服务) */
  baseService?: string | null
}): Promise<ServiceAliasRow> {
  return http.post<ServiceAliasRow>('/service-aliases', input)
    .then(({ data }) => data)
}

export function patchAlias(
  aliasName: string,
  input: { baseUrl?: string | null; environmentId?: number | null;
         credentialAlias?: string | null; baseService?: string | null;
         kind?: 'plate' | 'external' | null },
): Promise<ServiceAliasRow> {
  return http
    .patch<ServiceAliasRow>(`/service-aliases/${encodeURIComponent(aliasName)}`, input)
    .then(({ data }) => data)
}

export function deleteAlias(aliasName: string): Promise<void> {
  return http
    .delete(`/service-aliases/${encodeURIComponent(aliasName)}`)
    .then(() => undefined)
}

/** W11 三态分类读面:服务键集 → plate(受管)/external(第三方)/
 *  unknown(未登记,保存告警口径)。编排器徽标与保存告警的数据源。 */
export interface ServiceKinds {
  plate: string[]
  external: string[]
  unknown: string[]
}

export function classifyServices(services: string[]): Promise<ServiceKinds> {
  return http
    .get<ServiceKinds>('/service-aliases/classify', {
      params: services.map((s) => ['services', s]),
    })
    .then(({ data }) => data)
}

// ── 入站身份管理(webhook 设计 v3 P1 §4.5;仅 JWT)──────────────────

/** 入站凭证(gic_):明文令牌只在生成响应里出现一次,库中只存 sha256。 */
export interface InboundCredentialRow {
  id: number
  name: string
  createdAt: string | null
  lastUsedAt: string | null
  revokedAt: string | null
}

export interface InboundCredentialCreated extends InboundCredentialRow {
  token: string
}

export function createInboundCredential(
  aliasName: string, name = '',
): Promise<InboundCredentialCreated> {
  return http
    .post<InboundCredentialCreated>(
      `/service-aliases/${encodeURIComponent(aliasName)}/inbound-credentials`,
      { name })
    .then(({ data }) => data)
}

export function listInboundCredentials(
  aliasName: string,
): Promise<InboundCredentialRow[]> {
  return http
    .get<InboundCredentialRow[]>(
      `/service-aliases/${encodeURIComponent(aliasName)}/inbound-credentials`)
    .then(({ data }) => data)
}

export function revokeInboundCredential(
  aliasName: string, credId: number,
): Promise<void> {
  return http
    .delete(`/service-aliases/${encodeURIComponent(aliasName)}`
      + `/inbound-credentials/${credId}`)
    .then(() => undefined)
}

/** 入站与回调设置;rotateSecret 时响应携带新密钥明文(只此一次)。 */
export interface InboundSettings {
  aliasName: string
  kind: string
  inboundEnabled: boolean
  callbackEnabled: boolean
  callbackPath: string | null
  callbackSecretSet: boolean
  callbackSecret?: string | null
}

export function putInboundSettings(
  aliasName: string,
  input: { inboundEnabled?: boolean; callbackEnabled?: boolean;
           callbackPath?: string | null; rotateSecret?: boolean },
): Promise<InboundSettings> {
  return http
    .put<InboundSettings>(
      `/service-aliases/${encodeURIComponent(aliasName)}/inbound`, input)
    .then(({ data }) => data)
}

/** grant(ggt_):用户授权该别名代其执行(个人模式);明文只出现一次。 */
export interface GrantRow {
  id: number
  aliasName: string
  userId: number
  username: string | null
  expiresAt: string | null
  createdAt: string | null
  lastUsedAt: string | null
  revokedAt: string | null
}

export interface GrantCreated extends GrantRow {
  token: string
}

export function createGrant(
  aliasName: string, ttlDays?: number,
): Promise<GrantCreated> {
  return http
    .post<GrantCreated>(
      `/service-aliases/${encodeURIComponent(aliasName)}/grants`,
      ttlDays != null ? { ttlDays } : {})
    .then(({ data }) => data)
}

export function listGrants(aliasName: string): Promise<GrantRow[]> {
  return http
    .get<GrantRow[]>(
      `/service-aliases/${encodeURIComponent(aliasName)}/grants`)
    .then(({ data }) => data)
}

export function revokeGrant(
  aliasName: string, grantId: number,
): Promise<void> {
  return http
    .delete(`/service-aliases/${encodeURIComponent(aliasName)}`
      + `/grants/${grantId}`)
    .then(() => undefined)
}
