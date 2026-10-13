/**
 * executionStatus.ts — 执行状态 → 中文文案的唯一映射。
 *
 * 此前 ExecutionsList.vue 与 Executions.vue 各自维护一份内容相同的
 * 映射；新增状态（如 cancelled）需要改两处。
 * （V3 起 run 级状态已随 exec_runs 退役，仅保留 Execution 状态；
 * running = 认证解析通过、行分发开始，终态由 dispatcher 覆写。）
 */
export const EXECUTION_STATUS_LABELS: Record<string, string> = {
  queued: '排队',
  running: '运行中',
  done: '完成',
  failed: '失败',
  canceled: '已取消',
}

export function executionStatusText(s: string): string {
  return EXECUTION_STATUS_LABELS[s] ?? s
}

/**
 * 行级状态 → 人话(B-3,2026-10-14):内部码直接外露用户看不懂
 * (plate_rejected 什么意思?去哪修?)。映射只做「是什么 + 去哪看」,
 * 具体原因在 error 字段/行工件里。未收录码原样显示(不吞信息)。
 */
export const ROW_STATUS_LABELS: Record<string, string> = {
  queued: '排队',
  dispatched: '已分发',
  passed: '通过',
  failed: '失败',
  canceled: '取消',
  skipped: '跳过',
  gimbal_rejected: '定义被引擎拒绝',
  plate_unavailable: 'plate 不可达',
  plate_rejected: '定义校验未通过(plate)',
  launch_timeout: '启动超时',
  launch_error: '引擎启动失败',
  dispatcher_error: '调度失败',
  auth_failed: '认证失败',
}

export function rowStatusText(s: string): string {
  return ROW_STATUS_LABELS[s] ?? s
}

/** canceled 与 done/failed 同为终态(轮询停止条件)。 */
export function isTerminalExecutionStatus(s: string): boolean {
  return s === 'done' || s === 'failed' || s === 'canceled'
}
