/**
 * scenario-filter-groups.ts — 场景库「筛选分组」客户端。
 *
 * 分组 = 一组命名过的搜索/筛选条件,存在服务端 user_prefs(按登录身份
 * 归属),所以换设备、清浏览器数据都还在。filters 字段对本模块是不透明
 * JSON,原样往返 —— 后端刻意不校验它的形态。
 */
import http from './http'
import type { ScenarioFilters } from '@/utils/filters'

export type FilterBucket = 'mine' | 'public'

export interface FilterGroup {
  id: string
  name: string
  q: string
  filters: ScenarioFilters
  /** aware ISO(带 offset);只用于 tooltip 展示,不做时区推算。 */
  createdAt: string
}

export function listFilterGroups(bucket: FilterBucket) {
  return http
    .get<{ items: FilterGroup[] }>('/scenario-filter-groups', { params: { bucket } })
    .then((r) => r.data.items)
}

/** 存分组;同名 = 服务端覆盖(改条件重存是常态),返回存入后的分组。 */
export function createFilterGroup(body: {
  bucket: FilterBucket
  name: string
  q: string
  filters: ScenarioFilters
}) {
  return http.post<FilterGroup>('/scenario-filter-groups', body).then((r) => r.data)
}

export async function deleteFilterGroup(bucket: FilterBucket, id: string): Promise<void> {
  await http.delete<{ removed: string }>(`/scenario-filter-groups/${bucket}/${id}`)
}
