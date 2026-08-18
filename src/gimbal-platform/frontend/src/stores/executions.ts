/**
 * executions.ts — Pinia store + 1s polling for live status.
 *
 * The store proxies /api/executions/* and exposes a `startPolling(id)`
 * helper that auto-refreshes detail every second until status reaches
 * a terminal state (done/failed).
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/executions'
import type {
  Execution,
  ExecutionCreateIn,
  ExecutionDetail,
  ExecRun,
} from '@/api/executions'

const POLL_INTERVAL_MS = 1000

export const useExecutionsStore = defineStore('executions', () => {
  const list = ref<Execution[]>([])
  const detail = ref<ExecutionDetail | null>(null)
  const loading = ref(false)
  const lastError = ref('')
  /** Set when the detail poller gives up (404 / repeated failures). */
  const pollError = ref('')
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

  async function create(payload: ExecutionCreateIn): Promise<Execution> {
    const ex = await api.create(payload)
    list.value = [ex, ...list.value]
    return ex
  }

  /**
   * Optimistically append a newly-created run row to detail.runs so the
   * table updates immediately, no fetchDetail roundtrip required.  Used
   * by the rerun handler in Executions.vue — the API already returns
   * the full post-subprocess ExecRunOut, so this is safe (no
   * placeholder data).
   */
  function appendRun(run: ExecRun): void {
    if (!detail.value) return
    // Replace if already present (defensive — should not happen, but
    // guards against a double-click in the same tick).
    const idx = detail.value.runs.findIndex((r) => r.id === run.id)
    if (idx >= 0) {
      detail.value.runs[idx] = run
    } else {
      detail.value.runs = [...detail.value.runs, run]
    }
    // total_runs also grew by 1 (B-model: rerun inserts a new row).
    // Keep the parent's count in sync so the header counters update.
    detail.value.total_runs = (detail.value.total_runs || 0) + 1
  }

  /** Optimistically drop a deleted run + decrement parent counters. */
  function removeRun(runId: number): void {
    if (!detail.value) return
    const removed = detail.value.runs.find((r) => r.id === runId)
    detail.value.runs = detail.value.runs.filter((r) => r.id !== runId)
    detail.value.total_runs = Math.max(0, (detail.value.total_runs || 0) - 1)
    if (removed?.status === 'passed') {
      detail.value.passed = Math.max(0, (detail.value.passed || 0) - 1)
    } else if (removed?.status === 'failed') {
      detail.value.failed = Math.max(0, (detail.value.failed || 0) - 1)
    }
  }

  async function remove(id: number): Promise<void> {
    await api.remove(id)
    list.value = list.value.filter((e) => e.id !== id)
    if (detail.value?.id === id) detail.value = null
  }

  /**
   * Per-row "rerunning" markers.  Stored as a Set on the store (NOT
   * on the run row object) because the 1s polling wholesale-replaces
   * ``detail`` on every tick, wiping any per-row mutation.  Tracking
   * on the store lets the button stay in :loading state across
   * polling refreshes.
   */
  const rerunningIds = ref<Set<number>>(new Set())
  function markRerunning(runId: number, on: boolean) {
    const next = new Set(rerunningIds.value)
    if (on) next.add(runId)
    else next.delete(runId)
    rerunningIds.value = next
  }
  function isRerunning(runId: number): boolean {
    return rerunningIds.value.has(runId)
  }

  /**
   * Poll /api/executions/{id} every 1s until status is done/failed.
   * Returns a stop function the caller invokes on unmount.
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
        if (d.status === 'done' || d.status === 'failed') {
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
    rerunningIds,
    isRerunning,
    markRerunning,
    fetchList,
    fetchDetail,
    create,
    remove,
    appendRun,
    removeRun,
    startPolling,
    stopPolling,
  }
})