/** executions.ts — typed wrappers around /api/executions/* endpoints. */
import http from './http'
import type { ScenarioDraft } from '@/types/scenario-composer'
import type { ServiceBinding } from './scenario-composer'

export type ExecutionStatus = 'queued' | 'running' | 'done' | 'failed' | 'canceled'

export interface Execution {
  id: number
  scenario_id: string
  status: ExecutionStatus
  total_runs: number
  passed: number
  failed: number
  started_at: string | null
  finished_at: string | null
  /** 执行时场景快照是否存在(存量行 false → 详情页"导出场景"置灰)。 */
  has_scenario_snapshot: boolean
  config: {
    // V3 dispatcher 写入的配方键(run_dispatcher._create_execution,
    // 与 RunRequest 创建入参一一对应;camelCase)。
    runId?: string
    scenarioId?: string
    dataSetIds?: string[]
    envId?: string
    /** 实际注入清单(模板扫描 ∪ 绑定 authAlias)— 读侧据此展示认证列 */
    injectedAuths?: string[]
    /** service → {authAlias?, url?}(驼峰 dump,None 键不落) */
    serviceBindings?: Record<string, ServiceBinding>
    /** 0-based inclusive halt index(V3 写 stepTo) */
    stepTo?: number | null
    nRuns?: number
    parallel?: number
    // 系统标记(后端按需写入;详情页转告警条,不进配方 dl)
    /** 启动期 reconcile 收敛记录(P3:进程重启僵尸单) */
    reconciled?: { at: string; reason: string }
    /** 计数器漂移:passed+failed ≠ total_runs(P8 校账,真值以 JSONL 为准) */
    counterDrift?: boolean
  }
}

/** 行级状态(spec §9.1)— rows 端点返回的 camelCase 行结构 */
export interface ExecutionRow {
  seq: number
  datasetId: string | null
  rowIndex: number
  rep: number
  status: string
  caseDir: string
  startedAt: string | null
  finishedAt: string | null
}

export function listExecutions(params?: { scenarioId?: string; limit?: number }) {
  // 后端 Query 形参是 snake_case scenario_id — 出参侧保持 camelCase。
  return http
    .get<{ items: Execution[]; total: number }>('/executions', {
      params: { scenario_id: params?.scenarioId, limit: params?.limit },
    })
    .then((r) => r.data)
}

export function get(id: number) {
  return http.get<Execution>(`/executions/${id}`).then((r) => r.data)
}

export function remove(id: number) {
  return http.delete(`/executions/${id}`).then(() => undefined)
}

/** P4 协作式取消:queued 单登记取消,canceled 为终态。 */
export function cancelExecution(id: number): Promise<Execution> {
  return http.post<Execution>(`/executions/${id}/cancel`).then((r) => r.data)
}

/** 行级状态(spec §9.1):活跃执行读 dispatcher registry,历史执行回放 JSONL。 */
export function getExecutionRows(id: number): Promise<{ items: ExecutionRow[] }> {
  return http
    .get<{ items: ExecutionRow[] }>(`/executions/${id}/rows`)
    .then((r) => r.data)
}

/** 白名单工件(text/plain):engine-log=引擎日志 / result=步骤级明细。
 *  case.json 刻意不暴露(含明文凭证,spec §9.1)。 */
export function getCaseArtifact(
  id: number, caseStem: string, file: 'engine-log' | 'result',
): Promise<string> {
  return http
    .get<string>(`/executions/${id}/case-artifact`, { params: { case: caseStem, file } })
    .then((r) => r.data)
}

/** 执行时场景快照(dispatch 同拍存的 draft 容器,场景后改不影响)。
 *  存量行无快照 → 404 {code:"scenario_snapshot_not_found"}。 */
export function getScenarioSnapshot(id: number): Promise<ScenarioDraft> {
  return http
    .get<ScenarioDraft>(`/executions/${id}/scenario-snapshot`)
    .then((r) => r.data)
}
