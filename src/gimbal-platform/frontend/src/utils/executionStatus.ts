/**
 * executionStatus.ts — 执行/运行状态 → 中文文案的唯一映射。
 *
 * 此前 ExecutionsList.vue 与 Executions.vue 各自维护一份内容相同的
 * 映射；新增状态（如 cancelled）需要改两处。
 */
export const EXECUTION_STATUS_LABELS: Record<string, string> = {
  queued: '排队',
  running: '运行中',
  done: '完成',
  failed: '失败',
}

export const RUN_STATUS_LABELS: Record<string, string> = {
  pending: '排队',
  running: '运行中',
  passed: '通过',
  failed: '失败',
}

export function executionStatusText(s: string): string {
  return EXECUTION_STATUS_LABELS[s] ?? s
}

export function runStatusText(s: string): string {
  return RUN_STATUS_LABELS[s] ?? s
}
