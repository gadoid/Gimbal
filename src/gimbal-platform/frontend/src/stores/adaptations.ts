/**
 * adaptations store —— 适配中心徽章/待适配数据源(P5 D3)。
 *
 * admin 登录/刷新后 TopNav 静默拉一次(冷启动落基线属预期副作用);
 * 打开适配中心时 refreshDiff(true) 强制刷新。member 零调用(入口不发)。
 * 失败(plate 502/网络)保留旧数据只记 lastError,徽章不清零。
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/api/adaptations'
import type { CatalogDiffReport } from '@/api/adaptations'

export const useAdaptationsStore = defineStore('adaptations', () => {
  const pendingCount = ref(0)
  const diffReport = ref<CatalogDiffReport | null>(null)
  const lastError = ref('')
  const refreshing = ref(false)

  let inflight: Promise<void> | null = null
  let loaded = false

  async function refreshDiff(force = false): Promise<void> {
    if (inflight) return inflight
    if (loaded && !force) return
    refreshing.value = true
    lastError.value = ''
    inflight = (async () => {
      try {
        diffReport.value = await api.catalogDiff()
        pendingCount.value = diffReport.value.pending.length
        loaded = true
      } catch (e) {
        // spec §8:plate 不可用/网络错误 → 保留旧数据,仅记错
        lastError.value = api.errMsg(e, '目录服务不可用,稍后重试')
      } finally {
        refreshing.value = false
        inflight = null
      }
    })()
    return inflight
  }

  function ensureBadgeLoaded(): Promise<void> {
    return refreshDiff(false)
  }

  return { pendingCount, diffReport, lastError, refreshing, refreshDiff, ensureBadgeLoaded }
})
