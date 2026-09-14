/**
 * value-display.ts — 值的展示格式化(纯函数,零 IO)
 *
 * 共享收口:此前「对象值 → 紧凑 JSON / 标量原样」的判别在
 * Executions.formatRecipeValue / ScenarioDetailView.prettyVal /
 * CaseDataSetsList.valueSummary 等处各写一份(6+ 份重复)。
 * 数据集基线引入语义提示(对象 · N 字段)后统一走本文件。
 */

/** 容器值(对象/数组;null 是显式标量叶,不算) */
export function isStructuredValue(v: unknown): v is Record<string, unknown> | unknown[] {
  return typeof v === 'object' && v !== null
}

/** 直接子值里存在容器 → 结构嵌套(提示加「嵌套」) */
function hasNestedChild(v: Record<string, unknown> | unknown[]): boolean {
  const values = Array.isArray(v) ? v : Object.values(v)
  return values.some(isStructuredValue)
}

/**
 * 语义提示(替代 `String(v)` 的 "[object Object]"):
 * 标量原样 / 容器给「是什么 · 多大」— 让「有值还是没值」一眼可辨。
 * undefined/null → ''(与既有基线空态约定一致)。
 */
export function valueHint(v: unknown): string {
  if (v === undefined || v === null) return ''
  if (Array.isArray(v)) {
    const head = v.length ? `数组 · ${v.length} 项` : '空数组'
    return hasNestedChild(v) ? `${head} · 嵌套` : head
  }
  if (isStructuredValue(v)) {
    const n = Object.keys(v).length
    const head = n ? `对象 · ${n} 字段` : '空对象'
    return hasNestedChild(v) ? `${head} · 嵌套` : head
  }
  return String(v)
}

/**
 * 紧凑 JSON(tooltip / CSV 等机读通道):容器值保结构可读,
 * 不出现 [object Object];标量退化为 String(与 prettyVal 同语义)。
 */
export function valueJson(v: unknown): string {
  return isStructuredValue(v) ? JSON.stringify(v) : String(v ?? '')
}
