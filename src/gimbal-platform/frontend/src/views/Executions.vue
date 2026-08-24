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

    <h3 class="recipe-title">执行配方</h3>
    <dl class="recipe">
      <template v-for="(v, k) in recipeEntries" :key="k">
        <dt>{{ k }}</dt>
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
import { executionStatusText, isTerminalExecutionStatus } from '@/utils/executionStatus'
import { removeExecution } from '@/utils/removeExecution'
import { useExecutionsStore } from '@/stores/executions'

const route = useRoute()
const router = useRouter()
const execStore = useExecutionsStore()

const executionId = computed(() => Number(route.params.id))

const statusText = computed(() => {
  const s = execStore.detail?.status
  return s ? executionStatusText(s) : ''
})

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
const recipeEntries = computed<Array<[string, unknown]>>(() => {
  const cfg = execStore.detail?.config
  if (!cfg) return []
  return Object.entries(cfg).filter(([, v]) => v !== undefined)
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
</style>

<style src="@/styles/status-colors.css"></style>
