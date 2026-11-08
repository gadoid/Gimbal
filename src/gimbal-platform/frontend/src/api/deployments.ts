/**
 * api/deployments.ts — 部署表(authz M2a S2.2):(基础服务, 环境) → 地址。
 *
 * authz M2a S6 起部署表是地址的**唯一**来源(别名地址已随瘦身退役,
 * /deployments/conflicts 端点同步移除 —— 不再有按别名自带地址的
 * 裁定面)。读 = 登录用户;写 = Admin+(ops.write)。
 */
import http from '@/api/http'

export interface Deployment {
  id: number
  baseService: string
  envId: number
  baseUrl: string
}

export function listDeployments(envId?: number): Promise<Deployment[]> {
  return http.get<Deployment[]>('/deployments', {
    params: envId ? { envId } : {},
  }).then(({ data }) => data)
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
