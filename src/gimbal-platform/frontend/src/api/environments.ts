/**
 * api/environments.ts — 环境组 API client（Release v4.4 §11 V5-B）。
 *
 * environments 声明「每个系统部署的是哪条版本线」（lines =
 * {系统名: 版本线}）。读全员；写 owner/admin（团队共享配置）。
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

export function createEnvironment(input: {
  name: string
  description?: string
  lines?: Record<string, string>
}): Promise<EnvironmentRow> {
  return http.post<EnvironmentRow>('/environments', input)
    .then(({ data }) => data)
}

export function updateEnvironment(
  id: number,
  input: { description?: string; lines?: Record<string, string> },
): Promise<EnvironmentRow> {
  return http.put<EnvironmentRow>(`/environments/${id}`, input)
    .then(({ data }) => data)
}

export function deleteEnvironment(id: number): Promise<void> {
  return http.delete(`/environments/${id}`).then(() => undefined)
}
