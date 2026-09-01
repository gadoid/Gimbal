<!-- Executions.vue — 单次执行的实时状态页（V3）。
     可观测面 = Execution 计数器 + 执行信息 + 行级明细表（展开后随
     1s 轮询刷新；engine.log / result.json 工件按需加载）。
     V1 的每-run 报告/SSE 已退役。 -->
<template>
  <section class="executions" v-if="execStore.detail">
    <!-- Poller gave up (failure budget) while the last detail snapshot
         stays rendered — tell the user the data may be stale. -->
    <el-alert
      v-if="execStore.pollError"
      :title="execStore.pollError"
      type="warning"
      :closable="false"
      show-icon
      class="poll-warn"
    />
    <header class="page-header">
      <div>
        <h2>执行 #{{ execStore.detail.id }}</h2>
        <p>
          {{ execStore.detail.scenario_id }} · 状态 {{ statusText }}
          <template v-if="startedAtLabel"> · 开始 {{ startedAtLabel }}</template>
          <template v-if="finishedAtLabel"> · 结束 {{ finishedAtLabel }}</template>
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
        <el-tooltip
          content="该执行早于快照功能上线，无执行时场景快照"
          :disabled="execStore.detail.has_scenario_snapshot"
          placement="top"
        >
          <span>
            <el-button
              link
              type="primary"
              :disabled="!execStore.detail.has_scenario_snapshot"
              data-testid="exec-export-scenario"
              @click="exportScenario"
            >导出场景</el-button>
          </span>
        </el-tooltip>
        <el-button
          v-if="canCancel"
          link
          type="warning"
          @click="cancelExec"
        >取消</el-button>
        <el-button link @click="refreshNow">手动刷新</el-button>
        <el-button link type="danger" @click="removeExec">删除</el-button>
      </div>
    </header>

    <!-- 系统标记:reconcile 收敛 / 计数器漂移(不进配方 dl)-->
    <el-alert
      v-if="execStore.detail.config?.reconciled"
      type="warning"
      :closable="false"
      show-icon
      class="sys-alert"
      title="后端重启：本单由启动期 reconcile 收敛为 failed（详见执行信息外的 reconciled 记录）"
    />
    <el-alert
      v-if="execStore.detail.config?.counterDrift"
      type="error"
      :closable="false"
      show-icon
      class="sys-alert"
      title="计数器漂移：通过+失败 ≠ 总执行，真值以 data/runs/<date>.jsonl 调度日志为准"
    />

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
      <div class="counter" title="未执行 / 行边界跳过 / 取消未跑的行">
        <div class="counter-label">未完成</div>
        <div class="counter-value">{{
          Math.max(0, execStore.detail.total_runs - execStore.detail.passed - execStore.detail.failed)
        }}</div>
      </div>
    </div>

    <h3 class="recipe-title">执行信息</h3>
    <dl class="recipe">
      <template v-for="([k, label, v]) in recipeEntries" :key="k">
        <dt>{{ label }}</dt>
        <dd class="mono">{{ formatRecipeValue(v) }}</dd>
      </template>
    </dl>

    <h3 class="rows-title">行级明细</h3>
    <div class="rows-head">
      <p class="rows-hint">
        每行 = 数据集 × 行 × 重复（数据驱动场景按数据集展开）；状态随 1s 轮询刷新，引擎日志与步骤明细按需加载。
      </p>
      <el-button
        link
        type="primary"
        :data-testid="`exec-row-${execStore.detail.id}`"
        @click="toggleRows"
      >{{ isExpanded ? '收起行级表格' : '展开行级表格' }}</el-button>
    </div>
    <div v-if="isExpanded" class="rows-panel">
      <p v-if="rowsLoading" class="rows-empty">行级数据加载中…</p>
      <p v-else-if="rows.length === 0" class="rows-empty">
        无行级数据 — 预部署/认证快速失败等未分发行的单不产生行级记录
      </p>
      <table v-else class="ex-table">
        <thead>
          <tr>
            <th>#</th>
            <th>数据集</th>
            <th>行</th>
            <th>重复</th>
            <th>状态</th>
            <th>耗时</th>
            <th>case 目录</th>
            <th>工件</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="row in rows" :key="row.seq">
            <tr class="ex-table-row">
              <td class="mono">{{ row.seq }}</td>
              <td>{{ row.datasetId ?? '使用基线配置' }}</td>
              <td class="mono">{{ row.rowIndex }}</td>
              <td class="mono">{{ row.rep }}</td>
              <td>
                <span :class="['row-tag', rowStatusClass(row.status)]">{{ row.status }}</span>
              </td>
              <td class="mono">{{ rowDuration(row) }}</td>
              <td class="mono dim">{{ row.caseDir || '—' }}</td>
              <td>
                <span class="row-actions">
                  <el-button
                    link
                    type="primary"
                    size="small"
                    :disabled="!row.caseDir"
                    :data-testid="`row-artifact-${row.seq}-engine-log`"
                    @click="toggleArtifact(row, 'engine-log')"
                  >{{ isArtifactShown(row, 'engine-log') ? '收起日志' : '引擎日志' }}</el-button>
                  <el-button
                    link
                    type="primary"
                    size="small"
                    :disabled="!row.caseDir"
                    :data-testid="`row-artifact-${row.seq}-result`"
                    @click="toggleArtifact(row, 'result')"
                  >{{ isArtifactShown(row, 'result') ? '收起明细' : '步骤明细' }}</el-button>
                </span>
              </td>
            </tr>
            <tr
              v-for="a in loadedArtifacts(row)"
              :key="`${row.seq}-${a.file}-artifact`"
              class="ex-table-artifact"
            >
              <td colspan="8">
                <div class="artifact-head">
                  <span>{{ a.file === 'engine-log' ? 'engine.log（引擎日志）' : 'result.json（步骤明细）' }}</span>
                  <span class="mono dim">{{ row.caseDir }}</span>
                </div>
                <pre :class="['artifact-pre', 'mono', { 'artifact-error': a.isError }]">{{ a.content }}</pre>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>

  <section v-else-if="execStore.pollError" class="state error-state">
    <el-alert
      :title="execStore.pollError"
      type="error"
      :closable="false"
      show-icon
    />
    <div class="error-actions">
      <el-button type="primary" @click="refreshNow">重新加载</el-button>
      <el-button @click="router.push('/executions')">返回执行列表</el-button>
    </div>
  </section>

  <section v-else class="state loading-state">
    <el-skeleton :rows="5" animated />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { executionStatusText, isTerminalExecutionStatus } from '@/utils/executionStatus'
