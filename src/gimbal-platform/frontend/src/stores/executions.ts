/**
 * executions.ts — Pinia store + SSE 事件流实时状态(P2-06/C9)。
 *
 * The store proxies /api/executions/* and exposes a `startPolling(id)`
 * helper(历史名保留,实现已换 SSE):订阅 `/events/stream` 事件流,
 * 事件帧驱动 detail/rows 刷新(300ms 节流合并突发),`done` 帧终收敛;
 * 断线带 Last-Event-ID 自动重连(不重复不丢失),404/连续失败回落
 * pollError 文案。不再有 1s 定时轮询。
 *
 * T13 行级可观测(spec §9.1):rows 只对「已展开」的执行随刷新拉取
 * (避免列表 N+1);engine-log/result 工件按需拉取,不参与流刷新。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/executions'
import type { Execution, ExecutionListItem, ExecutionRow } from '@/api/executions'
import { executionEventsStreamUrl } from '@/api/executions'
import { httpStatusOf } from '@/api/http'
import { isTerminalExecutionStatus } from '@/utils/executionStatus'
import { useAuthStore } from '@/stores/auth'

const REFRESH_THROTTLE_MS = 300
const RECONNECT_DELAY_MS = 1000
const MAX_RECONNECTS = 10
/** 兜底轮询间隔:SSE 是主刷新通道,但断流/静默失败时保底(见 startPolling) */
const FALLBACK_POLL_MS = 3000

