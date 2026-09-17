<!-- RecentExecutionsCard.vue — 工作台注册卡:最近执行。
     框架由 slot 供给;行 = 网格列(#id / 场景 1fr / 状态 chip /
     计数 / 时间),flex-none 各列不重叠。点行直达详情。 -->
<template>
  <div data-testid="wb-card-recent-executions" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-green">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
      </span>
      <span class="chead-title">最近执行</span>
      <span class="chead-count">{{ state.rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/executions" class="manage-link">全部 →</router-link>
    </header>

    <div v-if="state.rows.length" class="rows">
      <router-link
        v-for="ex in state.rows"
        :key="ex.id"
        :to="executionUrl(ex.id)"
        class="ex-row"
        :data-testid="`wb-ex-row-${ex.id}`"
      >
        <span class="ex-id mono">#{{ ex.id }}</span>
        <span class="ex-scenario mono" :title="ex.scenario_id">{{ ex.scenario_id }}</span>
        <span :class="['ex-status', `status-${ex.status}`]">{{ statusText(ex.status) }}</span>
        <span class="ex-counts mono">{{ ex.passed }}<em>/</em>{{ ex.failed }}<em>/</em>{{ ex.total_runs }}</span>
        <span class="ex-time">{{ relTime(ex.started_at) }}</span>
      </router-link>
    </div>
    <div v-else-if="state.error" class="card-empty">
      <p>执行列表加载失败 — 稍后在「全部」页重试</p>
    </div>
    <div v-else class="card-empty">
      <p>还没有执行记录 — 从场景编排发起第一次执行</p>
      <router-link to="/scenarios" class="cta">去场景库 →</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive } from 'vue'
import { listExecutions, type Execution, type ExecutionStatus } from '@/api/executions'
import { executionStatusText } from '@/utils/executionStatus'
import { executionUrl } from '@/utils/links'
import { relTime } from '@/utils/datetime'

const state = reactive<{ rows: Execution[]; error: boolean }>({ rows: [], error: false })

const statusText = (s: ExecutionStatus) => executionStatusText(s)

onMounted(async () => {
  try {
    const res = await listExecutions({ limit: 5 })
    state.rows = res.items
  } catch {
    state.error = true
  }
})
</script>

<style scoped>
.wcard { display: flex; flex-direction: column; gap: 8px; min-height: 0; }

.chead { display: flex; align-items: center; gap: 8px; }
.chead-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 7px; flex: none;
}
.ci-green { color: #15803d; background: #e8f5ec; }
.chead-title { font-size: 13.5px; font-weight: 700; color: #10151c; }
.chead-count {
  padding: 0 7px; font-size: 11px; font-weight: 700; line-height: 17px;
  color: #64748b; background: #f1f5f9; border-radius: 999px;
}
.chead-spacer { flex: 1; }
.manage-link { font-size: 12px; font-weight: 600; color: #2f6fed; text-decoration: none; }
.manage-link:hover { text-decoration: underline; }

/* ── 执行行(网格列:id / 场景 1fr / 状态 / 计数 / 时间)──── */
.rows { display: flex; flex-direction: column; gap: 2px; }
.ex-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto auto;
  gap: 8px;
  align-items: center;
  padding: 6px 8px;
  margin: 0 -8px;
  font-size: 12px;
  color: inherit; text-decoration: none;
  border-radius: 7px;
  transition: background 0.12s ease;
}
.ex-row:hover { background: #f6f8fa; }
.ex-id { color: #94a3b8; }
.ex-scenario {
  min-width: 0; font-weight: 600; color: #10151c;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ex-status {
  padding: 1px 7px; font-size: 10.5px; font-weight: 600;
  border-radius: 4px; white-space: nowrap;
}
.ex-counts { color: #64748b; white-space: nowrap; }
.ex-counts em { font-style: normal; color: #cbd5e1; padding: 0 1px; }
.ex-time { font-size: 11px; color: #94a3b8; white-space: nowrap; }

.card-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 16px 0 8px; text-align: center;
}
.card-empty p { margin: 0; font-size: 12px; color: #64748b; }
.cta {
  padding: 4px 14px; font-size: 12.5px; font-weight: 600;
  color: #2f6fed; text-decoration: none;
  border: 1px solid #bcd0f7; border-radius: 6px;
  transition: background 0.12s ease;
}
.cta:hover { background: #e7efff; }

.mono { font-family: var(--font-mono, monospace); }
</style>

<style src="@/styles/status-colors.css"></style>
