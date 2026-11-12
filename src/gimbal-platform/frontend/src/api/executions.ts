/** executions.ts — typed wrappers around /api/executions/* endpoints. */
import http from './http'
import type { ScenarioDraft } from '@/types/scenario-composer'
import type { ServiceBinding } from './scenario-composer'

export type ExecutionStatus = 'queued' | 'running' | 'done' | 'failed' | 'canceled'

/** 台账 config.serviceBindings 的读侧宽容形状:新执行 = {alias}(M2a S6),
 *  历史执行可能仍是 legacy {authAlias,url} — 展示层只读不回写。 */
export type ExecutionServiceBinding = ServiceBinding & { authAlias?: string; url?: string }

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
  /** Suite 层重构:kind=suite_graph = 编排执行(scenario_id 是占位
   *  suite-<id>,scenario_display_name 是 Suite 名);聚合成员执行仍是
   *  scenario、只多记 suite_id。P3:kind=adhoc = 入站临时调用(scenario_id
   *  占位 adhoc-<runId>,scenario_name 为「临时调用 · 别名 · 锚点」;
   *  非场景形态由 utils/executionKind 统一判定,列表不给占位 id 与重跑)。 */
  kind?: string
  suite_id?: number | null
  config: {
    // V3 dispatcher 写入的配方键(run_dispatcher._create_execution,
    // 与 RunRequest 创建入参一一对应;camelCase)。
    runId?: string
    scenarioId?: string
    dataSetIds?: string[]
    envId?: string
    /** 实际注入清单(模板扫描 ∪ 绑定别名声明的槽位)— 读侧据此展示认证列 */
    injectedAuths?: string[]
    /** service → 绑定(authz M2a S6 起新执行 = {svc:{alias}};旧执行存量
     *  可能仍是 legacy {authAlias,url} — 展示按 JSON 原样渲染,两形状都容忍) */
    serviceBindings?: Record<string, ExecutionServiceBinding>
    /** 0-based inclusive halt index(W19 前的旧平铺键;新行读 runOptions) */
    stepTo?: number | null
    nRuns?: number
    parallel?: number
    /** 执行指令快照(W19:RunOptions 生成物 dump,内层 snake_case) */
    runOptions?: {
      step_from?: number | null
      step_to?: number | null
      n_runs?: number
      parallel?: number
    } | null
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
    // ── 2026-11-12 配方字段审计补记(run_dispatcher._create_execution
    //    实写键对账;去向:dl = 执行明细「执行信息」表)─────────────
    /** 数据集行级选择快照(请求回显,by_alias dump;空 = 全部行)→ dl「数据集选择」 */
    dataSetSelection?: Array<Record<string, unknown>>
    /** 行级账号覆盖({datasetId:rowIndex: {槽: 绑定 id}},M2b Q3)→ dl「行级账号覆盖」 */
    rowBindings?: Record<string, unknown>
    /** 注入条目 id(悬空过滤**前**请求原样;rerun 重建配方唯一来源)→ 机器面不进 dl */
    injectionEntryIds?: Array<string | number>
    /** 报告方案引用(UI 直发为 null)→ dl「报告方案」(空不渲染) */
    reportDefinitionId?: string | null
    /** S2.1 环境选择快照(无环境键缺席)→ 与 source 并合成行「执行环境」 */
    environmentId?: number | null
    /** 环境来源枚举(explicit/scheme/project/preference/exec_config[_default]/default)→ 译中文 */
    environmentSource?: string | null
    /** §6.3 环境版本线告警(人类可读文本)→ dl「环境告警」 */
    environmentWarnings?: string[]
    /** spec §1.1 Y 判定降级审计(键缺席 = 未发生)→ dl「判定降级」 */
    judgeDegraded?: boolean
    /** 降级期间被跳过的条目 id → dl「降级期跳过条目」 */
    entriesSkippedWhileDegraded?: Array<string | number>
    // ── 机器面键(回放快照 / webhook 审计块 / 调试留档 / 回调产物):
    //    无读侧展示价值,不进 dl —— 重跑回放走 API,webhook 台账由
    //    「入站来源」行 +「含范围外目标」旗标承接,回调产物在报告
    //    步骤提取值可读,ingest_stats 是引擎自监控调试计数。
    chain?: string
    ingest_stats?: Record<string, unknown>
    outputs?: Record<string, unknown>
    execSlotMap?: Record<string, unknown>
    execCarryOverrides?: Record<string, unknown>
    execConfigId?: number
    credentialSource?: string
    credentialProjectId?: number
    resolvedServices?: Record<string, unknown>
    builtinAuths?: Array<unknown>
    token?: Record<string, unknown>
    outOfScope?: Record<string, unknown>
  }
  /** 系统版本信息(W21,原「修订台账」):执行时生效版本 {系统: "<line>#<n>"};null = 未钉/预览执行 */
  plate_pins?: Record<string, string> | null
  /** M2 构建身份(W21 派发回填;历史执行 = null) */
  m2_hash?: string | null
  /** 场景当前声明的 meta.plate(重跑将使用;场景已删 = null) */
  current_plate?: Record<string, string> | null
  /** B-3:失败原因(终态失败单 = dispatcherError;成功/运行中 null) */
  error?: string | null
  /** 可取消标志(服务端给,前端不按 status 自推 —— 全量评估 2026-11-02 #1):
   *  graph 链(Suite 编排 / POST /api/runs 带 graph)任务体一经认领即 false
   *  (不看执行状态,不消费取消位,cancel 端点同口径 409);其余 queued/
   *  running 为 true。 */
  cancelable?: boolean
  /** 取消中(单元级取消方案 P4):取消位已写、任务仍活 —— graph 要等在飞
   *  单元跑完才收口,期间 running && cancel_requested 显示「取消中」、按钮隐藏。 */
  cancel_requested?: boolean
  /** 取消说明文案(服务端给,前端原样显示,不按 kind 自推):取消中 → 等的是
   *  在飞单元(graph)还是当前行(cases)按任务体 kind 区分,POST /api/runs
   *  带 graph 的执行 kind 仍是 scenario;终态 → 点了取消却按真实结果收口
   *  (config.cancelIgnored)的原因。 */
  cancel_note?: string | null
  /** 令牌只读投影(webhook v4 §7.1):经哪张令牌(id/名称快照)、以谁
   *  身份(authz C1 后恒 personal=属主)/ 调用方对账键。
   *  JWT 发起的执行三者皆 null。 */
  token_id?: number | null
  identity_mode?: 'personal' | null
  token_name?: string | null
  client_ref?: string | null

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
  /** 趋势切换点判定(W21):每次执行的修订钉定表 */
  plate_pins?: Record<string, string> | null

}

