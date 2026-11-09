/**
 * api/environments.ts — 环境组 API client（Release v4.4 §11 V5-B;authz
 * M2a S2 起环境是地址链的选择维度）。
 *
 * environments 声明「每个系统部署的是哪条版本线」（lines =
 * {系统名: 版本线}）;``is_default`` = Admin 指定的默认环境(环境链末位
 * 兜底,D2)。visibility 随 0044 删除。字段为后端原样蛇形(EnvironmentView
 * 无驼峰别名)。服务别名不再挂靠环境(authz M2a S6)— 环境只经部署表
 * 给地址、经环境链选执行环境。
 */
import http from '@/api/http'

export interface EnvironmentRow {
  id: number
  name: string
  description: string
  lines: Record<string, string>
  owner_id: number | null
  is_default: boolean
}

export function listEnvironments(): Promise<EnvironmentRow[]> {
  return http.get<EnvironmentRow[]>('/environments').then(({ data }) => data)
}

/** 置为默认环境(Admin+;后端原子切换,旧默认自动清除) */
export function setDefaultEnvironment(id: number): Promise<EnvironmentRow> {
  return http.post<EnvironmentRow>(`/environments/${id}/default`)
    .then(({ data }) => data)
}

/** 取消默认(之后没显式选环境的执行按别名地址走旧链) */
export function unsetDefaultEnvironment(id: number): Promise<EnvironmentRow> {
  return http.delete<EnvironmentRow>(`/environments/${id}/default`)
    .then(({ data }) => data)
}