import { cancelExecution, getScenarioSnapshot } from '@/api/executions'
import type { ExecutionRow } from '@/api/executions'
import { removeExecution } from '@/utils/removeExecution'
import { showError } from '@/utils/errorFallback'
import { useExecutionsStore } from '@/stores/executions'
import { convertDraftToExecutable } from '@/stores/scenario-draft'
import { downloadFile } from '@/utils/download'
import { exportTimestamp } from '@/utils/datetime'

const route = useRoute()
const router = useRouter()
const execStore = useExecutionsStore()

const executionId = computed(() => Number(route.params.id))

const statusText = computed(() => {
  const s = execStore.detail?.status
  return s ? executionStatusText(s) : ''
})

// P4 协作式取消:queued/running 可取消(running 由在飞 fanout 行边界
// 收敛);终态按钮消失。
const canCancel = computed(() => {
  const s = execStore.detail?.status
  return !!s && !isTerminalExecutionStatus(s)
})

/** 'YYYY-MM-DDTHH:MM:SS' → 'HH:MM:SS'(与列表页同款字符串切片)。 */
function fmtTime(iso: string | null): string {
  return iso ? iso.slice(11, 19) : ''
}

const startedAtLabel = computed(() => fmtTime(execStore.detail?.started_at ?? null))
const finishedAtLabel = computed(() => fmtTime(execStore.detail?.finished_at ?? null))

