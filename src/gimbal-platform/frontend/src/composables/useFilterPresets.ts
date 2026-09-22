/**
 * useFilterPresets.ts — 场景库「暂存分组」:把当前筛选状态(搜索词 +
 * 高级筛选)存成命名分组,点分组整体还原。定位 = 轻量暂存,不是场景
 * 的组织结构改造(场景本体不动、不建实体分组表)。
 *
 * 持久化:localStorage,按 用户 id + 分桶(mine/public)隔离键空间 —
 * 纯前端状态,不动后端契约;换设备/清浏览器数据不迁移(暂存语义可接受)。
 * 同名保存 = 覆盖(改条件重存是常态,不留一堆旧名)。
 */
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import type { ScenarioFilters } from '@/utils/filters'

export interface FilterPreset {
  id: string
  name: string
  q: string
  filters: ScenarioFilters
  createdAt: string
}

export function useFilterPresets(bucket: 'mine' | 'public') {
  const auth = useAuthStore()
  const storageKey = `gimbal.scenario-presets.${auth.currentUser?.id ?? 'anon'}.${bucket}`
  const presets = ref<FilterPreset[]>([])

  function load(): void {
    try {
      const raw = localStorage.getItem(storageKey)
      presets.value = raw ? (JSON.parse(raw) as FilterPreset[]) : []
    } catch {
      presets.value = [] // 脏数据不阻塞页面
    }
  }

  function persist(): void {
    try {
      localStorage.setItem(storageKey, JSON.stringify(presets.value))
    } catch { /* 容量满/隐私模式:静默,本次会话内仍可用 */ }
  }

  /** 保存(同名覆盖);返回存入的分组。 */
  function save(name: string, q: string, filters: ScenarioFilters): FilterPreset {
    const preset: FilterPreset = {
      id: `p-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
      name,
      q,
      filters: JSON.parse(JSON.stringify(filters)) as ScenarioFilters,
      createdAt: new Date().toISOString(),
    }
    const idx = presets.value.findIndex((p) => p.name === name)
    if (idx >= 0) presets.value.splice(idx, 1, preset)
    else presets.value.push(preset)
    persist()
    return preset
  }

  function remove(id: string): void {
    presets.value = presets.value.filter((p) => p.id !== id)
    persist()
  }

  load()
  return { presets, save, remove }
}
