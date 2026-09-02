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

export async function getDefaults(): Promise<CarryValues> {
  const { data } = await http.get<{ defaults: CarryValues }>('/carry/defaults')
  return data.defaults
}

export async function putDefaults(defaults: CarryValues): Promise<CarryValues> {
  const { data } = await http.put<{ defaults: CarryValues }>(
    '/carry/defaults', { defaults })
  return data.defaults
}

export async function getBindings(): Promise<Record<string, CarryValues>> {
  const { data } = await http.get<{ bindings: Record<string, CarryValues> }>(
    '/carry/bindings')
  return data.bindings
}

export async function getBindingsFor(service: string): Promise<CarryValues> {
  const { data } = await http.get<{ bindings: CarryValues }>(
    `/carry/bindings/${encodeURIComponent(service)}`)
  return data.bindings
}

export async function putBindings(
  service: string, bindings: CarryValues,
): Promise<CarryValues> {
  const { data } = await http.put<{ bindings: CarryValues }>(
    `/carry/bindings/${encodeURIComponent(service)}`, { bindings })
  return data.bindings
}

/** 单个 carry 字段的面元信息(plate /full request.declarations 的 carry 通道条目聚合并集)。 */
export interface CarryFieldFace { path: string; type: string; description: string }

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
 *  全部绑定误报为 orphaned — 先判该信号再渲染/放行批生成。 */
export interface DriftReport {
  services: ServiceDrift[]
  plateReachable: boolean
}

export async function getDrift(): Promise<DriftReport> {
  const { data } = await http.get<DriftReport>('/carry/drift')
  return data
}
