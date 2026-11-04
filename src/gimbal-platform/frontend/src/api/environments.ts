/**
 * api/environments.ts — 环境组 API client（Release v4.4 §11 V5-B,读面）。
 *
 * environments 声明「每个系统部署的是哪条版本线」（lines =
 * {系统名: 版本线}）。前端只消费列表(服务信息管理);写面
 * (POST/PUT/DELETE)后端在,前端暂无入口。
 * 服务别名经 environmentId 挂靠环境。
 */
import http from '@/api/http'

export interface EnvironmentRow {
  id: number
  name: string
  description: string
  visibility: string
  lines: Record<string, string>
  ownerId: number | null
}

export function listEnvironments(): Promise<EnvironmentRow[]> {
  return http.get<EnvironmentRow[]>('/environments').then(({ data }) => data)
}
