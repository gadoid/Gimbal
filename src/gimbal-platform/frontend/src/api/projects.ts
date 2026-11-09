/** M2a S1.4/S1.8:项目区管理面 API + 转移维护者/platformize。 */
import http from './http'

export interface ProjectOut {
  id: number
  name: string
  kind: string
  description: string
  memberCount: number
  myRole: string | null
  /** S7.0:请求者能否管理(项目管理员 ∨ Admin+;公共项目 = Admin+) */
  canManage?: boolean
  defaultEnvironmentId?: number | null
  /** 详情读面(S7.0):默认环境名 + 内容计数(列表端点不填) */
  defaultEnvironmentName?: string | null
  scenarioCount?: number
  suiteCount?: number
  taskCount?: number
}

export interface ProjectMember {
  userId: number
  username: string
  displayName: string
  role: string
  addedAt?: string | null
}

export function listProjects(): Promise<ProjectOut[]> {
  return http.get<ProjectOut[]>('/projects').then((r) => r.data)
}

/** 项目详情(S7.0):公共项目全员可读;普通项目非成员 404 */
export function getProject(id: number): Promise<ProjectOut> {
  return http.get<ProjectOut>(`/projects/${id}`).then((r) => r.data)
}

export function createProject(body: {
  name: string
  description?: string
  firstAdminUserId: number
}): Promise<ProjectOut> {
  return http.post<ProjectOut>('/projects', body).then((r) => r.data)
}

export function patchProject(id: number, body: {
  name?: string
  description?: string
}): Promise<ProjectOut> {
  return http.patch<ProjectOut>(`/projects/${id}`, body).then((r) => r.data)
}

export function deleteProject(id: number): Promise<void> {
  return http.delete(`/projects/${id}`).then(() => undefined)
}

export function listMembers(id: number): Promise<ProjectMember[]> {
  return http.get<ProjectMember[]>(`/projects/${id}/members`).then((r) => r.data)
}

export function addMember(
  id: number, body: { userId: number; role?: 'admin' | 'member' },
): Promise<ProjectMember> {
  return http.post<ProjectMember>(`/projects/${id}/members`, body)
    .then((r) => r.data)
}

export function patchMember(
  id: number, userId: number, role: 'admin' | 'member',
): Promise<ProjectMember> {
  return http.patch<ProjectMember>(
    `/projects/${id}/members/${userId}`, { role }).then((r) => r.data)
}

export function removeMember(id: number, userId: number): Promise<void> {
  return http.delete(`/projects/${id}/members/${userId}`).then(() => undefined)
}

/** S1-e:转移维护者(公共项目对象;resource ∈ scenarios|suites|report-definitions) */
export function transferMaintenance(
  resource: 'scenarios' | 'suites' | 'report-definitions',
  id: string | number, toUserId: number,
): Promise<{ transferredTo: number }> {
  return http.post(`/${resource}/${id}/transfer`, { toUserId })
    .then((r) => r.data)
}

/** D9:转为平台模板(Admin+;模板须在公共项目) */
export function platformizeTask(
  taskId: number,
): Promise<{ platformTemplate: boolean }> {
  return http.post(`/integration/tasks/${taskId}/platformize`)
    .then((r) => r.data)
}
