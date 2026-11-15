/**
 * api/service-meta.ts — 服务级元数据(服务注册页「说明」列)。
 * 读全员(登录用户);写 Admin+(ops.write,后端 MemberUser 闸)。
 * upsert 语义:PUT 不存在则建、存在则覆写(审计 service_meta.write)。
 */
import http from '@/api/http'

export interface ServiceMetaRow {
  serviceName: string
  description: string
  updatedAt: string | null
}

export function listServiceMeta(): Promise<ServiceMetaRow[]> {
  return http.get<ServiceMetaRow[]>('/service-meta').then(({ data }) => data)
}

export function putServiceMeta(
  serviceName: string, description: string,
): Promise<ServiceMetaRow> {
  return http.put<ServiceMetaRow>(
    `/service-meta/${encodeURIComponent(serviceName)}`,
    { description },
  ).then(({ data }) => data)
}
