/**
 * api/services.ts — 服务主档注册簿 + 环境×系统实例(registry 重构 §2)。
 *
 * services = 系统概念的唯一登记处(注册簿制,非 plate 目录镜像):
 * name 服务名(场景服务键)、system 系统名(与 Plate 侧一致,账户维度)、
 * kind plate(目录受管)|external(第三方)|integration(plate 集成件)。
 * instances = (system, env) 的 login_url/版本线收口(唯一)。
 *
 * 读全员;写 admin(ops.write)。list 附对账:unregistered = plate 目录
 * 里还没拉入主档的服务名;plateReachable=false 时对账跳过。
 */
import http from '@/api/http'

export type ServiceKind = 'plate' | 'external' | 'integration'

export interface ServiceRow {
  name: string
  system: string
  kind: ServiceKind
  abbr: string
  description: string
  /** 对账状态:plate 行是否仍在 plate 目录(drifted=false 提示漂移) */
  inCatalog: boolean
  createdAt: string | null
  updatedAt: string | null
}

export interface ServiceList {
  services: ServiceRow[]
  /** plate 目录中未登记主档的服务名(一键登记候选) */
  unregistered: string[]
  plateReachable: boolean
}

export interface ServiceCreateIn {
  name: string
  system?: string
  kind?: ServiceKind
  abbr?: string
  description?: string
}

export interface ServicePatchIn {
  system?: string
  abbr?: string
  description?: string
}

export function listServices(params?: { q?: string }): Promise<ServiceList> {
  return http
    .get<ServiceList>('/services', { params })
    .then(({ data }) => data)
}

export function createService(payload: ServiceCreateIn): Promise<ServiceRow> {
  return http.post<ServiceRow>('/services', payload).then(({ data }) => data)
}

export function patchService(
  name: string, payload: ServicePatchIn,
): Promise<ServiceRow> {
  return http
    .patch<ServiceRow>(`/services/${encodeURIComponent(name)}`, payload)
    .then(({ data }) => data)
}

export function deleteService(name: string): Promise<void> {
  return http
    .delete(`/services/${encodeURIComponent(name)}`)
    .then(() => undefined)
}

// ── 批量导入目录(对账横幅「立即批量映射」)──────────────────────
export interface ImportCatalogResult {
  /** 本次新建的主档服务名 */
  created: string[]
  /** 未处理:已登记 或 不在目录 */
  skipped: string[]
  /** remaining:目录里仍没进主档的 */
  unregistered: string[]
  plateReachable: boolean
}

/** 批量登记 plate 目录服务:names 缺省 = 全部未登记(幂等)。 */
export function importCatalog(names: string[] = []): Promise<ImportCatalogResult> {
  return http
    .post<ImportCatalogResult>('/services/import-catalog', { names })
    .then(({ data }) => data)
}

// ── 环境×系统实例(login_url/版本线) ─────────────────────────────

export interface InstanceRow {
  system: string
  envId: number
  envName: string
  /** 标签组:同组行 = 一个实例的多枚标签(配置共享) */
  groupId: string
  tags: string[]
  loginUrl: string
  line: string
  note: string
  updatedAt: string | null
}

export interface InstancePutIn {
  loginUrl?: string
  line?: string
  note?: string
}

/** 实例列表(envId = 按标签切片;缺省 = 全部标签行)。 */
export function listInstances(envId?: number): Promise<InstanceRow[]> {
  return http.get<InstanceRow[]>('/services/instances', {
    params: envId != null ? { envId } : undefined,
  }).then(({ data }) => data)
}

/** upsert:不存在则建、存在则覆写给出的字段(loginUrl/line/note)。 */
export function putInstance(
  system: string, envId: number, payload: InstancePutIn,
): Promise<InstanceRow> {
  return http
    .put<InstanceRow>(
      `/services/instances/${encodeURIComponent(system)}/${envId}`, payload)
    .then(({ data }) => data)
}

/** 实例改标签(标签即环境):目标 = 既有 envId 或自由 envTag
 *  (不存在则后端自动登记为环境定义)。目标已有该系统实例 → 409。
 *  只搬登录口/版本线/说明;API 地址与身份条目按各自环境维护。 */
