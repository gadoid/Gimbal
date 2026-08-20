/**
 * executionStatus.ts — 执行状态 → 中文文案的唯一映射。
 *
 * 此前 ExecutionsList.vue 与 Executions.vue 各自维护一份内容相同的
 * 映射；新增状态（如 cancelled）需要改两处。
 * （V3 起 run 级状态已随 exec_runs 退役，仅保留 Execution 状态；
 * 后端从不写 running。）
 */
export const EXECUTION_STATUS_LABELS: Record<string, string> = {
  queued: '排队',
  done: '完成',
  failed: '失败',
}

export function executionStatusText(s: string): string {
  return EXECUTION_STATUS_LABELS[s] ?? s
}
