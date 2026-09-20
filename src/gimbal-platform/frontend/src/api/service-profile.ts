/**
 * api/service-profile.ts —— 服务画像 API client(P1 热力网格)。
 *
 * 契约照后端 app/schemas/service_profile.py(camelCase 显式 alias)。
 * 槽① signals.req P1 恒 null(plate reference dim 是 P2,方案 §5.6 挂起)。
 */
import http from '@/api/http'

export interface GridSignals {
  req: string | null
  cases: boolean
  lastRun: 'pass' | 'fail' | null
  alarm: boolean
}

export interface GridEndpoint {
  id: string
  method: string
  path: string
  name: string
  signals: GridSignals
  caseCount: number
  lastRunAt: string | null
}

export interface GridStats {
  total: number
  noCases: number
  hasAlarm: number
  neverRun: number
}

export interface ServiceGrid {
  service: string
  endpoints: GridEndpoint[]
  stats: GridStats
  plateReachable: boolean
}

export function fetchGrid(service: string): Promise<ServiceGrid> {
  return http
    .get<ServiceGrid>(`/services/${encodeURIComponent(service)}/grid`)
    .then(({ data }) => data)
}

// ─── 接口级线索板(方案 §3;P1:测试象限完整,其余象限占位)────────
export type Quadrant = 'requirement' | 'data' | 'test' | 'topology'

export type BoardNodeKind =
  | 'endpoint' | 'table' | 'topology' | 'reference'
  | 'scenario' | 'execution' | 'adaptation' | 'card'

export interface BoardSubject {
  id: string
  method: string
  path: string
  name: string
  version: string
  fieldCount: number
  degraded: boolean
}

export interface BoardNode {
  id: string
  kind: BoardNodeKind
  quadrant: Quadrant | null
  label: string
  meta: Record<string, unknown>
}

export interface BoardEdge {
  from: string
  to: string
  kind: 'contains' | 'refs' | 'affects' | 'ran' | 'annotates'
}

export interface BoardTrail {
  kind: 'risk'
  path: string[]
}

export interface BoardResponse {
  subject: BoardSubject
  nodes: BoardNode[]
  edges: BoardEdge[]
  trails: BoardTrail[]
  quadrants: Record<string, string>
}

export function fetchBoard(endpointId: string, expand?: string): Promise<BoardResponse> {
  return http
    .get<BoardResponse>(`/endpoints/${encodeURIComponent(endpointId)}/board`, {
      params: expand ? { expand } : undefined,
    })
    .then(({ data }) => data)
}

// ─── 自建卡(方案 §3.3):作者即权限边界 ──────────────────────────
export interface BoardCard {
  id: number
  subjectKind: string
  subjectId: string
  body: string
  isRoot: boolean
  quadrant: Quadrant
  annotatesNodeId: string | null
  authorId: number
  createdAt: string | null
  updatedAt: string | null
}

export function createCard(input: {
  subjectId: string
  body: string
  quadrant: Quadrant
  annotatesNodeId?: string | null
}): Promise<BoardCard> {
  return http.post<BoardCard>('/board-cards', input).then(({ data }) => data)
}

export function patchCard(
  id: number,
  input: Partial<Pick<BoardCard, 'body' | 'quadrant' | 'annotatesNodeId'>>,
): Promise<BoardCard> {
  return http.patch<BoardCard>(`/board-cards/${id}`, input).then(({ data }) => data)
}

export function deleteCard(id: number): Promise<void> {
  return http.delete(`/board-cards/${id}`).then(() => undefined)
}

export function promoteCard(id: number): Promise<BoardCard> {
  return http.post<BoardCard>(`/board-cards/${id}/promote`).then(({ data }) => data)
}

export function demoteCard(id: number): Promise<BoardCard> {
  return http.post<BoardCard>(`/board-cards/${id}/demote`).then(({ data }) => data)
}
