<!-- RecentExecutionsCard.vue — 工作台注册卡:最近执行。
     框架由 slot 供给;行 = 网格列(#id / 场景 1fr / 状态 chip /
     计数 / 时间),flex-none 各列不重叠。点行直达详情。
     三档密度(设计文档 §4,useCardSize 注入):
       S = 结论统计(成功/失败/运行中大数字);M = 5 行;L = 8 行。 -->
<template>
  <div data-testid="wb-card-recent-executions" class="wcard">
    <!-- S 档:只出结论(近 N 次的状态分布) -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <header class="chead">
        <span class="chead-icon ci-green">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
          </svg>
        </span>
        <span class="chead-title">最近执行</span>
      </header>
      <div class="s-stats">
        <span class="s-stat st-done"><b>{{ doneCount }}</b>成功</span>
        <span class="s-stat st-failed"><b>{{ failedCount }}</b>失败</span>
        <span class="s-stat st-running"><b>{{ runningCount }}</b>运行中</span>
      </div>
      <router-link to="/executions" class="s-link">全部 →</router-link>
    </div>

    <template v-else>
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { useCardSize } from './registry'
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
.wcard { display: flex; flex-direction: column; gap: 8px; min-height: 0; }

/* ── 题头(三卡共用形制;底部分隔线,§2 卡头/卡身分区)──────── */
.chead {
  display: flex; align-items: center; gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e1e5eb;
}
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

/* ── S 档:结论面(状态分布大数字,§4"只出结论")────────────── */
.s-body { display: flex; flex-direction: column; gap: 6px; }
.s-body .chead { border-bottom: none; padding-bottom: 0; }
.s-stats { display: flex; gap: 14px; }
.s-stat { font-size: 11px; color: #64748b; }
.s-stat b { display: block; font-size: 22px; font-weight: 700; line-height: 1.15; }
.st-done b { color: #15803d; }
.st-failed b { color: #dc2626; }
.st-running b { color: #2f6fed; }
.s-link { font-size: 11px; font-weight: 600; color: #2f6fed; text-decoration: none; }
.s-link:hover { text-decoration: underline; }

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
