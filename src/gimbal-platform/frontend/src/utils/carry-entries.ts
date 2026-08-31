/**
 * carry-entries.ts — CarryConfig 保存编码的纯核心(T15 fix R1)。
 *
 * 行三态(hasRow/isNull/value — el-input 会把 null 折叠成 '',故 null 用
 * 布尔列承载)→ CarryValues dict 的唯一编码点:
 * - 无行且无任何输入(值空、非 null)→ 跳过:不写入,运行时回退全局默认;
 * - 任何输入即建行:修复 B1 —— hasRow=false 的行输入框可编辑(透全局
 *   默认 placeholder),旧编码 `!hasRow → continue` 把「无绑定行但用户
 *   填了值」的字段静默丢弃,PUT 后仍无该行却 toast 已保存;
 * - '' 是合法空串值:hasRow 行清空输入仍存 '';
 * - null 只能由 isNull 承载(显式 JSON null,spec §3.1)。
 *
 * 纯函数:单测不挂 Vue(模式同 carry-hint.ts)。
 */
import type { CarryValues } from './carry-hint'

/** 服务绑定行编辑态(CarryConfig ServiceRow 的可编码子集)。 */
export interface ServiceCarryRow {
  path: string
  value: string
  isNull: boolean
  hasRow: boolean
}

/**
 * rows → entries:仅跳过「无行且无输入」的行(删行按钮已清 value/isNull,
 * 删后保存仍删);任何输入(有值或 isNull)即建行。
 */
export function buildServiceEntries(rows: readonly ServiceCarryRow[]): CarryValues {
  const entries: CarryValues = {}
  for (const r of rows) {
    if (!r.hasRow && !r.value && !r.isNull) continue
    entries[r.path] = r.isNull ? null : r.value
  }
  return entries
}
