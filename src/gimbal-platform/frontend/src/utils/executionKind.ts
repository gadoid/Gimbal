/**
 * 执行形态判定(N3 归一,评审 2026-11-01 §3.2 拆判定):与后端
 * `app/models/execution.py` 的 `NON_SCENARIO_KINDS` / `is_scenario_backed`
 * 同口径,回答「执行是否挂在真实场景上」(按场景筛选 / 按配方重跑 /
 * 详情页链到场景)。临时调用(adhoc)等新形态落地时加进本集合 ——
 * 组件不散写这条判定。
 *
 * 「是不是 Suite 编排」是**另一个问题**:Suite 专属视图
 * (SuiteRunsTab / SuiteLibrary / 执行列表的 Suite 链接)按需直接比较
 * `kind === 'suite_graph'`(与后端 suites 路由保留直接比较同理由 —
 * 那是 Suite 自身的展示语义,新形态不该被当成 Suite 运行)。
 */

/** 不挂在真实场景上的形态:scenario_id 是占位 `<前缀>-<id>`。 */
export const NON_SCENARIO_KINDS = ['suite_graph'] as const

export type NonScenarioKind = (typeof NON_SCENARIO_KINDS)[number]

/** 执行是否挂在真实场景上(缺省 kind 视为 'scenario',与后端口径一致)。 */
export function isScenarioBacked(
  kind: string | null | undefined,
): boolean {
  return !(NON_SCENARIO_KINDS as readonly string[]).includes(kind ?? 'scenario')
}
