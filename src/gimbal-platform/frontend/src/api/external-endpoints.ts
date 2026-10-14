/** external-endpoints.ts — 外部接口登记目录(X1;I4 增 querySafe 开关)。 */
import http from '@/api/http'

export interface ExternalEndpointItem {
  id: number
  aliasName: string
  name: string
  title: string
  method: string
  path: string
  requestSchema: Record<string, unknown> | null
  auth: string
  /** I4(集成线 v2 §3.2):平台模式只读口径的目录级标记 —— admin 显式
   * 标记/撤销(后端写审计);POST 查询标了它即可进平台模式 */
  querySafe: boolean
  notes: string | null
  updatedAt: string | null
}

export async function listExternalEndpoints(
  alias: string,
): Promise<ExternalEndpointItem[]> {
  const { data } = await http.get<{ items: ExternalEndpointItem[] }>(
    '/external-endpoints', { params: { alias } })
  return data.items
}

export async function setExternalQuerySafe(
  alias: string, name: string, on: boolean,
): Promise<ExternalEndpointItem> {
  const { data } = await http.post<ExternalEndpointItem>(
    `/external-endpoints/${encodeURIComponent(alias)}/${encodeURIComponent(name)}/query-safe`,
    { on })
  return data
}
