/**
 * links.ts — 路由拼接的唯一出口。
 *
 * id 可能含空格 / 非 ASCII,统一走 encodeURIComponent(前端路由段语义)。
 */
export function executionUrl(id: number | string): string {
  return `/executions/${encodeURIComponent(String(id))}`
}

/** 场景详情页(数据驱动的可读渲染) */
export function scenarioDetailUrl(scenarioId: string): string {
  return `/scenarios/${encodeURIComponent(scenarioId)}/detail`
}

/** 场景的数据集列表页(Case 层已解散,数据集直接挂场景) */
export function scenarioDataSetsUrl(scenarioId: string): string {
  return `/scenarios/${encodeURIComponent(scenarioId)}/data-sets`
}

export function composerUrl(scenarioId: string, step = 1): string {
  return `/composer/${encodeURIComponent(scenarioId)}?step=${step}`
}

export function scenarioDataSetUrl(
  scenarioId: string,
  datasetId: string | 'new',
): string {
  return `/scenarios/${encodeURIComponent(scenarioId)}/data-sets/${encodeURIComponent(datasetId)}`
}
