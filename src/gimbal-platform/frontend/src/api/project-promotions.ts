/**
 * project-promotions — M2a S7.2 提升流程 API(加入项目 / 加入申请)。
 * 无冲突 → 立即复制(copied);有冲突 → pending 申请,项目管理员裁决。
 */
import http from './http'

export interface PromotionConflict {
  service: string
  path: string
  /** 原件在私有区的有效值(公共层 < 个人层) */
  sourceValue: string | null
  /** 项目层有效值(null = 项目层缺口 —— 采纳原件值即补写) */
  projectValue: string | null
  scenarioId?: string   // 用例集提升:来自哪个成员场景
}

export interface PromotionMemberPlan {
  scenarioId: string
  action: 'reference' | 'promote'
  copyOf?: string       // reference:指向项目里既有的提升副本
  role: string
}

export interface PromotionAnalysis {
  services: string[]
  conflicts: PromotionConflict[]
  blockers: { scenarioId: string; reason: string }[]
  slots: string[]
  memberPlan?: PromotionMemberPlan[]
}

export interface PromotionOut {
  id: number
  projectId: number
  kind: 'scenario' | 'suite'
  sourceId: string
  applicantId: number
  status: 'pending' | 'approved' | 'rejected' | 'withdrawn'
  conflicts: PromotionConflict[]
  resolution: {
    decisions?: { service: string; path: string; use: string }[]
    reason?: string
    decidedBy?: number
    decidedAt?: string
    immediate?: boolean
  } | null
  note: string
  createdAt: string | null
  updatedAt: string | null
  sourceChangedSinceApplication?: boolean
  copy?: { scenarioId?: string; suiteId?: number; copiedScenarioIds?: string[] }
}

export function analyzePromotion(
  projectId: number, body: { kind: 'scenario' | 'suite'; sourceId: string },
): Promise<PromotionAnalysis> {
  return http.post(`/projects/${projectId}/promotions/analyze`, body)
    .then((r) => r.data)
}

export function createPromotion(
  projectId: number, body: { kind: 'scenario' | 'suite'; sourceId: string },
): Promise<{ status: 'copied' | 'pending'; promotionId?: number;
  conflicts?: PromotionConflict[];
  copy?: { scenarioId?: string; suiteId?: number } }> {
  return http.post(`/projects/${projectId}/promotions`, body)
    .then((r) => r.data)
}

export function listPromotions(
  projectId: number, status?: string,
): Promise<{ items: PromotionOut[] }> {
  return http.get(`/projects/${projectId}/promotions`, {
    params: status ? { status } : undefined,
  }).then((r) => r.data)
}

export function getPromotion(id: number): Promise<PromotionOut> {
  return http.get(`/project-promotions/${id}`).then((r) => r.data)
}

export function approvePromotion(
  id: number, decisions: { service: string; path: string;
    use: 'source' | 'project'; sourceValue?: string | null }[],
): Promise<PromotionOut> {
  return http.post(`/project-promotions/${id}/approve`, { decisions })
    .then((r) => r.data)
}

export function rejectPromotion(id: number, reason: string): Promise<PromotionOut> {
  return http.post(`/project-promotions/${id}/reject`, { reason })
    .then((r) => r.data)
}

export function withdrawPromotion(id: number): Promise<PromotionOut> {
  return http.post(`/project-promotions/${id}/withdraw`)
    .then((r) => r.data)
}
