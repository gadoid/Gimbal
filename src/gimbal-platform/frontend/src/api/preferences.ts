/**
 * preferences.ts — 用户偏好读写客户端(GET 批量 + PUT 单键)。
 *
 * 值形态与后端 app/routers/user_preferences.py 的白名单模型一一对应;
 * 键名两边都要改才生效(后端拒收白名单外的键,是有意为之的护栏)。
 */
import http from './http'
import type { CardSize } from '@/components/workbench/registry'

/** 便签条目(与后端 NoteItem 同形态:驼峰,2026-11-05 评审 P1-2 定稿) */
export interface NoteItemDTO {
  id: string
  text: string
  done: boolean
  createdAt: string
  doneAt: string | null
}

export interface PrefValues {
  'workbench.layout': { order: string[]; sizes: Record<string, CardSize> }
  'follows.pinned': { ids: string[] }
  'timeline.colors': { execution: string; scenario: string; adaptation: string }
  /** 各列表页「每页行数」(2026-09-23 分页批次):键 = 页面 slug */
  'pager.sizes': { sizes: Record<string, number> }
  /** 便签卡(webhook v4 §4.3/D18) */
  notes: { items: NoteItemDTO[] }
}

export type PrefKey = keyof PrefValues

export function getPreferences() {
  return http
    .get<{ items: Partial<PrefValues> }>('/me/preferences')
    .then((r) => r.data.items)
}

export function putPreference(key: PrefKey, value: PrefValues[PrefKey]) {
  return http.put<{ key: string; value: PrefValues[PrefKey] }>(
    `/me/preferences/${key}`, { value })
}
