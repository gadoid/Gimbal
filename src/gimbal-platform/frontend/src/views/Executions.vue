<!-- Executions.vue — 单次执行的实时状态页（V3）。
     可观测面是 Execution 计数器 + 后端 data/runs/<date>.jsonl 调度日志
     （运维直读文件，不经 API）；V1 的每-run 明细/报告/日志/SSE 已退役。
     1s 轮询驱动状态刷新。 -->
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
      title="后端重启：本单由启动期 reconcile 收敛为 failed（详见执行配方外的 reconciled 记录）"
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

    <h3 class="recipe-title">执行配方</h3>
    <dl class="recipe">
      <template v-for="([k, label, v]) in recipeEntries" :key="k">
        <dt>{{ label }}</dt>
        <dd class="mono">{{ formatRecipeValue(v) }}</dd>
      </template>
    </dl>

    <p class="observability-hint">
      每-run 调度明细（请求/响应/耗时）由后端写入
      <code class="mono">data/runs/&lt;date&gt;.jsonl</code>，可在服务端检索。
    </p>
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
import { cancelExecution } from '@/api/executions'
import { removeExecution } from '@/utils/removeExecution'
import { showError } from '@/utils/errorFallback'
import { useExecutionsStore } from '@/stores/executions'

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
// the run-level surface lives in data/runs/*.jsonl, not the API.
// 系统键(reconciled/counterDrift)转上方 alert;stepTo 由 pill 表达,
// 均不进 dl。已知键给中文标签,未知键原样。
const RECIPE_LABELS: Record<string, string> = {
  runId: '运行ID',
  scenarioId: '场景',
  dataSetIds: '数据集',
  envId: '环境',
  exec_auth_alias: '执行认证',
  injectCredentials: '凭证注入',
  nRuns: '每行重复',
  parallel: '并发',
  prefix: '提单前缀',
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

function formatRecipeValue(v: unknown): string {
  if (Array.isArray(v)) return v.length ? v.join(', ') : '(空)'
  if (v === null || v === '') return '—'
  return String(v)
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

.recipe-title {
  margin: 0 0 12px;
  color: var(--color-text-primary);
  font-size: 14px;
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

.observability-hint {
  color: var(--color-text-tertiary);
  font-size: 12px;
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
