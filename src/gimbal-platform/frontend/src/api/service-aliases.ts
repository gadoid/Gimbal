/**
 * api/service-aliases.ts — 服务别名注册表 API client(服务画像方案 §4.1 基础层)。
 *
 * 读全员 / 写 admin;注册校验强约束(裸声明不猜,plate 宕机期间不能
 * 登记 —— 后端 409)。credentialAlias 引用**执行者本人**的凭证池
 * (auth_sessions.alias,owner 隔离),不是全局凭证名。
 */
import http from '@/api/http'

export interface ServiceAliasRow {
  aliasName: string
  baseService: string
  /** F4 方案 B:环境级端点默认层(NULL = 不提供;唯一权威,改一处全局生效) */
  baseUrl: string | null
  groupTag: string | null
  credentialAlias: string | null
  ownerUserId: number | null
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
  groupTag?: string | null
  credentialAlias?: string | null
}): Promise<ServiceAliasRow> {
  return http.post<ServiceAliasRow>('/service-aliases', input)
    .then(({ data }) => data)
}

export function patchAlias(
  aliasName: string,
  input: { baseUrl?: string | null; groupTag?: string | null; credentialAlias?: string | null },
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
