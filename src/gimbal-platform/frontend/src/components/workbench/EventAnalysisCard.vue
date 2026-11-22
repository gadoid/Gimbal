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
.ea-card { display: flex; flex-direction: column; gap: 0.375rem; }
.ea-empty { color: var(--c-text-secondary); font-size: 0.8125rem; padding: 0.5rem 0; }
.ea-row {
  display: flex; align-items: center; gap: 0.5rem;
  font-size: 0.8125rem; text-decoration: none; color: inherit;
  padding: 0.25rem 0.375rem; border-radius: 0.375rem;
}
.ea-row:hover { background: var(--sl-row-hover); }
/* 执行状态 chip:与 status-colors.css(.status-*)同令牌 —— 那里是唯一来源 */
.st { font-size: 0.6875rem; padding: 0.0625rem 0.375rem; border-radius: 0.25rem; background: var(--soft-neutral-bg); }
.st.done { background: var(--soft-ok-bg); color: var(--sl-ok); }
.st.running { background: var(--soft-accent-bg); color: var(--sl-accent); }
.st.failed { background: var(--soft-bad-bg); color: var(--sl-bad); }
.name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta { color: var(--c-text-secondary); font-size: 0.75rem; }
.mono { font-family: ui-monospace, monospace; }
</style>

<!-- 卡头(.chead/.ci-gold/.manage-link 等)不再本地重复 —— 直接用
     scenario-lib.css 的共享卡头家族(令牌化 + 双主题 + 分隔线),
     与其余 19 张工作台卡同款。 -->

