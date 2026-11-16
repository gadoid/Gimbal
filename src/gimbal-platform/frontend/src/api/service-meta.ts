/**
 * api/service-meta.ts — 服务说明(legacy 门面,registry 重构 P1-8)。
 *
 * service_meta 表已退役:说明是服务主档 services.description 的一列。
 * 本模块保形转发到 /api/services,让 ServiceAdmin/ServiceAliasDetail/
 * ExecConfigsView 的既有调用签名不动(页面重做时再直接用 services API)。
 *
 * 语义变化:putServiceMeta 只能改主档已有行(upsert 不再凭空建行 ——
 * 注册簿制:说明挂在登记的服务上)。
 */
import { listServices, patchService } from '@/api/services'
import type { ServiceRow } from '@/api/services'

export interface ServiceMetaRow {
  serviceName: string
  description: string
  updatedAt: string | null
}

function toRow(s: ServiceRow): ServiceMetaRow {
  return { serviceName: s.name, description: s.description,
           updatedAt: s.updatedAt }
}

export function listServiceMeta(): Promise<ServiceMetaRow[]> {
  return listServices().then(({ services }) => services.map(toRow))
}

export async function putServiceMeta(
  serviceName: string, description: string,
): Promise<ServiceMetaRow> {
  return toRow(await patchService(serviceName, { description }))
}