export function moveInstance(
  system: string, envId: number,
  target: { envId: number } | { envTag: string },
): Promise<InstanceRow> {
  const body = 'envId' in target
    ? { envId: target.envId }
    : { envTag: target.envTag }
  return http
    .patch<InstanceRow>(
      `/services/instances/${encodeURIComponent(system)}/${envId}`, body)
    .then(({ data }) => data)
}

/** 实例标签编辑(整组一次提交;至少一枚;不存在自动登记;冲突 409)。 */
export function putInstanceTags(
  system: string, envId: number, tags: string[],
): Promise<InstanceRow> {
  return http
    .put<InstanceRow>(
      `/services/instances/${encodeURIComponent(system)}/${envId}/tags`,
      { tags })
    .then(({ data }) => data)
}

/** 删除实例配置(只删登录口/版本线/说明;部署地址与条目不受影响)。 */
export function deleteInstance(
  system: string, envId: number,
): Promise<void> {
  return http
    .delete(`/services/instances/${encodeURIComponent(system)}/${envId}`)
    .then(() => undefined)
}

// ── 服务×环境实例组合视图(编排器数据源)────────────────────────
/** 实例下的调用身份条目(不含账户/密码)。 */
export interface ServiceInstanceIdentity {
  aliasName: string
  refMode: 'default' | 'username'
  refUsername: string
  display: string
}

/** 服务×环境实例 = deployment 地址 + 系统×环境登录口 + 身份条目。 */
export interface ServiceInstanceView {
  envId: number
  envName: string
  /** 同组标签行 = 一个实例的多枚环境 tag;空串 = 无系统实例行 */
  groupId: string
  tags: string[]
  baseUrl: string
  loginUrl: string
  line: string
  note: string
  identities: ServiceInstanceIdentity[]
}

/** 「凭证与调用身份」左栏视图:身份补上所属环境(服务级引用展开后
 *  每个身份都能落到具体 env,草稿/映射才有环境坐标)。 */
export interface ScopedServiceIdentityView extends ServiceInstanceIdentity {
  envId: number
  envName: string
}

/** 范围实例视图(编排器内部;一个实例 = 同 groupId 的若干环境 tag)。
 *  envId/envName = 主环境(首个 tag),新建凭证/身份时的默认坐标;
 *  envIds 为该实例在范围内实际选中的环境集合。 */
export interface ScopedServiceInstanceView {
  service: string
  system: string
  groupId: string
  envId: number | null
  envName: string
  tags: string[]
  envIds: number[]
  baseUrl: string
  loginUrl: string
  line: string
  identities: ScopedServiceIdentityView[]
}

export interface ServiceWithInstances {
  name: string
  system: string
  kind: ServiceKind
  instances: ServiceInstanceView[]
}

export interface ServiceInstanceOverview {
  services: ServiceWithInstances[]
}

/** 创建/编辑实例:envId / envTag 二选一;地址/登录口可选;
 *  identity 可选(同时登记一条调用身份,别名全局唯一)。 */
export interface ServiceInstancePutIn {
  envId?: number
  envTag?: string
  baseUrl?: string
  loginUrl?: string
  line?: string
  note?: string
  identity?: {
    aliasName: string
    refMode?: 'default' | 'username'
    refUsername?: string
    display?: string
  }
}

/** 全量服务×环境实例组合读模型(编排器「服务范围/凭证映射」)。 */
export function listServiceInstanceOverview(): Promise<ServiceInstanceOverview> {
  return http
    .get<ServiceInstanceOverview>('/services/instance-overview')
    .then(({ data }) => data)
}

/** 创建/编辑一个服务×环境实例(Admin;单事务写地址/登录口/身份)。 */
export function putServiceInstance(
  service: string, payload: ServiceInstancePutIn,
): Promise<ServiceInstanceView> {
  return http
    .put<ServiceInstanceView>(
      `/services/${encodeURIComponent(service)}/instances`, payload)
    .then(({ data }) => data)
}
