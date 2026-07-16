<!-- Executions.vue — 单次执行的实时状态页 + 报告链接.
     V0.1 用 1s 轮询；WebSocket 实时推送留 V1+. -->
<template>
  <section class="executions" v-if="execStore.detail">
    <header class="page-header">
      <div>
        <h2>执行 #{{ execStore.detail.id }}</h2>
        <p>
          {{ execStore.detail.case_id }} · 状态 {{ statusText }}
          <el-tag
            v-if="stepToLabel"
            type="info"
            size="small"
            class="step-to-pill"
            title="本次执行在 --step-to 模式下运行（仅跑到第 N 步后停止）"
          >执行到第 {{ stepToLabel }} 步</el-tag>
        </p>
      </div>
      <div class="header-actions">
        <span :class="['status-tag', `status-${execStore.detail.status}`]">
          {{ statusText }}
        </span>
        <el-button link @click="refreshNow">手动刷新</el-button>
        <el-button link type="danger" @click="removeExec">删除</el-button>
      </div>
    </header>

    <div class="counters">
      <div class="counter">
        <div class="counter-label">总执行</div>
        <div class="counter-value">{{ execStore.detail.total_runs }}</div>
      </div>
      <div class="counter ok">
        <div class="counter-label">通过</div>
        <div class="counter-value">{{ execStore.detail.passed }}</div>
      </div>
      <div class="counter fail">
        <div class="counter-label">失败</div>
        <div class="counter-value">{{ execStore.detail.failed }}</div>
      </div>
      <div class="counter">
        <div class="counter-label">未开始</div>
        <div class="counter-value">{{
          Math.max(0, execStore.detail.total_runs - execStore.detail.passed - execStore.detail.failed)
        }}</div>
      </div>
    </div>

    <h3 class="runs-title">运行明细</h3>
    <el-table
      :data="execStore.detail.runs"
      class="runs-table"
      :default-sort="{ prop: 'id', order: 'descending' }"
    >
      <el-table-column label="#" prop="idx" width="60" sortable />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <span :class="['run-tag', `run-${row.status}`]">{{ statusLabel(row.status) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="exit" width="70">
        <template #default="{ row }">
          <code :class="['mono', exitClass(row.exit_code)]">{{ row.exit_code ?? '—' }}</code>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="90">
        <template #default="{ row }">
          <span class="mono">{{ row.duration_ms != null ? `${row.duration_ms}ms` : '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="开始时间" width="160">
        <template #default="{ row }">
          <span class="mono dim">{{ row.started_at?.slice(11, 19) || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="报告" min-width="280" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            link
            type="primary"
            :disabled="!row.report_path"
            @click="openReport(row)"
          >查看报告</el-button>
          <el-button
            link
            :type="isSelectedForLog(row) ? 'primary' : undefined"
            @click="toggleLog(row)"
          >{{ isSelectedForLog(row) ? '收起日志' : '查看日志' }}</el-button>
          <el-button link @click="rerunRun(row)" :loading="row.rerunning">重跑</el-button>
          <el-button link type="danger" @click="deleteRun(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 日志面板：与执行详情同级，行内展开（替代原来的 el-dialog）。
         点行尾的「查看日志」按钮展开，再点一次（或点面板右上角「收起」）
         即折叠。流式 SSE 与原弹窗一致；只是布局从浮层改为页面内嵌。 -->
    <section v-if="logRow" class="log-panel" aria-live="polite">
      <header class="log-panel-head">
        <div class="log-panel-title">
          <span :class="['run-tag', `run-${logRow.status}`]">
            {{ runStatusLabel(logRow.status) }}
          </span>
          <span class="log-panel-id">
            run #{{ logRow.idx }}
            · exit {{ logRow.exit_code ?? '—' }}
            · {{ logRow.duration_ms != null ? `${logRow.duration_ms}ms` : '—' }}
          </span>
          <span v-if="logLoading" class="log-panel-loading">连接中…</span>
          <span v-else-if="logStreamClosed" class="log-panel-done">已结束</span>
        </div>
        <div class="log-panel-actions">
          <el-button
            v-if="logRow.report_path"
            link
            type="primary"
            @click="openReport(logRow)"
          >查看 HTML 报告 →</el-button>
          <el-button link @click="toggleLog(logRow)">收起</el-button>
        </div>
      </header>

      <section class="log-section">
        <h4 class="log-section-title">
          <span class="log-section-bullet" aria-hidden="true">$</span>
          命令行
        </h4>
        <pre class="log-pre log-cmd">{{ logRow.command_line || '(尚未记录)' }}</pre>
      </section>

      <section class="log-section">
        <h4 class="log-section-title">
          <span class="log-section-bullet" aria-hidden="true">›</span>
          stdout
        </h4>
        <pre ref="stdoutRef" class="log-pre log-stdout">{{ logStdout }}</pre>
      </section>

      <section v-if="logStderr" class="log-section">
        <h4 class="log-section-title">
          <span class="log-section-bullet" aria-hidden="true">!</span>
          stderr
        </h4>
        <pre class="log-pre log-stderr">{{ logStderr }}</pre>
      </section>
    </section>

    <!-- 报告嵌入弹窗 -->
    <el-dialog
      v-model="reportOpen"
      :title="`报告 #${reportIdx}`"
      width="90%"
      top="5vh"
      :close-on-click-modal="false"
    >
      <iframe
        v-if="reportOpen"
        :src="reportSrc"
        class="report-frame"
      ></iframe>
    </el-dialog>

    <!-- 删除确认 -->
    <el-dialog
      v-model="deleteOpen"
      title="⚠ 删除 run"
      width="420px"
    >
      <p>确认删除 run #{{ deleteTarget?.idx }} 的记录？<br>
      <span class="muted">仅删除数据库行 + 报告文件，execution 计数器不变。</span></p>
      <template #footer>
        <el-button @click="deleteOpen = false">取消</el-button>
        <el-button type="danger" :loading="deleteSubmitting" @click="confirmDeleteRun">确认</el-button>
      </template>
    </el-dialog>
  </section>

  <section v-else class="state loading-state">
    <el-skeleton :rows="5" animated />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElNotification } from 'element-plus'
import { useExecutionsStore } from '@/stores/executions'
import { useAuthStore } from '@/stores/auth'
import {
  reportUrl,
  rerunRun as apiRerun,
  deleteRun as apiDeleteRun,
  getRunLog,
  openRunLogStream,
  type LogStream,
} from '@/api/executions'
import type { ExecRun } from '@/api/executions'

const route = useRoute()
const router = useRouter()
const execStore = useExecutionsStore()

const executionId = computed(() => Number(route.params.id))

// Status labels.  Execution has its own status vocabulary
// (queued / running / done / failed); ExecRun reuses a near-identical
// set with "pending" / "passed" instead.  One map per surface, both
// rendered through the same lookup helper.
const EXEC_LABELS: Record<string, string> = {
  queued: '排队', running: '运行中', done: '完成', failed: '失败',
}
const RUN_LABELS: Record<string, string> = {
  pending: '排队', running: '运行中', passed: '通过', failed: '失败',
}
const statusText = computed(() => {
  const s = execStore.detail?.status
  return s ? (EXEC_LABELS[s] ?? s) : ''
})
function statusLabel(s: string): string {
  return RUN_LABELS[s] ?? s
}

// ``step_to`` is a 0-based inclusive halt index stored in
// Execution.config_json by the create endpoint.  Display as
// 1-based "执行到第 N 步" only when the field is present and non-null
// (legacy rows without the key render exactly as before — no pill).
const stepToLabel = computed(() => {
  const v = execStore.detail?.config?.step_to
  if (v === null || v === undefined) return ''
  const n = Number(v)
  if (!Number.isFinite(n) || n < 0) return ''
  return String(Math.floor(n) + 1)
})

function exitClass(code: number | null): string {
  if (code === null) return ''
  return code === 0 ? 'exit-ok' : 'exit-fail'
}

// ── report dialog ─────────────────────────────────────────
const reportOpen = ref(false)
const reportIdx = ref(0)
const reportSrc = ref('')

function openReport(row: ExecRun) {
  if (!row.report_path || !execStore.detail) return
  reportIdx.value = row.idx
  reportSrc.value = reportUrl(execStore.detail.id, row.idx)
  reportOpen.value = true
}

// ── log panel (inline, same level as execution detail) ────
// 只存 run id,通过下面的 computed ``logRow`` 从 ``detail.runs`` 派生当前行。
// 之前这里直接 ``logTarget = ref<ExecRun | null>`` 缓存 row 引用,
// 1s 轮询把 ``detail.value`` 整体替换后,``logTarget`` 仍指向第一次点击时的
// 旧对象,导致 ``command_line`` 等字段一直停留在 null,
// 模板渲染为 "(尚未记录)"。改用 id + computed 后,轮询刷新会自动重算。
const logTargetId = ref<number | null>(null)
const logRow = computed<ExecRun | null>(() => {
  const id = logTargetId.value
  if (id === null || !execStore.detail) return null
  return execStore.detail.runs.find((r) => r.id === id) ?? null
})
const logStdout = ref('')
const logStderr = ref('')
const logLoading = ref(false)
const logStreamClosed = ref(false)
// Reference to the stdout <pre> so we can auto-scroll as new lines arrive.
const stdoutRef = ref<HTMLPreElement | null>(null)
// We don't have a separate stream for stderr right now; the SSE frames
// arrive tagged with their kind and we route them into the matching ref.
const logStream = ref<LogStream | null>(null)
const authStore = useAuthStore()

function runStatusLabel(s: string): string {
  return statusLabel(s)
}

/** True when the row is the one currently displayed in the inline panel. */
function isSelectedForLog(row: ExecRun): boolean {
  return logTargetId.value === row.id
}

/** Toggle the inline log panel: open if closed or showing a different
 *  run; collapse if the user clicks the same run again. */
function toggleLog(row: ExecRun) {
  if (isSelectedForLog(row)) {
    collapseLog()
    return
  }
  startLog(row)
}

function collapseLog() {
  logStream.value?.close()
  logStream.value = null
  logTargetId.value = null
  logStdout.value = ''
  logStderr.value = ''
  logLoading.value = false
  logStreamClosed.value = false
}

async function startLog(row: ExecRun) {
  if (!execStore.detail) return
  // Switching to a different run — close the prior stream first.
  logStream.value?.close()
  logTargetId.value = row.id
  logStdout.value = ''
  logStderr.value = ''
  logLoading.value = true
  logStreamClosed.value = false
  try {
    // Open the SSE stream first — it will replay any history (sourced
    // from disk if the run already finished) before yielding new lines.
    const stream = await openRunLogStream(
      execStore.detail.id,
      row.id,
      authStore.accessToken,
    )
    logStream.value = stream
    drainStreamInBackground(row, stream)
  } catch (e) {
    logLoading.value = false
    logStreamClosed.value = true
    const err = e as { msg?: string; message?: string }
    logStderr.value = err.msg || err.message || '读取日志失败'
  }
}

/** Drain the SSE stream's events into the panel's refs.  Never throws
 *  — falls back to the legacy ``getRunLog`` endpoint if SSE fails so
 *  the user always sees something. */
async function drainStreamInBackground(row: ExecRun, stream: LogStream): Promise<void> {
  try {
    for (;;) {
      const event = await stream.next()
      if (event === null) {
        // Stream closed without an end event.  Try to reconnect using
        // the last delivered seq so we resume from where we left off
        // instead of re-fetching the whole log.
        try {
          const lastSeq = stream.lastSeq()
          stream.close()
          if (!execStore.detail) break
          const resumed = await openRunLogStream(
            execStore.detail.id,
            row.id,
            authStore.accessToken,
            { lastEventId: lastSeq },
          )
          logStream.value = resumed
          // Tail-call: continue consuming from the resumed stream.
          await drainStreamInBackground(row, resumed)
          return
        } catch {
          break
        }
      }
      if (event.kind === 'end') {
        // Backfill exit_code into the row so the header pill flips from
        // "exit —" to "exit <code>" without waiting for a refetch.
        // ``logRow`` 是从 ``detail.runs`` 派生的 computed,直接 mutate 它,
        // 触发依赖它的模板/计算属性重算。
        if (logRow.value) {
          logRow.value.exit_code = event.exit_code
        }
        logStreamClosed.value = true
        break
      }
      if (event.kind === 'stderr') logStderr.value += event.text
      else logStdout.value += event.text
      autoScrollStdout()
    }
  } catch {
    // Stream aborted or transient error — fall back to legacy fetch.
  } finally {
    logLoading.value = false
    await fetchLegacyFullLog(row)
  }
}

async function fetchLegacyFullLog(row: ExecRun) {
  if (!execStore.detail) return
  try {
    const text = await getRunLog(execStore.detail.id, row.id)
    if (text.startsWith('# gimbal run log')) {
      const sections = text.split(/^===== /m).filter(Boolean)
      let stdoutBuf = ''
      let stderrBuf = ''
      for (const s of sections) {
        if (s.startsWith('STDOUT =====\n')) {
          stdoutBuf = s.replace(/^STDOUT =====\n/, '')
        } else if (s.startsWith('STDERR =====\n')) {
          stderrBuf = s.replace(/^STDERR =====\n/, '')
        }
      }
      logStdout.value = stdoutBuf || logStdout.value
      logStderr.value = stderrBuf || logStderr.value
    }
  } catch {
    // best-effort; ignore
  }
}

/** Pin the stdout panel to the bottom on every new chunk.  Cheap
 *  (single ``scrollTop = scrollHeight``) and only runs while the panel
 *  is mounted. */
function autoScrollStdout() {
  const el = stdoutRef.value
  if (!el) return
  // Defer one microtask so the v-model has flushed the new text
  // before we measure.
  Promise.resolve().then(() => {
    el.scrollTop = el.scrollHeight
  })
}

// ── per-run actions ────────────────────────────────────────
const deleteOpen = ref(false)
const deleteTarget = ref<ExecRun | null>(null)
const deleteSubmitting = ref(false)

function deleteRun(row: ExecRun) {
  deleteTarget.value = row
  deleteOpen.value = true
}

async function confirmDeleteRun() {
  if (!deleteTarget.value || !execStore.detail) return
  deleteSubmitting.value = true
  try {
    const removed = deleteTarget.value
    await apiDeleteRun(execStore.detail.id, removed.id)
    // Optimistic remove — row disappears immediately + counters
    // decrement in the header.  Background fetchDetail keeps the
    // canonical state in sync for concurrent operators.
    execStore.removeRun(removed.id)
    deleteOpen.value = false
    void execStore.fetchDetail(execStore.detail.id)
    ElMessage.success(`run #${removed.idx} 已删除`)
  } catch {
    ElMessage.error('删除失败')
  } finally {
    deleteSubmitting.value = false
  }
}

async function rerunRun(row: ExecRun) {
  if (!execStore.detail) return
  row.rerunning = true
  try {
    // POST /rerun blocks server-side until the subprocess finishes; the
    // returned ExecRunOut already has the post-subprocess state.
    const newRun = await apiRerun(execStore.detail.id, row.id)
    // Optimistic append — the new row appears in the table
    // immediately without waiting for a full fetchDetail roundtrip.
    // The ElTable's :default-sort by id desc puts it at the top.
    execStore.appendRun(newRun)
    // Background sync so subsequent polls / counters stay consistent
    // (catches any side-effect updates from concurrent reruns or
    // other operators hitting the same execution).
    void execStore.fetchDetail(execStore.detail.id)
    ElNotification.success({
      title: '重跑完成',
      message: `新 run #${newRun.idx} (id=${newRun.id}) 已生成 · exit=${newRun.exit_code ?? '—'}`,
      duration: 4500,
    })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '重跑失败')
  } finally {
    row.rerunning = false
  }
}

// ── lifecycle ─────────────────────────────────────────────
let stop: (() => void) | null = null

async function refreshNow() {
  if (executionId.value) await execStore.fetchDetail(executionId.value)
}

async function removeExec() {
  if (!execStore.detail) return
  await execStore.remove(execStore.detail.id)
  ElMessage.success('已删除')
  router.push('/executions')
}

onMounted(async () => {
  if (!executionId.value) return
  await execStore.fetchDetail(executionId.value)
  stop = execStore.startPolling(executionId.value)
})

onUnmounted(() => {
  if (stop) stop()
  // Tear down any live SSE stream so the backend subscriber is freed.
  collapseLog()
})
</script>

<style scoped>
.executions {
  max-width: 1480px;
  padding: 28px 32px 48px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.page-header h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 22px;
  line-height: 1.25;
}

.page-header p {
  margin: 5px 0 0;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.step-to-pill {
  margin-left: 8px;
  vertical-align: middle;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.status-tag {
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 4px;
}

.status-queued {
  color: #4338ca;
  background: #eef2ff;
}

.status-running {
  color: #854d0e;
  background: #fef9c3;
}

.status-done {
  color: #166534;
  background: #dcfce7;
}

.status-failed {
  color: #991b1b;
  background: #fee2e2;
}

.counters {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.counter {
  padding: 16px;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 8px;
}

.counter-label {
  color: #64748b;
  font-size: 11px;
}

.counter-value {
  margin-top: 6px;
  color: var(--color-text-primary);
  font-size: 24px;
  font-weight: 700;
}

.counter.ok .counter-value {
  color: #166534;
}

.counter.fail .counter-value {
  color: #991b1b;
}

.runs-title {
  margin: 0 0 12px;
  color: var(--color-text-primary);
  font-size: 14px;
}

.runs-table {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.run-tag {
  display: inline-flex;
  padding: 2px 8px;
  font-size: 10.5px;
  font-weight: 600;
  border-radius: 4px;
}

.run-pending {
  color: #4338ca;
  background: #eef2ff;
}

.run-running {
  color: #854d0e;
  background: #fef9c3;
}

.run-passed {
  color: #166534;
  background: #dcfce7;
}

.run-failed {
  color: #991b1b;
  background: #fee2e2;
}

.mono {
  font-family: var(--font-mono);
}

.dim {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.muted {
  color: var(--color-text-tertiary);
  font-size: 11px;
}

.exit-ok {
  color: #166534;
  font-weight: 600;
}

.exit-fail {
  color: #991b1b;
  font-weight: 600;
}

.report-link {
  color: var(--accent);
  font-size: 12px;
  text-decoration: none;
}

.report-link:hover {
  text-decoration: underline;
}

.report-frame {
  width: 100%;
  height: 75vh;
  border: 0.5px solid #e2e8f0;
  border-radius: 4px;
}

.state {
  max-width: 720px;
  padding: 80px 20px;
  margin: 0 auto;
}

/* ─── Inline log panel (same level as execution detail) ───
   Lives directly below the runs table.  Fixed-height scrollable
   stdout so the panel doesn't grow unbounded as lines stream in. */
.log-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px 18px;
  margin-top: 16px;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 8px;
}

.log-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 0.5px solid var(--color-border-tertiary);
}

.log-panel-title {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--color-text-primary);
  font-size: 13px;
}

.log-panel-id {
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 11px;
}

.log-panel-loading {
  color: var(--color-text-secondary);
  font-size: 10.5px;
  font-style: italic;
}

.log-panel-done {
  padding: 1px 8px;
  color: #166534;
  font-size: 10.5px;
  font-weight: 600;
  background: #dcfce7;
  border-radius: 4px;
}

.log-panel-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.log-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.log-section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.6px;
  text-transform: uppercase;
}

.log-section-bullet {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  color: white;
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--color-text-secondary);
  border-radius: 3px;
}

.log-pre {
  margin: 0;
  padding: 10px 12px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  border-radius: 6px;
}

.log-cmd {
  color: #4338ca;
  background: var(--accent-soft);
  border: 1px solid var(--accent-soft-border);
}

.log-stdout {
  max-height: 320px;
  color: #1f2933;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  overflow: auto;
}

.log-stderr {
  max-height: 240px;
  color: #991b1b;
  background: #fef2f2;
  border: 1px solid #fecaca;
  overflow: auto;
}
</style>