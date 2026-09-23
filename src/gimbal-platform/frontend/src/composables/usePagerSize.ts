/**
 * usePagerSize.ts — 列表页「每页行数」的用户偏好(2026-09-23 分页批次)。
 *
 * 存储走 useUserPreference 的服务端键 ``pager.sizes``(值 = {页面slug:
 * 行数} 整值覆盖;同键全局单实例 → 12 个列表页共享一次 GET / 一发 PUT),
 * 镜像管首帧、服务端管跨设备。行为:
 *  - 初始值 = 镜像/服务端里本页的行数,没有 → fallback;
 *  - 服务端回读换新 map:用户尚未手动改过则采纳(手动改过 = 本机即新值,
 *    同键豁免规则由 useUserPreference 层兜);
 *  - 用户改行数 → 合并进 map 防抖 PUT(只有用户改动才写,采纳不写)。
 */
import { nextTick, ref, watch } from 'vue'
import { useUserPreference } from './useUserPreferences'

const MIN = 1
const MAX = 500

function clampSize(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) && v >= MIN && v <= MAX
    ? Math.floor(v)
    : null
}

export function usePagerSize(pageKey: string, fallback: number) {
  const pref = useUserPreference('pager.sizes', {
    mirrorPrefix: 'pager-sizes',
    fromMirror: (raw) => {
      if (!raw) return {}
      try {
        const v: unknown = JSON.parse(raw)
        return v && typeof v === 'object' ? v as Record<string, number> : {}
      } catch {
        return {}
      }
    },
    toMirror: (v) => JSON.stringify(v),
    toServer: (v) => ({ sizes: v }),
    fromServer: (raw) => {
      const s = (raw as { sizes?: unknown } | null)?.sizes
      return s && typeof s === 'object'
        ? s as Record<string, number>
        : null
    },
  })

  const pageSize = ref(clampSize(pref.value.value[pageKey]) ?? fallback)

  // 采纳服务端/镜像回读(自己写回的 map 因值相等自然短路)
  let suppressSave = false
  watch(pref.value, (map) => {
    const v = clampSize(map[pageKey])
    if (v == null || v === pageSize.value) return
    suppressSave = true
    pageSize.value = v
    void nextTick(() => { suppressSave = false })
  }, { deep: true })

  watch(pageSize, (n) => {
    if (suppressSave) return
    if (pref.value.value[pageKey] === n) return
    pref.value.value = { ...pref.value.value, [pageKey]: n }
    pref.save()
  })

  return { pageSize }
}
