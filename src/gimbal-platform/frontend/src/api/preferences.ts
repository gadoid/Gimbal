/**
 * preferences.ts — 用户偏好读写客户端(GET 批量 + PUT 单键)。
 *
 * 值形态与后端 app/routers/user_preferences.py 的白名单模型一一对应;
 * 键名两边都要改才生效(后端拒收白名单外的键,是有意为之的护栏)。
 */
import http from './http'
import type { CardSize } from '@/components/workbench/registry'

export interface PrefValues {
  'workbench.layout': { order: string[]; sizes: Record<string, CardSize> }
  'follows.pinned': { ids: string[] }
  'timeline.colors': { execution: string; scenario: string; adaptation: string }
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
