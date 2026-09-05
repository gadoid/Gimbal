/**
 * 策略显示名覆写(2026-09-05 P7 文案统一收口):快捷菜单动作已去响应化
 * (提取该字段 / 向该字段动态注入 / 断言该字段),策略卡徽标与「添加策略」
 * 下拉同口径 — plate 旧 label 含「从响应/注入响应」描述,在展示层覆写;
 * kind 数据面(plate API 契约/草稿存储)不动,未知 kind 回落 plate label。
 */
export const STRATEGY_LABEL_OVERRIDES: Record<string, string> = {
  extract: '提取该字段',
  assign: '向该字段动态注入',
  assertion: '断言该字段',
}

/** kind 的显示名:覆写表命中用覆写,否则 plate label 原样 */
export function strategyLabelOf(kind: string, plateLabel: string): string {
  return STRATEGY_LABEL_OVERRIDES[kind] ?? plateLabel
}
