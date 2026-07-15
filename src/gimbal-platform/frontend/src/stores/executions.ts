/**
 * executions.ts — Pinia store + 1s polling for live status.
 *
 * The store proxies /api/executions/* and exposes a `startPolling(id)`
 * helper that auto-refreshes detail every second until status reaches
 * a terminal state (done/failed).
 */
import { defineStore } from 'pinia'
import { ref, onUnmounted } from 'vue'
import * as api from '@/api/executions'
import type {
  Execution,
  ExecutionCreateIn,
  ExecutionDetail,
} from '@/api/executions'

const POLL_INTERVAL_MS = 1000

export const useExecutionsStore = defineStore('executions', () => {
  const list = ref<Execution[]>([])
  const detail = ref<ExecutionDetail | null>(null)
  const loading = ref(false)
  const lastError = ref('')
  let pollHandle: ReturnType<typeof setInterval> | null = null

  async function fetchList(): Promise<Execution[]> {
    loading.value = true
    try {
      const r = await api.list()
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

  async function fetchDetail(id: number): Promise<ExecutionDetail> {
    loading.value = true
    try {
      const d = await api.get(id)
      detail.value = d
      lastError.value = ''
      return d
    } catch (e) {
      lastError.value = e instanceof Error ? e.message : 'fetch failed'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function create(payload: ExecutionCreateIn): Promise<Execution> {
    const ex = await api.create(payload)
    list.value = [ex, ...list.value]
    return ex
  }

  async function remove(id: number): Promise<void> {
    await api.remove(id)
    list.value = list.value.filter((e) => e.id !== id)
    if (detail.value?.id === id) detail.value = null
  }

  /**
   * Poll /api/executions/{id} every 1s until status is done/failed.
   * Returns a stop function the caller invokes on unmount.
   */
  function startPolling(id: number): () => void {
    stopPolling()
    const tick = async () => {
      try {
        const d = await api.get(id)
        detail.value = d
        if (d.status === 'done' || d.status === 'failed') {
          stopPolling()
        }
      } catch {
        // soft-fail: keep polling on transient errors
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

  onUnmounted(stopPolling)

  return {
    list,
    detail,
    loading,
    lastError,
    fetchList,
    fetchDetail,
    create,
    remove,
    startPolling,
    stopPolling,
  }
})