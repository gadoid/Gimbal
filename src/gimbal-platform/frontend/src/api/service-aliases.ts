/**
 * api/service-aliases.ts — 身份条目注册表 API client(registry 重构 §3)。
 *
 * 条目 = 环境下的服务调用身份:aliasName 引用键(规约延续
 * `<服务名>-<后缀>`,注入键 = 条目名)、baseService 服务锚、envId 必填、
 * ref 引用账户(refMode default=取 (system,env) 默认账户 | username=
 * 指定用户名)。地址归实例(services/instances),凭证归账户(/auths)。
 *
 * 读全员 / 写 admin;plate 走派生强约束(目录 ∪ 主档 plate),external
 * 显式 baseService(主档第三方服务)。q 检索覆盖 alias/base/slot。
 */
import http from '@/api/http'

export type AliasKind = 'plate' | 'external' | 'integration'

export interface ServiceAliasRow {
  aliasName: string
  baseService: string
  /** 注入键 = 条目名(恒等于 aliasName;null = 旧数据无条目名) */
  slot: string | null
  /** 接入三态(自主档派生):plate 受管 | external 第三方 | integration 集成件 */
  kind: AliasKind
  /** 条目归属环境(新架构必填;null = 旧数据兜底) */
  envId: number | null
  /** 账户引用:default=取 (system,env) 默认账户 | username=指定用户名 */
  refMode: 'default' | 'username'
  refUsername: string | null
  display: string
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
  /** 接入:缺省 plate(目录派生强约束);external 跳过目录校验 */
  kind?: 'plate' | 'external'
  /** external 须显式 baseService(主档第三方服务) */
  baseService?: string | null
  /** 重构新维度:环境(缺省 = 平台默认环境兜底) */
  envId?: number | null
  /** 账户引用:default | username(配 refUsername) */
  refMode?: 'default' | 'username'
  refUsername?: string
  display?: string
}): Promise<ServiceAliasRow> {
  return http.post<ServiceAliasRow>('/service-aliases', input)
    .then(({ data }) => data)
}

/** aliasName/baseService/envId 是条目实体键 —— 不可改;可改 ref 与展示名。 */
export function patchAlias(
  aliasName: string,
  input: { refMode?: 'default' | 'username';
           refUsername?: string | null;
           display?: string | null },
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
