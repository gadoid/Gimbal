/**
 * links.ts — 路由拼接的唯一出口。
 *
 * id 可能含空格 / 非 ASCII,统一走 encodeURIComponent(前端路由段语义)。
 * 数据集独立路由已退役(D1,重构方案 Phase 2 批次 0),对应 URL 助手一并移除。
 */
export function executionUrl(id: number | string): string {
  return `/executions/${encodeURIComponent(String(id))}`
}

/** 场景详情页(数据驱动的可读渲染) */
export function scenarioDetailUrl(scenarioId: string): string {
  return `/scenarios/${encodeURIComponent(scenarioId)}/detail`
}

export function composerUrl(scenarioId: string, step = 1): string {
  return `/composer/${encodeURIComponent(scenarioId)}?step=${step}`
}

/** 断言管理编辑器 — 场景级注册表(spec v2 §7)。
 *  entryId 给定时带 `?entry=` —— 编辑器进入「聚焦单条」态(只渲染该条);
 *  省略则进全量视图(列表 + 手工新建)。 */
export function scenarioAssertionsUrl(scenarioId: string, entryId?: string): string {
  const base = `/scenarios/${encodeURIComponent(scenarioId)}/assertions`
  return entryId ? `${base}?entry=${encodeURIComponent(entryId)}` : base
}

/** 方案工作台(spec 2026-09-14 §6);schemeId 用于深链右栏选中态 */
export function scenarioSchemesUrl(scenarioId: string, schemeId?: string): string {
  const base = `/scenarios/${encodeURIComponent(scenarioId)}/schemes`
  return schemeId ? `${base}?scheme=${encodeURIComponent(schemeId)}` : base
}
