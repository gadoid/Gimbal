<!-- RecentExecutionsCard.vue — 工作台注册卡:最近执行。
     框架由 slot 供给;行 = 网格列(#id / 场景 1fr / 状态 chip /
     计数 / 时间),flex-none 各列不重叠。点行直达详情。
     卡头形制三档一致(图标+标题+计数+深链+分隔线);三档只换
     正文密度(设计文档 §4,useCardSize 注入):
       S = 结论统计(成功/失败/运行中大数字);M = 5 行;L = 8 行。 -->
<template>
  <div data-testid="wb-card-recent-executions" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-green">
        <SlibIcon name="history" :size="14" />
      </span>
      <span class="chead-title">最近执行</span>
      <span class="chead-count">{{ state.rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/executions" class="manage-link">全部 →</router-link>
    </header>

    <!-- S 档:只出结论(近 N 次的状态分布) -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <div class="s-stats">
        <span class="s-stat st-done"><b>{{ doneCount }}</b>成功</span>
        <span class="s-stat st-failed"><b>{{ failedCount }}</b>失败</span>
        <span class="s-stat st-running"><b>{{ runningCount }}</b>运行中</span>
      </div>
    </div>

    <template v-else>
      <div v-if="state.rows.length" class="rows">
        <router-link
          v-for="ex in state.rows"
          :key="ex.id"
          :to="executionUrl(ex.id)"
          class="ex-row wrow"
          :data-testid="`wb-ex-row-${ex.id}`"
        >
          <span class="ex-id mono">#{{ ex.id }}</span>
          <span class="wrow-name mono" :title="ex.scenario_id">{{ ex.scenario_id }}</span>
          <span :class="['ex-status', `status-${ex.status}`]">{{ statusText(ex.status) }}</span>
          <span class="ex-counts mono">{{ ex.passed }}<em>/</em>{{ ex.failed }}<em>/</em>{{ ex.total_runs }}</span>
          <span class="wrow-time">{{ relTime(ex.started_at) }}</span>
        </router-link>
      </div>
      <div v-else-if="state.error" class="card-empty">
        <p>执行列表加载失败 — 稍后在「全部」页重试</p>
      </div>
      <div v-else class="card-empty">
        <p>还没有执行记录 — 从场景编排发起第一次执行</p>
        <router-link to="/scenarios" class="cta">去场景库 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { listExecutions, type Execution, type ExecutionStatus } from '@/api/executions'
import { executionStatusText } from '@/utils/executionStatus'
import { executionUrl } from '@/utils/links'
import { relTime } from '@/utils/datetime'

const size = useCardSize()

const state = reactive<{ rows: Execution[]; error: boolean }>({ rows: [], error: false })

const statusText = (s: ExecutionStatus) => executionStatusText(s)

/** 取数量随档位:M=5,L=8(§7 第 5 条:仍复用同一 list API,只调 limit) */
const limit = computed(() => (size.value === 'L' ? 8 : 5))

const doneCount = computed(() => state.rows.filter((r) => r.status === 'done').length)
const failedCount = computed(() => state.rows.filter((r) => r.status === 'failed').length)
const runningCount = computed(() => state.rows.filter((r) => r.status === 'running').length)

const wbT = (suffix: string) => `wb-card-recent-executions-${suffix}`

onMounted(async () => {
  try {
    const res = await listExecutions({ limit: limit.value })
    state.rows = res.items
  } catch {
    state.error = true
  }
})

// 档位在挂载后切换不重拉(数据面 5/8 条都够 S 档统计);下次进工作台生效。
</script>

<style scoped>
/* 卡头 / 结论面 / 行骨架 / 空态形制都在基座 scenario-lib.css
   (.wcard .chead .s-body .wrow .card-empty .cta);
   这里只剩执行卡专属:状态分布面 + 行网格列宽。 */

/* S 档:状态分布(.s-stats/.s-stat 形制在基座,这里只给三个数字上色) */
.st-done b { color: var(--sl-ok); }
.st-failed b { color: var(--sl-bad); }
.st-running b { color: var(--sl-accent); }

/* 执行行:id / 场景 1fr / 状态 / 计数 / 时间 */
.ex-row { grid-template-columns: auto minmax(0, 1fr) auto auto auto; }
.ex-id { color: var(--sl-ink-3); }
.ex-status {
  padding: 1px 7px;
  font-size: 10.5px;
  font-weight: 600;
  border-radius: 4px;
  white-space: nowrap;
}
.ex-counts { color: var(--sl-ink-2); white-space: nowrap; }
.ex-counts em { font-style: normal; color: #cbd5e1; padding: 0 1px; }
</style>

<style src="@/styles/status-colors.css"></style>
