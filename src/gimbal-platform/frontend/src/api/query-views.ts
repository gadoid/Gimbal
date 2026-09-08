/**
 * query-views.ts — 动态取数源行集拉取(2026-09-07 spec §7,Task 9)。
 *
 * 消费 Task 7 的 rows 路由:`GET /api/query-views/{name}/rows`
 * (platform 代理 → query_view_runner;L1/L2 缓存 + 熔断 + stale 回退)。
 * 错误经 http.ts 拦截器归一为 ApiError 抛出(detail.code 进 error.code —
 * 字符串码如 sut_auth_expired 由 normalizeError 透传,§7.5 降级判定面)。
 */
import http from './http'

export interface QueryViewRowsResult {
  view: string
  rows: Array<Record<string, unknown>>
  truncated: boolean
  fetched_at: string
  cached: boolean
  stale: boolean
}

export async function fetchQueryViewRows(
  name: string,
  opts: { refresh?: boolean; serviceUrl?: string; queryAlias?: string | null } = {},
): Promise<QueryViewRowsResult> {
  const { data } = await http.get(`/query-views/${encodeURIComponent(name)}/rows`, {
    params: {
      refresh: opts.refresh ? 1 : 0,
      ...(opts.serviceUrl ? { service_url: opts.serviceUrl } : {}),
      ...(opts.queryAlias ? { query_alias: opts.queryAlias } : {}),
    },
  })
  return data
}
