/** executions.ts — typed wrappers around /api/executions/* endpoints. */
import http from './http'

export type MergePolicy = 'override' | 'merge' | 'append'
export type ExecutionStatus = 'queued' | 'done' | 'failed' | 'canceled'

export interface Execution {
  id: number
  scenario_id: string
  status: ExecutionStatus
  total_runs: number
  passed: number
  failed: number
  started_at: string | null
  finished_at: string | null
  config: {
    // V3 dispatcher 写入的配方键(run_dispatcher._create_execution,
    // 与 RunRequest 创建入参一一对应;camelCase)。
    runId?: string
    scenarioId?: string
    dataSetIds?: string[]
    envId?: string
    exec_auth_alias?: string[]
    /** 0-based inclusive halt index(V3 写 stepTo) */
    stepTo?: number | null
    injectCredentials?: boolean
    nRuns?: number
    parallel?: number
    prefix?: string | null
    mergePolicy?: MergePolicy
  }
}

export function list() {
  return http
    .get<{ items: Execution[]; total: number }>('/executions')
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
