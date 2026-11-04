/**
 * value-display.ts — 值的展示格式化(纯函数,零 IO)
 *
 * 共享收口:此前「对象值 → 紧凑 JSON / 标量原样」的判别在
 * Executions.formatRecipeValue / ScenarioDetailView.prettyVal /
 * CaseDataSetsList.valueSummary 等处各写一份(6+ 份重复)。
 */

/** 容器值(对象/数组;null 是显式标量叶,不算) */
export function isStructuredValue(v: unknown): v is Record<string, unknown> | unknown[] {
  return typeof v === 'object' && v !== null
}

/**
 * 紧凑 JSON(tooltip / CSV 等机读通道):容器值保结构可读,
 * 不出现 [object Object];标量退化为 String(与 prettyVal 同语义)。
 */
export function valueJson(v: unknown): string {
  return isStructuredValue(v) ? JSON.stringify(v) : String(v ?? '')
}
