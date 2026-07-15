/** cases.ts — typed wrappers around /api/cases/* endpoints. */
import http from './http'

export interface CaseSummary {
  case_id: string
  name: string
  module: string
  description: string
  visibility: string
  owner_id: number | null
  audited: boolean
  file_path: string
  updated_at: string
  tags: string[]
  priority: number | null  // 1 | 2 | 3
  author: string | null  // meta.author || meta.owner
  favorited_by_me: boolean
  copied_by_me: boolean
}

export interface CaseListOut {
  items: CaseSummary[]
  total: number
}

export interface CaseDetailOut {
  payload: Record<string, unknown>
  summary: CaseSummary
}

export interface CopyOut {
  case_id: string
  path: string
}

export interface FavoriteOut {
  case_id: string
  favorited: boolean
}

export function mine() {
  return http.get<CaseListOut>('/cases/mine').then((r) => r.data)
}

export function publicList() {
  return http.get<CaseListOut>('/cases/public').then((r) => r.data)
}

export function get(caseId: string) {
  // case_id may contain slashes (path-style case ids), so URL-encode.
  return http
    .get<CaseDetailOut>(`/cases/${encodeURI(caseId)}`)
    .then((r) => r.data)
}

export function patch(
  caseId: string,
  payload: { payload: Record<string, unknown> },
) {
  return http
    .patch<CaseSummary>(`/cases/${encodeURI(caseId)}`, payload)
    .then((r) => r.data)
}

export interface HiddenProfile {
  case_id: string
  hidden_paths: string[]
  scope: string
  updated_at: string | null
}

export function getHidden(caseId: string) {
  return http
    .get<HiddenProfile>(`/cases/${encodeURIComponent(caseId)}/hidden`)
    .then((r) => r.data)
}

export function putHidden(
  caseId: string,
  payload: { hidden_paths: string[]; scope?: string },
) {
  return http
    .put<HiddenProfile>(
      `/cases/${encodeURIComponent(caseId)}/hidden`,
      payload,
    )
    .then((r) => r.data)
}

export function favorite(caseId: string) {
  return http
    .post<FavoriteOut>(`/cases/${encodeURI(caseId)}/favorite`)
    .then((r) => r.data)
}

export function unfavorite(caseId: string) {
  return http.delete(`/cases/${encodeURI(caseId)}/favorite`).then(() => undefined)
}

export function copy(caseId: string, payload: { new_name?: string } = {}) {
  return http
    .post<CopyOut>(`/cases/${encodeURI(caseId)}/copy`, payload)
    .then((r) => r.data)
}

export function saveAs(
  caseId: string,
  payload: { new_name?: string; visibility?: 'private' | 'public' },
) {
  return http
    .post<CopyOut>(
      `/cases/${encodeURI(caseId)}/save-as`,
      payload,
    )
    .then((r) => r.data)
}

export function upload(file: File, visibility: 'private' | 'public' = 'private') {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('visibility', visibility)
  return http
    .post<CaseSummary>('/cases/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((r) => r.data)
}

export function remove(caseId: string) {
  return http
    .delete(`/cases/${encodeURIComponent(caseId)}`)
    .then(() => undefined)
}

export function publish(caseId: string) {
  return http
    .post<CaseSummary>(`/cases/${encodeURIComponent(caseId)}/publish`)
    .then((r) => r.data)
}

export function rename(caseId: string, newCaseId: string) {
  return http
    .post<CaseSummary>(`/cases/${encodeURI(caseId)}/rename`, {
      new_case_id: newCaseId,
    })
    .then((r) => r.data)
}
