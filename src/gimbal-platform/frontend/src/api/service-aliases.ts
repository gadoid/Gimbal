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
  groupTag: string | null
  credentialAlias: string | null
  ownerUserId: number | null
  createdAt: string | null
  updatedAt: string | null
}

export function listAliases(base?: string): Promise<ServiceAliasRow[]> {
  return http
    .get<ServiceAliasRow[]>('/service-aliases', {
      params: base ? { base } : undefined,
    })
    .then(({ data }) => data)
}

export function createAlias(input: {
  aliasName: string
  groupTag?: string | null
  credentialAlias?: string | null
}): Promise<ServiceAliasRow> {
  return http.post<ServiceAliasRow>('/service-aliases', input)
    .then(({ data }) => data)
}

export function patchAlias(
  aliasName: string,
  input: { groupTag?: string | null; credentialAlias?: string | null },
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
