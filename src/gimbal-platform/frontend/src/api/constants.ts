/** constants.ts — /api/constants 常量池 CRUD 包装。 */
import http from './http'
import type {
  ConstantEntry,
  ConstantEntryCreateIn,
  ConstantEntryPatchIn,
} from '@/types/constants'

export function list() {
  return http.get<ConstantEntry[]>('/constants').then((r) => r.data)
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