export const useExecutionsStore = defineStore('executions', () => {
  const list = ref<ExecutionListItem[]>([])
  /** 筛选后的总数(执行记录页筛选行显示;fetchList 不筛时 = list.length 对应总数) */
  const total = ref(0)
  const detail = ref<Execution | null>(null)
  const loading = ref(false)
  const lastError = ref('')
  /** Set when the event stream gives up (404 / repeated failures). */
  const pollError = ref('')
  let streamAbort: AbortController | null = null
  let refreshTimer: ReturnType<typeof setTimeout> | null = null
  let lastSeq = 0
  let reconnects = 0

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
      // 404 分支:caseDir 是软引用,可能因工件清扫(CASE_RETENTION_DAYS=14)
      // 或 server 链部分工件不在 case 目录。人话提示而非死链 404;
      // 具体原因前端无法区分,统一为「不可用」并注明常见原因。
      if (httpStatusOf(e) === 404) {
        artifactError.value = {
          ...artifactError.value,
          [key]: '该工件当前不可用(可能已被过期清扫或该执行链不产此工件)',
        }
        return
      }
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

  async function fetchList(): Promise<ExecutionListItem[]> {
    loading.value = true
    try {
      const r = await api.listExecutions()
      list.value = r.items
      total.value = r.total
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
    if (detail.value?.id === id) {
      detail.value = null
      stopPolling()   // 在轮询对象被删:停流(服务端 404 之外的主动收口)
    }
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
   * SSE 订阅 `/events/stream`(P2-06/C9,历史名 startPolling 保留):
   * 事件帧 → 300ms 节流刷新 detail + 已展开 rows;done 帧 → 终收敛
   * 后关流;断线带 Last-Event-ID 重连。返回停止函数(卸载时调用)。
   *
   * 兜底轮询:SSE 是唯一刷新通道时存在单点故障(代理断流/token 过期/
   * 静默失败 → 状态永远停在 running)。加一个 3s 定时器,非终态时无论
   * SSE 是否活着都拉一次 detail;终态后自动停止。SSE 正常时它是多余的
   * 一次 GET(同数据幂等覆盖),SSE 挂了它就是唯一的生命线。
   */
  let fallbackTimer: ReturnType<typeof setInterval> | null = null

  function _startFallback(id: number): void {
    _stopFallback()
    fallbackTimer = setInterval(() => {
      const st = detail.value?.status
      if (!st || isTerminalExecutionStatus(st)) {
        _stopFallback()
        return
      }
      void _refreshOnce(id).catch(() => { /* 静默:下拍再试 */ })
    }, FALLBACK_POLL_MS)
  }

  function _stopFallback(): void {
    if (fallbackTimer !== null) {
      clearInterval(fallbackTimer)
      fallbackTimer = null
    }
  }

  function startPolling(id: number): () => void {
    stopPolling()
    pollError.value = ''
    lastSeq = 0
    reconnects = 0
    // 流建立前先拉一次基线(终态执行也有一拍完整视图)
    void _refreshOnce(id).catch(() => { /* 基线失败留给流帧重试 */ })
    void _pump(id)
    // 兜底:SSE 断流/静默失败时仍能感知终态(3s 一拍,终态即停)
    _startFallback(id)
    return stopPolling
  }

  /** 单拍刷新:detail + 已展开 rows(终态且已有缓存跳过,T13-Q2)。 */
  async function _refreshOnce(id: number): Promise<Execution> {
    const prevDetail = detail.value
    const d = await api.get(id)
    detail.value = d
    for (const rid of expanded.value) {
      if (shouldSkipRowFetch(rid, prevDetail)) continue
      await fetchRows(rid)
    }
    return d
  }

  /** 突发事件帧合并为 ≤1/300ms 的刷新(尾沿保证最后一帧必刷)。 */
  function _scheduleRefresh(id: number): void {
    if (refreshTimer !== null) return
    refreshTimer = setTimeout(() => {
      refreshTimer = null
      void _refreshOnce(id).catch(() => { /* 单帧失败,留给下一帧 */ })
    }, REFRESH_THROTTLE_MS)
  }

  /** SSE 帧 → {id, event, data}(注释/心跳帧返回 null)。 */
  function _parseFrame(frame: string): { id?: string; event?: string; data?: string } | null {
    const out: { id?: string; event?: string; data?: string } = {}
    for (const raw of frame.split('\n')) {
      const line = raw.replace(/\r$/, '')
      if (!line || line.startsWith(':')) continue
      if (line.startsWith('id:')) out.id = line.slice(3).trim()
      else if (line.startsWith('event:')) out.event = line.slice(6).trim()
      else if (line.startsWith('data:')) out.data = line.slice(5).trim()
    }
    return out.id || out.event || out.data ? out : null
  }

  async function _pump(id: number): Promise<void> {
    const auth = useAuthStore()
    const headers: Record<string, string> = {
      Authorization: `Bearer ${auth.accessToken}`,
    }
    if (lastSeq > 0) headers['Last-Event-ID'] = String(lastSeq)
    const ctrl = new AbortController()
    streamAbort = ctrl
    try {
      const resp = await fetch(executionEventsStreamUrl(id), {
        headers, signal: ctrl.signal,
      })
      if (resp.status === 404) {
        detail.value = null
        pollError.value = '该执行记录已不存在（可能已被删除）'
        return
      }
      if (!resp.ok || !resp.body) {
        throw Object.assign(new Error(`stream ${resp.status}`), { status: resp.status })
      }
      reconnects = 0
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        let sep = buf.indexOf('\n\n')
        while (sep >= 0) {
          const frame = _parseFrame(buf.slice(0, sep))
          buf = buf.slice(sep + 2)
          sep = buf.indexOf('\n\n')
          if (!frame) continue
          if (frame.id) lastSeq = Math.max(lastSeq, Number(frame.id) || 0)
          if (frame.event === 'done') {
            await _refreshOnce(id).catch(() => { /* 终收敛尽力 */ })
            return
          }
          if (frame.data !== undefined) _scheduleRefresh(id)
        }
      }
      // 服务端关流但执行未终态(如网关空闲断链)→ 走重连路径
      if (!isTerminalExecutionStatus(detail.value?.status ?? '')) {
        throw new Error('stream closed before terminal')
      }
    } catch (e) {
      if (ctrl.signal.aborted) return
      const status = (e as { status?: number }).status ?? httpStatusOf(e)
      if (status === 404) {
        detail.value = null
        pollError.value = '该执行记录已不存在（可能已被删除）'
        return
      }
      reconnects += 1
      if (reconnects <= MAX_RECONNECTS) {
        await new Promise((r) => setTimeout(r, RECONNECT_DELAY_MS))
        return _pump(id)
      }
      pollError.value = '事件流连接失败，已停止刷新 — 请手动刷新重试'
    }
  }

  function stopPolling() {
    if (streamAbort !== null) {
      streamAbort.abort()
      streamAbort = null
    }
    if (refreshTimer !== null) {
      clearTimeout(refreshTimer)
      refreshTimer = null
    }
    _stopFallback()
  }

  return {
    list,
    total,
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