/**
 * executions.ts — Pinia store + 1s polling for live status.
 *
 * The store proxies /api/executions/* and exposes a `startPolling(id)`
 * helper that auto-refreshes detail every second until status reaches
 * a terminal state (done/failed/canceled).
 *
 * T13 行级可观测(spec §9.1):rows 只对「已展开」的执行随 tick 拉取
 * (避免列表 N+1);engine-log/result 工件按需拉取,不参与轮询。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/executions'
import type { Execution, ExecutionRow } from '@/api/executions'
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

  // ── 行级可观测(spec §9.1)──────────────────────────────
  /** execution id → 行级状态(仅已展开的执行有数据) */
  const rowsByExecution = ref<Record<number, ExecutionRow[]>>({})
  /** 已展开行级表格的 execution id 集合(轮询 tick 据此增量刷新) */
  const expanded = ref<Set<number>>(new Set())
  /** 工件文本缓存:key = `${id}:${caseStem}:${file}`(按需拉取,不轮询) */
  const artifactText = ref<Record<string, string>>({})
  /** 工件拉取失败文案(同 key;成功重拉时清除) */
  const artifactError = ref<Record<string, string>>({})
  /** 已展开工件视图的 key 集合(同上 key;收起只藏视图不清缓存) */
  const expandedArtifacts = ref<Set<string>>(new Set())

  /** 行级状态软失败:下次 tick/展开点击自然重试,不打断详情轮询。 */
  async function fetchRows(id: number): Promise<void> {
    try {
      rowsByExecution.value = {
        ...rowsByExecution.value,
        [id]: (await api.getExecutionRows(id)).items,
      }
    } catch {
      // 预部署/认证快速失败的单合法返回 [];网络错误留旧值等重试。
    }
  }

  async function fetchArtifact(
    id: number,
    caseStem: string,
    file: 'engine-log' | 'result',
  ): Promise<void> {
    const key = `${id}:${caseStem}:${file}`
    try {
      const text = await api.getCaseArtifact(id, caseStem, file)
      artifactText.value = { ...artifactText.value, [key]: text }
      const errs = { ...artifactError.value }
      delete errs[key]
      artifactError.value = errs
    } catch (e) {
      const msg = e instanceof Error ? e.message : '拉取失败'
      artifactError.value = { ...artifactError.value, [key]: `工件拉取失败：${msg}` }
    }
  }

  /** 展开即拉一次 rows;收起不清缓存(再展开即时可见,由 tick 增量刷新)。 */
  function toggleExpanded(id: number): void {
    const next = new Set(expanded.value)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    expanded.value = next
    if (next.has(id)) void fetchRows(id)
  }

  /** 工件视图展开/收起:展开即拉一次(运行中单日志在长,重展重拉最新);
   *  收起只藏视图,缓存留着重展不闪。 */
  function toggleArtifact(
    id: number,
    caseStem: string,
    file: 'engine-log' | 'result',
  ): void {
    const key = `${id}:${caseStem}:${file}`
    const next = new Set(expandedArtifacts.value)
    if (next.has(key)) {
      next.delete(key)
    } else {
      next.add(key)
      void fetchArtifact(id, caseStem, file)
    }
    expandedArtifacts.value = next
  }

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
    // T13-Q1:行级/工件缓存一并出清 — 该 id 的 rows、展开态与工件文本
    // 都指向已删执行;expanded 残留还会让 tick 继续拉一个 404。
    const nextExpanded = new Set(expanded.value)
    nextExpanded.delete(id)
    expanded.value = nextExpanded
    const nextRows = { ...rowsByExecution.value }
    delete nextRows[id]
    rowsByExecution.value = nextRows
    const keepOthers = (o: Record<string, string>): Record<string, string> =>
      Object.fromEntries(
        Object.entries(o).filter(([k]) => !k.startsWith(`${id}:`)),
      )
    artifactText.value = keepOthers(artifactText.value)
    artifactError.value = keepOthers(artifactError.value)
    const nextArtifacts = new Set(expandedArtifacts.value)
    for (const k of nextArtifacts) {
      if (k.startsWith(`${id}:`)) nextArtifacts.delete(k)
    }
    expandedArtifacts.value = nextArtifacts
  }

  /**
   * T13-Q2:tick 是否跳过 rid 的 rows 拉取 = 「已知终态 && 已有 rows 缓存」。
   * 终态是吸收态,list/detail 旧快照里的终态永远可信;状态未知(不在
   * list、也不是本拍轮询对象)不跳过 — 宁可多拉一拍,不冒陈旧行级状态。
   * ``prevDetail`` 是上一拍的 detail 快照:本拍 FIRST 观察到终态的那一拍
   * 仍要先拉到最终 rows(T13 不变量,见 tick 内顺序),跳过只发生在
   * 后续拍。
   */
  function shouldSkipRowFetch(rid: number, prevDetail: Execution | null): boolean {
    if (rowsByExecution.value[rid] === undefined) return false
    const status = prevDetail?.id === rid
      ? prevDetail.status
      : list.value.find((e) => e.id === rid)?.status
    return status !== undefined && isTerminalExecutionStatus(status)
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
        // 上一拍的 detail 快照:跳过判定用它(见 shouldSkipRowFetch)。
        const prevDetail = detail.value
        const d = await api.get(id)
        consecutiveFailures = 0
        detail.value = d
        // 行级表格只对已展开的执行随 tick 刷新;放在终态判定之前,
        // 让收敛为终态的那一拍仍拉到最终 rows。T13-Q2:已知终态且已有
        // rows 缓存的执行(终态行级数据不再变化)不再逐秒重拉。
        for (const rid of expanded.value) {
          if (shouldSkipRowFetch(rid, prevDetail)) continue
          await fetchRows(rid)
        }
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
    rowsByExecution,
    expanded,
    artifactText,
    artifactError,
    expandedArtifacts,
    fetchList,
    fetchDetail,
    remove,
    fetchRows,
    fetchArtifact,
    toggleExpanded,
    toggleArtifact,
    startPolling,
    stopPolling,
  }
})