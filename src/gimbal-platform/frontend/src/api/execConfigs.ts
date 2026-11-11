/**
 * api/execConfigs.ts — 执行配置 API client(执行配置分层①)。
 *
 * 执行配置 = 场景外部支撑的跨场景载体:在哪(envId)/以谁(bindings)/
 * 带什么业务参数(carryOverrides)。个人面(全员,owner 隔离);一套
 * 默认 + 若干命名,新建可自现有配置复制。
 *
 * 零凭证值、零地址值(设计方案 §4):凭证由池按 (system, env, slot)
 * 解析、地址由部署表按 (目录服务, env) 解析 —— 这里只存引用键,
 * 槽位是名字,跨区可移植。
 */
import http from '@/api/http'

/** 按系统的子配置:bindings = {身份面(别名全名): 槽位名} */
export interface SystemSubConfig {
  service: string
  bindings: Record<string, string>
  /** null = 显式注入 JSON null(删键 = 不覆盖,走层序合成) */
  carryOverrides: Record<string, string | null>
}

export interface ExecConfigRow {
  id: number
  name: string
  isDefault: boolean
  environmentId: number | null
  systems: SystemSubConfig[]
  scope?: 'user' | 'project'
}

export interface ExecConfigCreateInput {
  name: string
  environmentId?: number | null
  systems?: SystemSubConfig[]
  isDefault?: boolean
  /** ⑧ 组级批次:project scope(项目变体;与 projectId 成对)。
   *  读=项目成员,写=项目管理员;v1 链路只消费 carry 覆盖 */
  scope?: 'user' | 'project'
  projectId?: number
}

export interface ExecConfigUpdateInput {
  name?: string
  /** 显式传 null = 不设置环境(链跳过此位);不传 = 不动 */
  environmentId?: number | null
  systems?: SystemSubConfig[]
}

/** 配置列表(默认在前);重名 409(exec_config_name_exists)。
 *  缺省 = 本人配置;projectId 给定 = 该项目的项目变体(读=成员) */
export function listExecConfigs(
  projectId?: number,
): Promise<ExecConfigRow[]> {
  return http.get<ExecConfigRow[]>('/exec-configs', {
    params: projectId != null ? { projectId } : {},
  }).then(({ data }) => data)
}

export function createExecConfig(
  body: ExecConfigCreateInput,
): Promise<ExecConfigRow> {
  return http.post<ExecConfigRow>('/exec-configs', body)
    .then(({ data }) => data)
}

export function getExecConfig(id: number): Promise<ExecConfigRow> {
  return http.get<ExecConfigRow>(`/exec-configs/${id}`)
    .then(({ data }) => data)
}

/** 整体替换式 PATCH;environmentId 语义见 ExecConfigUpdateInput */
export function updateExecConfig(
  id: number,
  body: ExecConfigUpdateInput,
): Promise<ExecConfigRow> {
  return http.patch<ExecConfigRow>(`/exec-configs/${id}`, body)
    .then(({ data }) => data)
}

/** 置为默认(环境链位④载体 + carry 个人默认;后端原子切换) */
export function setDefaultExecConfig(id: number): Promise<ExecConfigRow> {
  return http.post<ExecConfigRow>(`/exec-configs/${id}/default`)
    .then(({ data }) => data)
}

/** 复制为命名变体(§4「新建可自现有配置复制」;副本恒非默认) */
export function copyExecConfig(
  id: number,
  name: string,
): Promise<ExecConfigRow> {
  return http.post<ExecConfigRow>(`/exec-configs/${id}/copy`, { name })
    .then(({ data }) => data)
}

export function deleteExecConfig(id: number): Promise<void> {
  return http.delete(`/exec-configs/${id}`).then(() => undefined)
}

/** ③ 关联枢纽:配置 carryOverrides vs plate 面的 diff(orphaned = 覆盖了
 * 但面已没有;uncovered = 面有而未覆盖=按层序合成的部分)。 */
export interface ExecConfigDriftService {
  service: string
  orphaned: string[]
  uncovered: string[]
}

export function execConfigDrift(id: number): Promise<{
  services: ExecConfigDriftService[]
  plateReachable: boolean
}> {
  return http.get(`/exec-configs/${id}/drift`).then(({ data }) => data)
}