// ``stepTo`` is a 0-based inclusive halt index stored in
// Execution.config_json by the dispatcher (V3 camelCase).
// Display as 1-based "执行到第 N 步" only when present and non-null.
const stepToLabel = computed(() => {
  const v = execStore.detail?.config?.stepTo
  if (v === null || v === undefined) return ''
  const n = Number(v)
  if (!Number.isFinite(n) || n < 0) return ''
  return String(Math.floor(n) + 1)
})

// V3 dispatcher recipe (config_json) rendered as a definition list —
// the run-level surface lives in the 行级明细 table below.
// 系统键(reconciled/counterDrift)转上方 alert;stepTo 由 pill 表达,
// 均不进 dl。已知键给中文标签,未知键原样。
// T3→T13 配方键迁移(spec §6):新键 serviceBindings/injectedAuths
// 取代 auths/prefix/mergePolicy/injectCredentials/exec_auth_alias;
// 旧键标签保留 — 历史记录的 config_json 仍含旧键,按键驱动渲染保持可读。
const RECIPE_LABELS: Record<string, string> = {
  runId: '运行ID',
  scenarioId: '场景',
  dataSetIds: '数据集',
  envId: '环境',
  // 新配方键(读侧认证列 = injectedAuths,实际注入清单)
  serviceBindings: '服务绑定',
  injectedAuths: '注入凭证',
  // 旧配方键(snake/camel 两种历史拼写都留标签,仅展示用)
  exec_auth_alias: '执行认证',
  execAuthAlias: '执行认证',
  injectCredentials: '凭证注入',
  nRuns: '每行重复',
  parallel: '并发',
  prefix: '提单号前缀',
  mergePolicy: '认证合并',
}
const RECIPE_HIDDEN_KEYS = new Set(['stepTo', 'reconciled', 'counterDrift'])

const recipeEntries = computed<Array<[string, string, unknown]>>(() => {
  const cfg = execStore.detail?.config
  if (!cfg) return []
  return Object.entries(cfg)
    .filter(([k, v]) => v !== undefined && !RECIPE_HIDDEN_KEYS.has(k))
    .map(([k, v]) => [k, RECIPE_LABELS[k] ?? k, v])
})

/** 未配置项(空数组/空对象/null/空串)= 无覆盖 → 场景基线配置生效。 */
function formatRecipeValue(v: unknown): string {
  if (Array.isArray(v)) return v.length ? v.join(', ') : '使用基线配置'
  // serviceBindings 等对象值:紧凑 JSON 保结构可读,不出现 [object Object]
  if (v !== null && typeof v === 'object') {
    return Object.keys(v).length ? JSON.stringify(v) : '使用基线配置'
  }
  if (v === null || v === '') return '使用基线配置'
  return String(v)
}

// ── 行级明细(spec §9.1)───────────────────────────────────
const rows = computed<ExecutionRow[]>(() => execStore.rowsByExecution[executionId.value] ?? [])
const rowsLoading = computed(() => execStore.rowsByExecution[executionId.value] === undefined)
const isExpanded = computed(() => execStore.expanded.has(executionId.value))

function toggleRows(): void {
  if (!execStore.detail) return
  execStore.toggleExpanded(execStore.detail.id)
}

const ARTIFACT_FILES = ['engine-log', 'result'] as const
type ArtifactFile = (typeof ARTIFACT_FILES)[number]

interface RowArtifactView {
  file: ArtifactFile
  content: string
  isError: boolean
}

/** 工件视图展开/收起(展开重拉最新;收起藏视图,缓存留在 store)。 */
function toggleArtifact(row: ExecutionRow, file: ArtifactFile): void {
  execStore.toggleArtifact(executionId.value, row.caseDir, file)
}

function isArtifactShown(row: ExecutionRow, file: ArtifactFile): boolean {
  return execStore.expandedArtifacts.has(`${executionId.value}:${row.caseDir}:${file}`)
}

/** 已展开且已拉取的工件 → 渲染视图(按需拉取,不轮询)。 */
function loadedArtifacts(row: ExecutionRow): RowArtifactView[] {
  const out: RowArtifactView[] = []
  for (const file of ARTIFACT_FILES) {
    const key = `${executionId.value}:${row.caseDir}:${file}`
    if (!isArtifactShown(row, file)) continue
    const err = execStore.artifactError[key]
    if (err !== undefined) {
      out.push({ file, content: err, isError: true })
      continue
    }
    const text = execStore.artifactText[key]
    if (text !== undefined) {
      out.push({ file, content: text === '' ? '(空)' : prettyArtifact(file, text), isError: false })
    }
  }
  return out
}

