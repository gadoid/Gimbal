<!-- RecentExecutionsCard.vue — 工作台注册卡:最近执行。
     数据契约(§7 第 5 条):复用 list API + limit(5),不拉全量。
     行 = 状态色 chip + passed/failed/total + 相对时间;点行直达详情。 -->
<template>
  <div class="card-root" data-testid="wb-card-recent-executions">
    <header class="card-head">
      <span class="card-title">最近执行</span>
      <span class="card-count">{{ state.rows.length }}</span>
      <span class="spacer" />
      <router-link to="/executions" class="manage-link">全部 →</router-link>
    </header>

    <div v-if="state.rows.length" class="ex-list">
      <router-link
        v-for="ex in state.rows"
        :key="ex.id"
        :to="executionUrl(ex.id)"
        class="ex-row"
        :data-testid="`wb-ex-row-${ex.id}`"
      >
        <span class="ex-id mono">#{{ ex.id }}</span>
        <span class="ex-scenario mono">{{ ex.scenario_id }}</span>
        <span :class="['ex-status', `status-${ex.status}`]">{{ statusText(ex.status) }}</span>
        <span class="ex-counts mono">{{ ex.passed }}/{{ ex.failed }}/{{ ex.total_runs }}</span>
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
    state.error = true   // §7 三态:取数失败显式说,不给假空态
  }
})
</script>

<style scoped>
.card-root {
  display: flex; flex-direction: column; gap: 10px;
  padding: 14px 16px; background: #fff;
  border: 1px solid #e1e5eb; border-radius: 10px;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.06);
  height: 100%; box-sizing: border-box;
}
.card-head { display: flex; align-items: center; gap: 8px; }
.card-title { font-size: 14px; font-weight: 700; color: #10151c; }
.card-count {
  padding: 1px 6px; font-size: 11px; font-weight: 600;
  color: #64748b; background: #f1f5f9; border-radius: 3px;
}
.spacer { flex: 1; }
.manage-link { font-size: 12px; font-weight: 500; color: #2f6fed; text-decoration: none; }
.manage-link:hover { text-decoration: underline; }

.ex-list { display: flex; flex-direction: column; gap: 2px; }
.ex-row {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 6px; font-size: 12px;
  color: inherit; text-decoration: none;
  border-radius: 6px;
}
.ex-row:hover { background: #f6f8fa; }
.ex-id { color: #94a3b8; flex: none; }
.ex-scenario {
  flex: 1; min-width: 0; font-weight: 600; color: #10151c;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ex-status {
  flex: none; padding: 1px 7px; font-size: 10.5px; font-weight: 600;
  border-radius: 4px;
}
.ex-counts { flex: none; color: #64748b; }
.ex-time { flex: none; font-size: 11px; color: #94a3b8; }

.card-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 14px 0; text-align: center;
}
.card-empty p { margin: 0; font-size: 12px; color: #64748b; }
.cta { font-size: 12.5px; font-weight: 600; color: #2f6fed; text-decoration: none; }
.cta:hover { text-decoration: underline; }

.mono { font-family: var(--font-mono, monospace); }
</style>

<style src="@/styles/status-colors.css"></style>
