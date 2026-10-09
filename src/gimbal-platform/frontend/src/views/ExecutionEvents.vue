<!-- ExecutionEvents.vue — 日志分析页(P2-07/C10)。
     单执行的事件与日志组合筛选:标签列(category/module/service/protocol/
     unit/attempt/step)、级别下限("warning 以上")、事件类型、message 全文
     搜索;category 聚合计数条。标签值只取执行器写入的(P1 信封),不从
     文本推断。入口:执行详情页头部 + 工作台卡片。 -->
<template>
  <ListPage title="日志分析" icon="history" width="wide"
    :subtitle="`执行 #${executionId} — 事件与日志按执行上下文标签筛选`">
    <template #actions>
      <Button variant="outline" size="sm" @click="goDetail">← 执行详情</Button>
    </template>

    <!-- 筛选栏 -->
    <div class="filters">
      <select v-model="filters.kind" data-testid="f-kind" class="f-select">
        <option value="">全部类型</option>
        <option value="event">事件</option>
        <option value="log">日志</option>
      </select>
      <select v-if="filters.kind !== 'event'" v-model="filters.level_min"
              data-testid="f-level" class="f-select">
        <option value="">全部级别</option>
        <option v-for="lv in LEVELS" :key="lv" :value="lv">{{ lv }} 以上</option>
      </select>
      <select v-model="filters.category" data-testid="f-category" class="f-select">
        <option value="">全部分类</option>
        <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
      </select>
      <input v-model="filters.module" data-testid="f-module" class="f-input"
             placeholder="module" />
      <input v-model="filters.service" class="f-input" placeholder="service" />
      <input v-model="filters.unit" class="f-input" placeholder="unit" />
      <input v-model="filters.step" class="f-input" placeholder="step" />
      <input v-model="filters.event_type" class="f-input" placeholder="事件类型" />
      <input v-model="filters.search" data-testid="f-search" class="f-input grow"
             placeholder="message 全文搜索…" />
      <Button size="sm" @click="reload" data-testid="f-apply">筛选</Button>
      <Button variant="outline" size="sm" @click="reset">重置</Button>
    </div>

    <!-- category 聚合(P2-07 验收) -->
    <div class="counts" data-testid="category-counts">
      <span v-for="(n, c) in counts" :key="c"
            class="count-chip" :class="{ active: filters.category === c }"
            @click="toggleCategory(c as string)">
        {{ c }} · {{ n }}
      </span>
      <span v-if="!Object.keys(counts).length" class="count-empty">暂无事件</span>
    </div>

    <!-- 结果表 -->
    <div v-if="error" class="state error">{{ error }}</div>
    <div v-else-if="loading" class="state">加载中…</div>
    <div v-else-if="!items.length" class="state empty">无匹配记录</div>
    <table v-else class="ev-table">
      <thead>
        <tr>
          <th>seq</th><th>时间</th><th>类型</th><th>级别</th><th>分类</th>
          <th>module</th><th>service</th><th>unit</th><th>step</th>
          <th>事件/消息</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="it in items" :key="it.id"
            :class="`row-${it.kind}`" :data-testid="`ev-${it.seq}`">
          <td class="mono">{{ it.seq }}</td>
          <td class="mono ts">{{ shortTs(it.ts) }}</td>
          <td><span class="kind-badge" :class="it.kind">{{ it.kind === 'log' ? '日志' : '事件' }}</span></td>
          <td><span v-if="it.level" class="lv" :class="lvClass(it.level)">{{ it.level }}</span></td>
          <td>{{ it.category ?? '—' }}</td>
          <td>{{ it.module ?? '—' }}</td>
          <td>{{ it.service ?? '—' }}</td>
          <td>{{ it.unit ?? '—' }}</td>
          <td>{{ it.step ?? '—' }}</td>
          <td class="msg">
            <span v-if="it.event_type" class="et mono">{{ it.event_type }}</span>
            {{ it.message ?? '' }}
          </td>
        </tr>
      </tbody>
    </table>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'
