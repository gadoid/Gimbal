/**
 * api/deployments.ts — 部署表(authz M2a S2.2):(基础服务, 环境) → 地址。
 *
 * authz M2a S6 起部署表是地址的**唯一**来源(别名地址已随瘦身退役,
 * /deployments/conflicts 端点同步移除 —— 不再有按别名自带地址的
 * 裁定面)。读 = 登录用户;写 = Admin+(ops.write)。
 * 维护面在「服务注册」页(/service-admin,与身份面同页);
 * list 固定拉全环境矩阵 —— 按环境切片由调用方客户端过滤(独立部署页
 * 退役后不再有按 envId 取数的调用方;后端 env_id 查询参保留给外部)。
 */
import http from '@/api/http'

export interface Deployment {
  id: number
  baseService: string
  envId: number
  baseUrl: string
}

export function listDeployments(): Promise<Deployment[]> {
  return http.get<Deployment[]>('/deployments').then(({ data }) => data)
}

export function createDeployment(
  body: Omit<Deployment, 'id'>,
): Promise<Deployment> {
  return http.post<Deployment>('/deployments', body).then(({ data }) => data)
}

export function updateDeployment(id: number, baseUrl: string): Promise<Deployment> {
  return http.patch<Deployment>(`/deployments/${id}`, { baseUrl })
    .then(({ data }) => data)
}

export function deleteDeployment(id: number): Promise<void> {
  return http.delete(`/deployments/${id}`).then(() => undefined)
}

export interface PingResult {
  /** true = 拿到了 HTTP 响应(401/404 也算可达;与拨测语义不同) */
  ok: boolean
  statusCode: number | null
  latencyMs: number | null
  message: string
}

/** 连通测速:后端 GET 一次部署地址(短超时),返回状态码与毫秒。 */
export function pingDeployment(id: number): Promise<PingResult> {
  return http.post<PingResult>(`/deployments/${id}/ping`).then(({ data }) => data)
}
