/**
 * 执行形态判定(N3 归一):与后端 `app/models/execution.py` 的
 * `ORCHESTRATION_KINDS` / `is_orchestration_kind` 同口径 —— 新增
 * 编排类形态时后端改集合、前端改此集合,组件里不散写 kind 比较。
 * (SuiteRunsTab 是 Suite 专属视图,其比较语义就是「编排」自身,保留。)
 */

/** 编排类形态:不挂在真实场景上(scenario_id 是占位 `<前缀>-<id>`)。 */
export const ORCHESTRATION_KINDS = ['suite_graph'] as const

export type OrchestrationKind = (typeof ORCHESTRATION_KINDS)[number]

/** 执行是否为编排类形态(缺省 kind 视为 'scenario',与后端口径一致)。 */
export function isOrchestrationKind(
  kind: string | null | undefined,
): boolean {
  return (ORCHESTRATION_KINDS as readonly string[]).includes(kind ?? 'scenario')
}
