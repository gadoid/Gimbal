/** executions.ts — typed wrappers around /api/executions/* endpoints. */
import http from './http'

export type MergePolicy = 'override' | 'merge' | 'append'
export type ExecutionStatus = 'queued' | 'running' | 'done' | 'failed'
export type RunStatus = 'pending' | 'running' | 'passed' | 'failed'

export interface Execution {
  id: number
  case_id: string
  status: ExecutionStatus
  total_runs: number
  passed: number
  failed: number
  started_at: string | null
  finished_at: string | null
  config: {
    n_runs?: number
    parallel?: number
    env?: string
    prefix?: string | null
    exec_auth_alias?: string[]
    merge_policy?: MergePolicy
  }
}

export interface ExecRun {
  id: number
  idx: number
  status: RunStatus
  exit_code: number | null
  report_path: string | null
  log_path: string | null
  // 后端在 _run_one 子进程启动后才写入;前端用 computed 派生最新值,
  // 避免在轮询替换 detail.runs 时仍指向孤立的旧 row 对象。
  command_line: string | null
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
}

export interface ExecutionDetail extends Execution {
  runs: ExecRun[]
}

export interface ExecutionCreateIn {
  case_id: string
  n_runs: number
  parallel: number
  env: string
  prefix?: string
  exec_auth_alias?: string[]
  merge_policy?: MergePolicy
  /** When false, skip credential injection entirely: ``Config.users`` in
   *  the rendered yaml is left exactly as the case yaml defines it (the
   *  UI calls this state "origin").  Backend default is true so legacy
   *  clients sending only ``merge_policy`` keep working. */
  inject_credentials?: boolean
  /** Admin-only: replace the executor's default ``gimbal run launch <yaml>``
   *  argv.  Each list element is one argv entry.  Server rejects with 403 if
   *  the caller isn't an admin.  ``undefined`` → use the default command. */
  command_line?: string[]
}

export function list() {
  return http
    .get<{ items: Execution[]; total: number }>('/executions')
    .then((r) => r.data)
}

export function get(id: number) {
  return http.get<ExecutionDetail>(`/executions/${id}`).then((r) => r.data)
}

export function create(payload: ExecutionCreateIn) {
  return http.post<Execution>('/executions', payload).then((r) => r.data)
}

export function remove(id: number) {
  return http.delete(`/executions/${id}`).then(() => undefined)
}

export function reportUrl(id: number, idx: number): string {
  // Same-origin so the browser can load it inside Executions page.
  return `/api/executions/${id}/report/${idx}`
}

export function rerunRun(executionId: number, runId: number) {
  return http
    .post<ExecRun>(`/executions/${executionId}/runs/${runId}/rerun`)
    .then((r) => r.data)
}

export function deleteRun(executionId: number, runId: number) {
  return http.delete(`/executions/${executionId}/runs/${runId}`).then(() => undefined)
}

/** Fetch the run's CLI + stdout + stderr log as plain text.
 *  Returns a *relative* path — axios's baseURL (`/api`) is prepended at
 *  request time, so we MUST NOT include `/api` here (would yield
 *  `/api/api/executions/.../log` and 404).  `reportUrl` is the converse:
 *  the iframe reads it directly so it needs the absolute path. */
export function runLogUrl(executionId: number, runId: number): string {
  return `/executions/${executionId}/runs/${runId}/log`
}

export function getRunLog(executionId: number, runId: number) {
  return http
    .get<string>(runLogUrl(executionId, runId), { responseType: 'text' })
    .then((r) => r.data)
}

/** Open an SSE stream for the run's log lines.
 *
 *  Wraps a `fetch()` + `ReadableStream` so we can send the JWT via
 *  `Authorization` header (the native `EventSource` API does NOT support
 *  custom headers; token-in-query is rejected by the security review).
 *
 *  Each call to `next()` returns either:
 *   - a chunk tagged with its kind (``stdout`` or ``stderr``)
 *   - an ``end`` event with the subprocess exit code
 *   - `null` once the underlying byte stream is closed (e.g. server
 *     restart) without an explicit ``end`` event — caller may try to
 *     reconnect via the cursor in `lastSeq`.
 *
 *  ``lastSeq`` is updated after every successful chunk read so the
 *  caller can pass it as the ``Last-Event-ID`` header on reconnect.
 */
export type LogStreamEvent =
  | { kind: 'stdout' | 'stderr'; text: string }
  | { kind: 'end'; exit_code: number }

export interface LogStream {
  next(): Promise<LogStreamEvent | null>
  /** Monotonically increasing sequence of the last delivered chunk. */
  lastSeq(): number
  close(): void
}

export async function openRunLogStream(
  executionId: number,
  runId: number,
  token: string,
  opts: { lastEventId?: number } = {},
): Promise<LogStream> {
  const controller = new AbortController()
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    Authorization: `Bearer ${token}`,
  }
  if (typeof opts.lastEventId === 'number' && opts.lastEventId > 0) {
    headers['Last-Event-ID'] = String(opts.lastEventId)
  }
  const resp = await fetch(`/api/executions/${executionId}/runs/${runId}/log/stream`, {
    headers,
    signal: controller.signal,
  })
  if (!resp.ok) {
    throw new Error(`SSE connect failed: HTTP ${resp.status}`)
  }
  const reader = resp.body!.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let lastDeliveredSeq = 0

  // Parse SSE frames from the raw byte stream.  Each frame is one or
  // more ``event: <name>`` + ``id: <seq>`` + ``data: <json>`` lines
  // terminated by a blank line.  Heartbeats are comment lines starting
  // with ``:``.  The ``id:`` line is what makes Last-Event-ID resume work.
  function pullFrame(): { event: string; id: string; data: string } | null {
    const nl = buffer.indexOf('\n\n')
    if (nl === -1) return null
    const frame = buffer.slice(0, nl)
    buffer = buffer.slice(nl + 2)
    let eventName = ''
    let idStr = ''
    const dataLines: string[] = []
    for (const line of frame.split('\n')) {
      if (line.startsWith(':')) continue
      if (line.startsWith('event:')) eventName = line.slice(6).trim()
      else if (line.startsWith('id:')) idStr = line.slice(3).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
    }
    return { event: eventName, id: idStr, data: dataLines.join('\n') }
  }

  return {
    async next(): Promise<LogStreamEvent | null> {
      for (;;) {
        const frame = pullFrame()
        if (frame !== null) {
          if (frame.data === '') continue
          if (frame.event === 'end') {
            try {
              const payload = JSON.parse(frame.data) as { exit_code?: number }
              return { kind: 'end', exit_code: payload.exit_code ?? 0 }
            } catch {
              return { kind: 'end', exit_code: 0 }
            }
          }
          try {
            const payload = JSON.parse(frame.data) as { text?: string; seq?: number }
            if (typeof payload.text === 'string') {
              // Update cursor using the server's seq if present, else
              // the frame id, else leave unchanged.
              const seq =
                typeof payload.seq === 'number'
                  ? payload.seq
                  : frame.id
                  ? Number(frame.id)
                  : lastDeliveredSeq
              if (Number.isFinite(seq) && seq > 0) lastDeliveredSeq = seq
              return {
                kind: frame.event === 'stderr' ? 'stderr' : 'stdout',
                text: payload.text,
              }
            }
          } catch {
            return { kind: 'stdout', text: frame.data }
          }
          continue
        }
        const { done, value } = await reader.read()
        if (done) return null
        buffer += decoder.decode(value, { stream: true })
      }
    },
    lastSeq(): number {
      return lastDeliveredSeq
    },
    close(): void {
      controller.abort()
    },
  }
}