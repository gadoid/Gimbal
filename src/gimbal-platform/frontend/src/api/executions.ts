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
  /** 批次键(执行设计 §1.2):队列逐条发起的 N 条共用;单条发起/历史行 null。 */
  batch_id: string | null
  /** 连续第 N 次失败(§3.2 信号列;仅 failed 行非 0)— 同 scenario 连续失败链长。 */
  consecutive_failures: number
  /** G1 读侧投影:展示名 = 可读活名 → 执行时快照 → 裸 id(缺省回落 id)。 */
  scenario_display_name?: string
  /** 场景行已删(快照仍是审计权威,照常展示)。 */
  scenario_deleted?: boolean
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
    /** 方案溯源(run_dispatcher 写入):本次执行按哪个方案发起;
     *  非方案发起(公共原件验证执行等)为 null/缺省。 */
    schemeId?: string | null
    schemeName?: string | null
    // 系统标记(后端按需写入;详情页转告警条,不进配方 dl)
    /** 认证快速失败标记(§3.2 信号):dispatch 侧凭证解析 fail-fast 写入 */
    authFailFast?: { error: string }
    /** 批次键(与 Execution.batch_id 同值;rerun 重建配方时读) */
    batchId?: string | null
    /** 启动期 reconcile 收敛记录(P3:进程重启僵尸单) */
    reconciled?: { at: string; reason: string }
    /** 计数器漂移:passed+failed ≠ total_runs(P8 校账,真值以 JSONL 为准) */
    counterDrift?: boolean
  }
}

/** 列表行形态(M1 响应投影,PG迁移方案 §2.2 债 4 补刀):去 config —
 *  config_json 是凭证引用面,不随行下发;详情页保留完整 config。
 *  configSummary = 列表 UI 既有的四个非敏感展示字段的窄投影。 */
export interface ExecutionListItem extends Omit<Execution, 'config'> {
  configSummary: {
    schemeId?: string | null
    schemeName?: string | null
    nRuns?: number
    parallel?: number
    stepTo?: number | null
    authFailFast?: { error: string }
  }
}

export interface ExecutionListEnvelope {
  items: ExecutionListItem[]
  total: number
  page: number
  pageSize: number
}

/** 行级状态(spec §9.1)— rows 端点返回的 camelCase 行结构 */
export interface ExecutionRow {
  seq: number
  datasetId: string | null
  /** G1:数据集名投影(随场景可见性;null = 已删/不可读,回落 datasetId)。 */
  datasetName?: string | null
  /** 注入族行的条目 id(spec v2 §8);数据集行/旧 JSONL 回放缺键 → null */
  injectionId?: string | null
  rowIndex: number
  rep: number
  status: string
  caseDir: string
  startedAt: string | null
  finishedAt: string | null
}

export function listExecutions(params?: {
  scenarioId?: string
  /** 检索词下推(M4):scenario_name/scenario_id 子串 + 执行号前缀 */
  q?: string
  limit?: number
  offset?: number
  page?: number
  pageSize?: number
  /** 状态筛(执行设计 §3.4);后端校验非法值 422 */
  status?: ExecutionStatus
  /** 批次筛(队列归并视图) */
  batchId?: string
  /** 发起时间范围 ISO(锚 created_at;queued 单 started_at 可空不作锚) */
  createdFrom?: string
  createdTo?: string
}) {
  // 后端 Query 形参是 snake_case — 出参侧保持 snake_case(既有约定)。
  return http
    .get<ExecutionListEnvelope>('/executions', {
      params: {
        scenario_id: params?.scenarioId,
        q: params?.q,
        limit: params?.limit,
        offset: params?.offset,
        page: params?.page,
        page_size: params?.pageSize,
        status: params?.status,
        batch_id: params?.batchId,
        created_from: params?.createdFrom,
        created_to: params?.createdTo,
      },
    })
    .then((r) => r.data)
}

/** 顶部 KPI 带(执行设计 §3.5):Execution 计数器/时间戳就能算的量。
 *  口径 = 查询者自己的执行(owner 隔离);行级分布不落库,不在响应里。 */
export interface ExecutionsSummary {
  windowDays: number
  totalExecutions: number
  totalRuns: number
  passedRuns: number
  failedRuns: number
  passRate: number | null
  avgDurationSec: number | null
  repeatFailureScenarios: number
  activeExecutions: number
}

export function getExecutionsSummary(windowDays = 7): Promise<ExecutionsSummary> {
  return http
    .get<ExecutionsSummary>('/executions/summary', { params: { window_days: windowDays } })
    .then((r) => r.data)
}

/** 同配置重跑(§3.4):按 config_json 重建配方,新的一次独立发起(不带原批)。 */
export function rerunExecution(id: number): Promise<{ runId: string; executionId: number }> {
  return http
    .post<{ runId: string; executionId: number }>(`/executions/${id}/rerun`)
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

/** 行级状态(M6,债 5):活跃执行读 dispatcher registry,历史执行读
 *  execution_rows DB;信封 {items,total,page,pageSize}(单执行行数
 * 有限,默认一页全取,信封为超长单留分页口)。 */
export function getExecutionRows(
  id: number, page = 1, pageSize = 500,
): Promise<{ items: ExecutionRow[]; total: number; page: number; pageSize: number }> {
  return http
    .get<{ items: ExecutionRow[]; total: number; page: number; pageSize: number }>(
      `/executions/${id}/rows`, { params: { page, page_size: pageSize } })
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
