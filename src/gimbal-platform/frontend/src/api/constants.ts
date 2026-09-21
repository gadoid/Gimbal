/** constants.ts — /api/constants 常量池 CRUD 包装。 */
import http from './http'
import type {
  ConstantEntry,
  ConstantEntryCreateIn,
  ConstantEntryPatchIn,
} from '@/types/constants'

/** M4 Page 信封(§6.3)。 */
export interface ConstantsPage {
  items: ConstantEntry[]
  total: number
  page: number
  pageSize: number
}

export function list(params?: {
  q?: string
  kind?: string
  page?: number
  page_size?: number
}) {
  return http
    .get<ConstantsPage>('/constants', { params })
    .then((r) => r.data)
}

/** 全量便利(小池消费方):编排面板/管理页仍要全集。 */
export function listAll() {
  return list({ page: 1, page_size: 200 }).then((p) => p.items)
}

export function create(payload: ConstantEntryCreateIn) {
  return http.post<ConstantEntry>('/constants', payload).then((r) => r.data)
}

export function patch(id: number, payload: ConstantEntryPatchIn) {
  return http.patch<ConstantEntry>(`/constants/${id}`, payload).then((r) => r.data)
}

export function remove(id: number) {
  return http.delete(`/constants/${id}`).then(() => undefined)
}