import { Button } from '@/components/ui/button'
import {
  getExecutionEvents, getExecutionEventCounts,
  type ExecutionEventItem,
} from '@/api/executions'

const route = useRoute()
const router = useRouter()
const executionId = computed(() => Number(route.params.id))

const LEVELS = ['TRACE', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL']
const CATEGORIES = ['call', 'auth', 'strategy', 'compiler', 'scheduler', 'plugin', 'debug', 'core']

const filters = reactive({
  kind: '' as '' | 'event' | 'log',
  level_min: '',
  category: '',
  module: '',
  service: '',
  unit: '',
  step: '',
  event_type: '',
  search: '',
})

const items = ref<ExecutionEventItem[]>([])
const counts = ref<Record<string, number>>({})
const loading = ref(false)
const error = ref('')
/** 聚合条全量展示(不受筛选影响);分类下拉用静态词表 */
const categories = CATEGORIES

async function reload(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const q: Record<string, string | number> = {}
    for (const [k, v] of Object.entries(filters)) {
      if (v !== '') (q as Record<string, string>)[k] = v
    }
    const r = await getExecutionEvents(executionId.value, q)
    items.value = r.items
  } catch (e) {
    error.value = e instanceof Error ? e.message : '查询失败'
  } finally {
    loading.value = false
  }
}

async function reloadCounts(): Promise<void> {
  try {
    counts.value = (await getExecutionEventCounts(executionId.value)).byCategory
  } catch { /* 聚合失败不阻塞列表 */ }
}

function reset(): void {
  Object.assign(filters, {
    kind: '', level_min: '', category: '', module: '',
    service: '', unit: '', step: '', event_type: '', search: '',
  })
  void reload()
}

function toggleCategory(c: string): void {
  filters.category = filters.category === c ? '' : c
  void reload()
}

function goDetail(): void {
  void router.push(`/executions/${executionId.value}`)
}

function shortTs(ts: string): string {
  return ts.replace('T', ' ').replace('Z', '').slice(11, 23)
}

function lvClass(lv: string): string {
  return ['WARNING', 'ERROR', 'CRITICAL'].includes(lv) ? 'warn' : ''
}

onMounted(() => {
  void reload()
  void reloadCounts()
})
</script>

<style scoped>
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; align-items: center; }
.f-select, .f-input {
  border: 1px solid var(--border, #d4d4d8); border-radius: 6px;
  padding: 4px 8px; font-size: 13px; background: var(--card, #fff);
}
.f-input { width: 110px; }
.f-input.grow { flex: 1; min-width: 180px; }
.counts { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.count-chip {
  font-size: 12px; padding: 2px 10px; border-radius: 999px;
  border: 1px solid var(--border, #d4d4d8); cursor: pointer;
}
.count-chip.active { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }
.count-empty { font-size: 12px; color: #71717a; }
.ev-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.ev-table th {
  text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border, #e4e4e7);
  color: #71717a; font-weight: 500; white-space: nowrap;
}
.ev-table td { padding: 5px 8px; border-bottom: 1px solid var(--f0, #f4f4f5); vertical-align: top; }
.mono { font-family: ui-monospace, monospace; }
.ts { white-space: nowrap; }
.kind-badge { font-size: 11px; padding: 1px 6px; border-radius: 4px; }
.kind-badge.event { background: #eff6ff; color: #1d4ed8; }
.kind-badge.log { background: #fefce8; color: #a16207; }
.lv.warn { color: #b91c1c; font-weight: 600; }
.et { margin-right: 6px; color: #71717a; }
.msg { max-width: 420px; word-break: break-all; }
.row-log { background: #fffbeb; }
.state { padding: 24px; text-align: center; color: #71717a; }
.state.error { color: #b91c1c; }
</style>
