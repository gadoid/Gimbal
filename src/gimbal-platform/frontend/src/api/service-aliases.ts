/**
 * api/service-aliases.ts — 服务别名注册表 API client(服务画像方案 §4.1 基础层)。
 *
 * 读全员 / 写 admin;注册校验强约束(裸声明不猜,plate 宕机期间不能
 * 登记 —— 后端 409)。
 *
 * authz M2a S6「别名瘦身」:baseUrl/environmentId/environmentName/
 * credentialAlias/ownerUserId 已退役 —— 地址归部署表(部署地址页),
 * 凭证归槽位(slot,执行时按执行者本人认证池的槽位取),个人别名退役
 * (全部团队共享)。AliasOut = {aliasName, baseService, slot, kind,
 * createdAt, updatedAt};q 检索覆盖 alias/base/slot。
 */
import http from '@/api/http'

export interface ServiceAliasRow {
  aliasName: string
  baseService: string
  /** M2a S6:声明槽位 —— 执行注入取哪个凭证槽(null = 未声明) */
  slot: string | null
  /** 三态接入(P1.0):plate 受管(目录派生强约束)| external 第三方
   *  (无版本管理,别名即服务本体;不触发预览/不阻塞集成,单独统计) */
  kind: 'plate' | 'external'
  /** 入站与回调(webhook 设计 v3 P1):secret 只回「是否已设」,密文不外露 */
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
  /** 三态接入(P1.0):缺省 plate(目录派生强约束);external 跳过
   *  目录校验(第三方服务,别名即服务本体) */
  kind?: 'plate' | 'external'
  /** M2a S6:声明槽位(缺省 = 别名同名槽) */
  slot?: string | null
  /** b2.5:external 须显式 base_service(plate kind=integration 的服务) */
  baseService?: string | null
}): Promise<ServiceAliasRow> {
  return http.post<ServiceAliasRow>('/service-aliases', input)
    .then(({ data }) => data)
}

export function patchAlias(
  aliasName: string,
  input: { slot?: string | null; baseService?: string | null;
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