export interface ExecutionListEnvelope {
  items: ExecutionListItem[]
  total: number
  page: number
  pageSize: number
  /** 与 total 同筛选口径的失败单数(服务端全口径;客户端只数得出当前页) */
  failedTotal: number
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
  /** B6(R11 轻量版):server 链槽位号 → 引擎日志 server-engine[-N].log;
   *  launch 链 / 存量行为 null(日志在 case 目录自带) */
  serverSlot?: number | null
}

// ── B4 执行报告(2026-11-06 日志报告整理)────────────────────────
/** 一条断言的结果(引擎 step.end 投影;敏感目标已脱敏、超长值已截断)。 */
export interface ReportAssertion {
  name: string
  target: string | null
  operator: string | null
  expected: unknown
  actual: unknown
  passed: boolean
  message: string | null
}

export interface ReportExtract {
  target: string
  value: unknown
}

export interface ReportStep {
  rowSeq: number
  unit: string
  attempt: string
  stepId: string
  stepName: string
  description: string | null
  callSummary: string
  status: string
  durationMs: number
  error: string | null
  assertionCount: number
  assertionPassed: number
  assertions: ReportAssertion[]
  extracts: ReportExtract[]
  hasEvidence: boolean
}

/** 调用证据(与 call.exchange 同形;已脱敏,请求/响应体 16K 截断)。 */
export interface ReportEvidence {
  protocol?: string
  request?: { method?: string; url?: string; headers?: Record<string, unknown>; body?: unknown }
  response?: { status?: unknown; meta?: Record<string, unknown>; body?: unknown }
  elapsed_ms?: number
}

export interface ReportGroup {
  key: string
  rowSeq: number
  unit: string
  datasetId: string | null
  rowIndex: number
  rep: number
  status: string
  caseDir: string
  serverSlot: number | null
  steps: ReportStep[]
}

export interface ExecutionReport {
  execution: {
    id: number
    scenarioId: string
    scenarioName: string
    status: ExecutionStatus
    kind: string
    suiteId: number | null
    batchId: string | null
    startedAt: string | null
    finishedAt: string | null
    durationMs: number | null
    totalRuns: number
    passed: number
    failed: number
    skipped: number
  }
  summary: {
    steps: number
    stepsPassed: number
    stepsFailed: number
    stepsOther: number
    assertions: number
    assertionsPassed: number
  }
  groups: ReportGroup[]
  failure: (ReportStep & { failedAssertions: ReportAssertion[]; evidence: ReportEvidence | null }) | null
  /** false = 早于步骤落库的执行或旧引擎:报告无步骤数据,看「执行明细」工件 */
  hasStepData: boolean
}

