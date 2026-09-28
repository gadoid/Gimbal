<!-- EventAnalysisCard.vue — 工作台卡片(P2-07):最近执行的日志分析入口。
     列最近 5 次执行,每行直达其日志分析页;不拉事件明细(卡片保持轻,
     筛选与聚合在日志分析页)。 -->
<template>
  <div class="ea-card wcard" data-testid="wb-card-event-analysis">
    <header class="chead">
      <span class="chead-icon ci-gold">
        <SlibIcon name="clock" :size="14" />
      </span>
      <span class="chead-title">日志分析</span>
      <span class="chead-count">{{ rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/executions" class="manage-link">执行记录 →</router-link>
    </header>
    <div v-if="!rows.length" class="ea-empty">最近没有执行记录</div>
    <RouterLink v-for="r in rows" :key="r.id"
                :to="`/executions/${r.id}/events`"
                class="ea-row" :data-testid="`ea-row-${r.id}`">
      <span class="st" :class="r.status">{{ statusLabel(r.status) }}</span>
      <span class="name">#{{ r.id }} {{ r.scenario_id }}</span>
      <span class="meta mono">{{ r.passed }}/{{ r.total_runs }}</span>
    </RouterLink>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import * as api from '@/api/executions'

const rows = ref<api.ExecutionListItem[]>([])

function statusLabel(st: string): string {
  return { running: '在跑', queued: '排队', done: '完成', failed: '失败', canceled: '取消' }[st] ?? st
}

onMounted(async () => {
  try {
    rows.value = (await api.listExecutions()).items.slice(0, 5)
  } catch { /* 卡片失败静默(工作台其他卡不受影响) */ }
})
</script>

<style scoped>
.ea-card { display: flex; flex-direction: column; gap: 6px; }
.ea-empty { color: #71717a; font-size: 13px; padding: 8px 0; }
.ea-row {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; text-decoration: none; color: inherit;
  padding: 4px 6px; border-radius: 6px;
}
.ea-row:hover { background: #f4f4f5; }
.st { font-size: 11px; padding: 1px 6px; border-radius: 4px; background: #f4f4f5; }
.st.done { background: #dcfce7; color: #166534; }
.st.running { background: #dbeafe; color: #1e40af; }
.st.failed { background: #fee2e2; color: #991b1b; }
.name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta { color: #71717a; font-size: 12px; }
.mono { font-family: ui-monospace, monospace; }
</style>

<style scoped>
.chead { display: flex; align-items: center; gap: 8px; padding: 10px 12px 8px; }
.chead-icon { display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 6px; }
.ci-gold { background: #fef3c7; color: #b45309; }
.chead-title { font-weight: 600; font-size: 13px; }
.chead-count { font-size: 12px; color: #71717a; }
.chead-spacer { flex: 1; }
.manage-link { font-size: 12px; color: #2563eb; text-decoration: none; }
</style>
