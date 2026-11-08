/** M2a S1.8:当前区(项目切换器选中值)。
 * 'private' = 私有区(默认)| 'public' = 公共项目 | number = 普通项目 id。
 * localStorage 持久化;非法值回落私有区。列表参数投影:listParams
 * (公共区 → visibility=public;项目区 → projectId;私有区 → 不加)。 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const KEY = 'gimbal-zone'

export type Zone = 'private' | 'public' | number

function read(): Zone {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw === null || raw === 'private' || raw === 'public') return raw ?? 'private'
    const n = Number(raw)
    return Number.isInteger(n) && n > 0 ? n : 'private'
  } catch {
    return 'private'
  }
}

export const useZoneStore = defineStore('zone', () => {
  const zone = ref<Zone>(read())
  function set(z: Zone): void {
    zone.value = z
    try { localStorage.setItem(KEY, String(z)) } catch { /* 私有模式 */ }
  }
  const listParams = computed(() =>
    zone.value === 'public'
      ? { visibility: 'public' as const }
      : typeof zone.value === 'number'
        ? { projectId: zone.value }
        : {})
  return { zone, set, listParams }
})