export function getExecutionReport(id: number): Promise<ExecutionReport> {
  return http.get<ExecutionReport>(`/executions/${id}/report`).then((r) => r.data)
}

// ── B5 批次汇总 ────────────────────────────────────────────────
export interface BatchSummary {
  batchId: string
  total: number
  counts: Partial<Record<ExecutionStatus, number>>
  startedAt: string | null
  finishedAt: string | null
  active: boolean
  members: Array<{
    id: number
    scenarioId: string
    scenarioName: string
    status: ExecutionStatus
    passed: number
    failed: number
    totalRuns: number
  }>
}

export function getBatchSummary(batchId: string): Promise<BatchSummary> {
  return http
    .get<BatchSummary>('/executions/batch-summary', { params: { batchId } })
    .then((r) => r.data)
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
  /** 按访问令牌列经它发起的执行(webhook v4)。authz W4:执行可见收敛为
   *  属主∨本令牌(admin 旁路已删)—— 后端只回调用方自己可见的行。 */
  tokenId?: number
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
        token_id: params?.tokenId,
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

// ── P2-06/P2-07:执行事件流(SSE)与事件/日志查询 ─────────────────

/** 事件/日志统一行(execution_events 投影;标签只取执行器写入值)。 */
export interface ExecutionEventItem {
  id: number
  seq: number
  ts: string
  kind: 'event' | 'log'
  level: string | null
  category: string | null
  module: string | null
  service: string | null
  protocol: string | null
  unit: string | null
  attempt: string | null
  step: string | null
  event_type: string | null
  message: string | null
  payload?: Record<string, unknown>
}

/** SSE 流地址(Bearer 头鉴权 → fetch 流式读取,EventSource 不支持头)。 */
export function executionEventsStreamUrl(id: number): string {
  return `/api/executions/${id}/events/stream`
}

/** 日志流地址(AD5:tail 游标=入库 id;backfill 仅首次回看;服务端筛选)。 */
export function executionLogsStreamUrl(
  id: number,
  params: Record<string, string | number | undefined> = {},
): string {
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')
  return `/api/executions/${id}/logs/stream${qs ? `?${qs}` : ''}`
}

export interface ExecutionEventsQuery {
  kind?: 'event' | 'log'
  level?: string
  level_min?: string
  category?: string
  module?: string
  service?: string
  unit?: string
  step?: string
  event_type?: string
  search?: string
  after_seq?: number
  // (ts,id) 翻页锚(批 3)与 S2 上下文窗口锚(批 4)
  after_ts?: string
  after_id?: number
  around_ts?: string
  around_id?: number
  n_before?: number
  n_after?: number
  limit?: number
}

/** 事件/日志组合筛选(P2-07 日志分析页读面)。 */
export function getExecutionEvents(
  id: number, q: ExecutionEventsQuery = {},
): Promise<{ items: ExecutionEventItem[]; count: number }> {
  return http
    .get<{ items: ExecutionEventItem[]; count: number }>(
      `/executions/${id}/events`, { params: q })
    .then((r) => r.data)
}


// ── C6(P3-04):调试台(执行器 token 不出后端;命令与引擎 DebugCommand 同形;
//    调试装载形状 = m2.ts 生成物 DebugSpec,W19 起随 RunRequest.runOptions 上送)──

export interface DebugSessionInfo {
  executionId: number
  status: string
  active: boolean
  runId: string | null
}

export interface DebugCommandBody {
  kind: 'continue' | 'step' | 'abort' | 'read' | 'write' | 'patch' | 'retry' | 'skip'
  variable?: string
  path?: string
  value?: unknown
}

export function getDebugSession(id: number): Promise<DebugSessionInfo> {
  return http.get<DebugSessionInfo>(`/executions/${id}/debug`).then((r) => r.data)
}

export function getDebugOutput(id: number): Promise<{ output: string[] }> {
  return http.get<{ output: string[] }>(`/executions/${id}/debug/output`)
    .then((r) => r.data)
}

export function postDebugCommand(
  id: number, body: DebugCommandBody,
): Promise<{ accepted: boolean; output: string[] }> {
  return http.post<{ accepted: boolean; output: string[] }>(
    `/executions/${id}/debug/command`, body).then((r) => r.data)
}

/** 按 category 聚合计数(P2-07 验收)。 */
export function getExecutionEventCounts(
  id: number,
): Promise<{ byCategory: Record<string, number> }> {
  return http
    .get<{ byCategory: Record<string, number> }>(`/executions/${id}/events/counts`)
    .then((r) => r.data)
}
