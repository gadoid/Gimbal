/**
 * api/carry.ts —— carry 值层 client(spec §3.2)。
 *
 * 契约对齐后端 app/routers/carry.py + app/schemas/carry.py:
 * - 值表两层:服务绑定(覆盖)→ 全局默认;dict 的 null 值 = 显式 null 行,
 *   键缺席 = 未配置(spec §3.1)。
 * - 读值表 CurrentUser(编排器提示,T14);写值表与 fields/drift 走
 *   AdminUser(配置页 T15 / 漂移面板 T16)。
 * - getDrift 返回完整 DriftReport:plate 不可达(plateReachable=False)时
 *   services 照常返回,但面视为空集 → 全部绑定误报为 orphaned —
 *   消费方必须先判 plateReachable 再渲染清单/放行批生成,
 *   防把不可达误读成漂移。
 *
 * http 是裸 axios 实例(响应拦截器透传 AxiosResponse),惯例同
 * api/adaptations.ts:解构 `.data`,baseURL 已含 /api,路径不带前缀。
 */
import http from '@/api/http'
import type { CarryValues } from '@/utils/carry-hint'

export type { CarryValues }

/** authz M2a S4 作用域:'global'(默认,公共项目层,Admin+)/'user'(个人层,
 * 本人)/'project'(项目层,项目管理员 —— S7.3 项目配置页签)。 */
export type CarryScope = 'global' | 'user' | 'project'

/** scope 附加参:project 层必须带 projectId(后端 _resolve_scope)。 */
export type ScopeTarget = { scope: CarryScope; projectId?: number }

function scopeParams(target: ScopeTarget) {
  if (target.scope === 'global') return {}
  return { params: target.projectId != null
    ? { scope: target.scope, projectId: target.projectId }
    : { scope: target.scope } }
}

export async function getDefaults(
  target: ScopeTarget = { scope: 'global' },
): Promise<CarryValues> {
  const { data } = await http.get<{ defaults: CarryValues }>(
    '/carry/defaults', scopeParams(target))
  return data.defaults
}

export async function putDefaults(
  defaults: CarryValues, target: ScopeTarget = { scope: 'global' },
): Promise<CarryValues> {
  const { data } = await http.put<{ defaults: CarryValues }>(
    '/carry/defaults', { defaults }, scopeParams(target))
  return data.defaults
}

export async function getBindings(): Promise<Record<string, CarryValues>> {
  const { data } = await http.get<{ bindings: Record<string, CarryValues> }>(
    '/carry/bindings')
  return data.bindings
}

/** 单层读(scope 参数形态,项目/个人配置页用;不带 scope 的并集读走 getBindings)。 */
export async function getBindingsFor(
  service: string, target?: ScopeTarget,
): Promise<CarryValues> {
  const { data } = await http.get<{ bindings: CarryValues }>(
    `/carry/bindings/${encodeURIComponent(service)}`,
    target ? scopeParams(target) : undefined)
  return data.bindings
}

export async function putBindings(
  service: string, bindings: CarryValues, target?: ScopeTarget,
): Promise<CarryValues> {
  const { data } = await http.put<{ bindings: CarryValues }>(
    `/carry/bindings/${encodeURIComponent(service)}`,
    { bindings }, target ? scopeParams(target) : undefined)
  return data.bindings
}

/** 单个 carry 字段的面元信息(plate /full request.declarations 的 carry 通道条目聚合并集)。 */
export interface CarryEndpointMini {
  id: string
  name?: string
  method?: string
  path?: string
}

export interface CarryFieldFace {
  path: string
  type: string
  description: string
  /** G6:声明此字段的服务内端点集合(配置页分组上下文)。 */
  endpoints?: CarryEndpointMini[]
}

/** 字段面聚合响应(对齐后端 ServiceFieldsOut):degraded=True = 任一端点
 *  /full 失败(抛错或 404),面不完整 — 保存是整表替换,会不可逆删除
 *  不可见端点的绑定值,调用方必须据此禁存直到刷新恢复。 */
export interface ServiceFields {
  fields: CarryFieldFace[]
  degraded: boolean
}

export async function getServiceFields(service: string): Promise<ServiceFields> {
  const { data } = await http.get<ServiceFields>(
    `/carry/bindings/${encodeURIComponent(service)}/fields`)
  return data
}

/** 单服务漂移项:orphaned=绑定有面无 / uncovered=面有绑定无 /
 *  renamedSuggestions=单×单 配对建议(多候选不猜)。 */
export interface ServiceDrift {
  service: string
  orphaned: string[]
  uncovered: string[]
  renamedSuggestions: Array<{ from: string; to: string }>
}

/** 漂移报告:plateReachable=False 时 services 照常返回,但面视为空集 →
 *  全部绑定误报为 orphaned — 先判该信号再渲染/放行批生成。
 *  S7.6:scope/scopeId = 报告层标签(缺省请求 = 公共项目层)。 */
export interface DriftReport {
  services: ServiceDrift[]
  plateReachable: boolean
  scope?: string | null
  scopeId?: number | null
}

/** S7.6 按层拉漂移:target 缺省 = 公共项目层(Admin+);project 层 =
 * 项目管理员;user 层 = 本人(分权与 carry 写面同口径)。 */
export async function getDrift(target?: ScopeTarget): Promise<DriftReport> {
  const { data } = await http.get<DriftReport>(
    '/carry/drift', target ? scopeParams(target) : undefined)
  return data
}
