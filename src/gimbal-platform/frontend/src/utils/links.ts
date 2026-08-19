/**
 * links.ts — 路由拼接的唯一出口。
 *
 * id 可能含空格 / 非 ASCII（path 式 case id 保留 "/"），统一走
 * encodeURIComponent（前端路由段语义；"/" 在 path-to-regexp 段内同样
 * 需要编码）。此前 8 处手拼散落各视图，其中 2 处漏编码。
 */
export function executionUrl(id: number | string): string {
  return `/executions/${encodeURIComponent(String(id))}`
}

/** 用例只读详情页(CaseDetailView) */
export function caseViewUrl(caseId: string): string {
  return `/cases/${encodeURIComponent(caseId)}`
}

export function caseDataSetsUrl(caseId: string): string {
  return `/cases/${encodeURIComponent(caseId)}/data-sets`
}

export function composerUrl(scenarioId: string, step = 1): string {
  return `/composer/${encodeURIComponent(scenarioId)}?step=${step}`
}

export function caseDataSetUrl(caseId: string, datasetId: string | 'new'): string {
  return `/cases/${encodeURIComponent(caseId)}/data-sets/${encodeURIComponent(datasetId)}`
}
