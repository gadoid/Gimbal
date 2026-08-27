/**
 * executions.ts — Pinia store + 1s polling for live status.
 *
 * The store proxies /api/executions/* and exposes a `startPolling(id)`
 * helper that auto-refreshes detail every second until status reaches
 * a terminal state (done/failed/canceled).
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/executions'
import type { Execution } from '@/api/executions'
import { isTerminalExecutionStatus } from '@/utils/executionStatus'

const POLL_INTERVAL_MS = 1000

export const useExecutionsStore = defineStore('executions', () => {
  const list = ref<Execution[]>([])
  const detail = ref<Execution | null>(null)
  const loading = ref(false)
  const lastError = ref('')
  /** Set when the detail poller gives up (404 / repeated failures). */
  const pollError = ref('')
  let pollHandle: ReturnType<typeof setInterval> | null = null

  async function fetchList(): Promise<Execution[]> {
    loading.value = true
    try {
      const r = await api.listExecutions()
      list.value = r.items
      lastError.value = ''
      return r.items
    } catch (e) {
      lastError.value = e instanceof Error ? e.message : 'fetch failed'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchDetail(id: number): Promise<Execution> {
    loading.value = true
    try {
      const d = await api.get(id)
      detail.value = d
      lastError.value = ''
      // Manual refresh succeeded — clear any stale poll-gave-up message.
      pollError.value = ''
      return d
    } catch (e) {
      lastError.value = e instanceof Error ? e.message : 'fetch failed'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function remove(id: number): Promise<void> {
    await api.remove(id)
    list.value = list.value.filter((e) => e.id !== id)
    if (detail.value?.id === id) detail.value = null
  }

  /**
   * Poll /api/executions/{id} every 1s until status is terminal
   * (done/failed/canceled). Returns a stop function the caller
   * invokes on unmount.
   */
  function startPolling(id: number): () => void {
    stopPolling()
    pollError.value = ''
    // Soft-fail budget: transient network hiccups shouldn't kill the
    // poller, but a deleted execution (404 forever) or a dead backend
    // must not poll at 1 req/s indefinitely while the page sits open.
    let consecutiveFailures = 0
    const MAX_CONSECUTIVE_FAILURES = 10
    const tick = async () => {
      try {
        const d = await api.get(id)
        consecutiveFailures = 0
        detail.value = d
        if (isTerminalExecutionStatus(d.status)) {
          stopPolling()
        }
      } catch (e) {
        consecutiveFailures += 1
        const status = (e as { status?: number }).status
        if (status === 404) {
          // Execution was deleted (other tab / another user) — stop and
          // surface it instead of silently polling a corpse.
          stopPolling()
          detail.value = null
          pollError.value = '该执行记录已不存在（可能已被删除）'
        } else if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
          stopPolling()
          pollError.value = '轮询连续失败，已停止刷新 — 请手动刷新重试'
        }
      }
    }
    pollHandle = setInterval(tick, POLL_INTERVAL_MS)
    return stopPolling
  }

  function stopPolling() {
    if (pollHandle !== null) {
      clearInterval(pollHandle)
      pollHandle = null
    }
  }

  return {
    list,
    detail,
    loading,
    lastError,
    pollError,
    fetchList,
    fetchDetail,
    remove,
    startPolling,
    stopPolling,
  }
})