/** result.json 是 P1 证据字典(launchStatus/status/…),形状不定:
 *  能 parse 就缩进 pretty-print,不能就原样展示,绝不假设结构。 */
function prettyArtifact(file: ArtifactFile, text: string): string {
  if (file !== 'result') return text
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

/** 行耗时 = finishedAt − startedAt;两者齐备才算,否则 '—'
 *  (T15 起 final 行 ts = 完成时刻,新单回放时长真实;修正前的存量
 *  调度日志行 finishedAt ≈ startedAt,直显 0ms,不过度设计)。 */
function rowDuration(row: ExecutionRow): string {
  if (!row.startedAt || !row.finishedAt) return '—'
  const ms = Date.parse(row.finishedAt) - Date.parse(row.startedAt)
  if (!Number.isFinite(ms) || ms < 0) return '—'
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

// 行级状态词汇来自 dispatcher/引擎(queued/dispatched/…
// /launch_timeout 等),与 Execution 状态集部分重叠:语义对得上的
// 复用既有配色桶;状态串原样透传(不翻译),表外词汇套中性兜底色。
const ROW_STATUS_CLASS: Record<string, string> = {
  queued: 'status-queued',
  dispatched: 'status-running',
  passed: 'status-done',
  failed: 'status-failed',
  canceled: 'status-canceled',
  gimbal_rejected: 'status-failed',
  plate_unavailable: 'status-failed',
  plate_rejected: 'status-failed',
  launch_timeout: 'status-failed',
  launch_error: 'status-failed',
  dispatcher_error: 'status-failed',
}

function rowStatusClass(s: string): string {
  return ROW_STATUS_CLASS[s] ?? 'row-status-other'
}

function refreshRowsIfExpanded(): void {
  if (execStore.expanded.has(executionId.value)) void execStore.fetchRows(executionId.value)
}

// ── lifecycle ─────────────────────────────────────────────
let stop: (() => void) | null = null

async function refreshNow() {
  if (!executionId.value) return
  try {
    await execStore.fetchDetail(executionId.value)
    // If the poller had given up (404-blip / failure budget), bring it
    // back for non-terminal executions — a manual click is the natural
    // "resume" gesture after the pollError banner.
    const st = execStore.detail?.status
    if (st && !isTerminalExecutionStatus(st)) {
      stop = execStore.startPolling(executionId.value)
    }
    refreshRowsIfExpanded()
  } catch (e) {
    // fetchDetail rethrows; detail stays as-is — surface via pollError.
    const err = e as Error
    execStore.pollError = `刷新失败：${err.message}`
  }
}

async function removeExec() {
  if (!execStore.detail) return
  const ok = await removeExecution(execStore.detail.id, (i) => execStore.remove(i))
  if (ok) router.push('/executions')
}

/** 导出执行时场景快照:快照 draft → plate convert(无 overlay、不注入
 *  凭证;carry 仍物化 — spec §4.3 勘误,与场景库"默认导出"同构)→ 下载。
 *  文件名带 exec<id> 区分于场景库导出;执行时的服务绑定/数据集选择在
 *  执行信息里另行可读。 */
async function exportScenario(): Promise<void> {
  if (!execStore.detail) return
  try {
    const draft = await getScenarioSnapshot(execStore.detail.id)
    const converted = await convertDraftToExecutable(draft)
    const filename =
      `${execStore.detail.scenario_id}-exec${execStore.detail.id}-${exportTimestamp()}.json`
    downloadFile(filename, JSON.stringify(converted, null, 2), 'application/json')
    ElMessage.success(`已导出 ${filename}（执行时版本）`)
  } catch (e) {
    showError('导出场景', e)
  }
}

/** P4:请求协作式取消;在飞 fanout 在行边界收敛,刷新看最新状态。 */
async function cancelExec() {
  if (!execStore.detail) return
  try {
    await cancelExecution(execStore.detail.id)
    ElMessage.success('已请求取消 — 在飞行收敛后生效')
  } catch (e) {
    if ((e as { status?: number }).status === 409) {
      // 终态竞态:刷新让按钮消失即可,不算失败。
      ElMessage.info('该执行已结束,无法取消')
    } else {
      showError('取消', e)
      return
    }
  }
  await refreshNow()
}

onMounted(async () => {
  if (!executionId.value) return
  try {
    await execStore.fetchDetail(executionId.value)
  } catch (e) {
    // Surface load failure instead of an infinite skeleton (fetchDetail
    // rethrows and detail stays null).
    const status = (e as { status?: number }).status
    execStore.pollError = status === 404
      ? '该执行记录不存在（可能已被删除）'
      : `加载失败：${(e as Error).message}`
    return
  }
  stop = execStore.startPolling(executionId.value)
  // 行级表格的展开态跨导航保留(store 持有):回到本页立即补一次 rows。
  refreshRowsIfExpanded()
})

onUnmounted(() => {
  if (stop) stop()
})
</script>

<style scoped>
.executions {
  max-width: 1080px;
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

/* 状态配色统一在 @/styles/status-colors.css（见文件末尾引入） */

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

.recipe-title,
.rows-title {
  margin: 0 0 12px;
  color: var(--color-text-primary);
  font-size: 14px;
}

.rows-title {
  margin-top: 8px;
}

.recipe {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 24px;
  padding: 14px 18px;
  margin: 0 0 16px;
  font-size: 12px;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 8px;
}

.recipe dt {
  color: var(--color-text-secondary);
}

.recipe dd {
  margin: 0;
  color: var(--color-text-primary);
}

.mono {
  font-family: var(--font-mono);
}

.dim {
  color: var(--color-text-tertiary);
}

/* ── 行级明细(spec §9.1)────────────────────────────── */
.rows-head {
  display: flex;
  gap: 16px;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.rows-hint {
  margin: 0;
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.rows-panel {
  margin-bottom: 16px;
}

.rows-empty {
  margin: 0;
  padding: 18px;
  color: var(--color-text-tertiary);
  font-size: 12px;
  background: #fff;
  border: 0.5px dashed #e2e8f0;
  border-radius: 8px;
}

.ex-table {
  width: 100%;
  font-size: 12px;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 8px;
  border-collapse: collapse;
}

.ex-table th {
  padding: 8px 10px;
  color: var(--color-text-secondary);
  font-weight: 600;
  text-align: left;
  background: #f8fafc;
  border-bottom: 0.5px solid #e2e8f0;
  white-space: nowrap;
}

.ex-table td {
  padding: 7px 10px;
  color: var(--color-text-primary);
  text-align: left;
  border-bottom: 0.5px solid #f1f5f9;
}

.row-tag {
  display: inline-flex;
  padding: 2px 8px;
  font-size: 10.5px;
  font-weight: 600;
  border-radius: 4px;
  white-space: nowrap;
}

/* 词汇表外的行状态:中性兜底(状态串原样透传,不翻译) */
.row-status-other {
  color: #475569;
  background: #f1f5f9;
}

.row-actions {
  display: inline-flex;
  gap: 4px;
  white-space: nowrap;
}

.ex-table-artifact td {
  padding: 8px 10px 12px;
  background: #f8fafc;
}

.artifact-head {
  display: flex;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 6px;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.artifact-pre {
  max-height: 320px;
  padding: 10px 12px;
  margin: 0;
  overflow: auto;
  font-size: 11px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-all;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 6px;
}

.artifact-error {
  color: #991b1b;
}

.state {
  max-width: 720px;
  padding: 80px 20px;
  margin: 0 auto;
}

.error-state {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: flex-start;
}

.error-actions {
  display: flex;
  gap: 8px;
}

.poll-warn {
  margin-bottom: 12px;
}

.sys-alert {
  margin-bottom: 12px;
}
</style>

<style src="@/styles/status-colors.css"></style>
