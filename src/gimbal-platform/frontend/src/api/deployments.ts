/**
 * api/deployments.ts — 部署表(authz M2a S2.2):(基础服务, 环境) → 地址。
 *
 * 地址链第 ③ 层的数据源:显式选了环境(本次 / 方案 / 项目 / 个人偏好)
 * 时部署表优先;只落到默认环境时别名自带地址优先、部署表补缺(影子期,
 * S6 删别名地址后合一)。读 = 登录用户;写 = Admin+(ops.write)。
 */
import http from '@/api/http'

export interface Deployment {
  id: number
  baseService: string
  envId: number
  baseUrl: string
}

/** 回填时同键地址不一致、尚无部署行的键(待 Admin 裁定) */
export interface DeploymentConflict {
  baseService: string
  envId: number
  /** 别名名 → 自带地址 */
  aliases: Record<string, string>
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

export function listDeploymentConflicts(): Promise<DeploymentConflict[]> {
  return http.get<DeploymentConflict[]>('/deployments/conflicts')
    .then(({ data }) => data)
}
