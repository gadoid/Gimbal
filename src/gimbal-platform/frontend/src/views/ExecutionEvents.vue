<!-- ExecutionEvents.vue — 日志分析页(P2-07/C10;结构化日志批 3 增强)。
     单执行的事件与日志组合筛选:标签列(category/module/service/protocol/
     unit/attempt/step)、级别下限("warning 以上")、事件类型、message 全文
     搜索;category 聚合计数条。标签值只取执行器写入的(P1 信封),不从
     文本推断。入口:执行详情页头部 + 工作台卡片。
     批 3 修订:①分类下拉改 counts 驱动(消除与引擎词表的双源漂移——
     硬编码词表已缺 step/resolve/context);②行点击右侧 Sheet 展开
     payload 全字段(S7:展开外移,列表行不变形);③(ts,id) 时间轴下的
     「加载更多」长尾翻页。 -->
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

    <!-- category 聚合(P2-07 验收);批 3:下拉同源驱动 -->
    <div class="counts" data-testid="category-counts">
      <span v-for="(n, c) in counts" :key="c"
            class="count-chip" :class="{ active: filters.category === c }"
            @click="toggleCategory(c as string)">
        {{ c }} · {{ n }}
      </span>
      <span v-if="!Object.keys(counts).length" class="count-empty">暂无事件</span>
    </div>

    <!-- 结果表(批 3:行点击 → 右侧 Sheet 展开 payload) -->
    <div v-if="error" class="state error">{{ error }}</div>
    <div v-else-if="loading && !items.length" class="state">加载中…</div>
    <div v-else-if="!items.length" class="state empty">无匹配记录</div>
    <template v-else>
      <table class="ev-table">
        <thead>
          <tr>
            <th>seq</th><th>时间</th><th>类型</th><th>级别</th><th>分类</th>
            <th>module</th><th>service</th><th>unit</th><th>step</th>
            <th>事件/消息</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in items" :key="it.id"
              :class="['row-click', `row-${it.kind}`]"
              :data-testid="`ev-${it.seq}`"
              :title="'点击查看完整字段'"
              @click="openRow(it)">
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
      <div v-if="hasMore" class="load-more">
        <Button variant="outline" size="sm" data-testid="load-more"
                :disabled="loadingMore" @click="loadMore">
          {{ loadingMore ? '加载中…' : `加载更多(已 ${items.length} 行)` }}
        </Button>
      </div>
      <div v-else-if="items.length >= PAGE_SIZE" class="load-more dim">
        已全部加载({{ items.length }} 行)
      </div>
    </template>

    <!-- 行详情(批 3/S7:展开统一走右侧 Sheet,列表行高恒定) -->
    <Sheet :open="rowOpen" @update:open="rowOpen = $event">
      <SheetContent side="right" class="w-[440px] sm:max-w-[440px] p-0 flex flex-col">
        <SheetHeader class="border-b border-signal-line px-4 py-3">
          <SheetTitle class="text-left mono text-sm">
            {{ detailRow?.kind === 'log' ? '日志行' : '事件行' }} · #{{ detailRow?.id }}
          </SheetTitle>
          <SheetDescription class="text-left">
            {{ detailRow?.level ?? detailRow?.event_type ?? '' }}
            {{ detailRow?.category ? `· ${detailRow.category}` : '' }}
            {{ detailRow?.step ? `· ${detailRow.step}` : '' }}
          </SheetDescription>
        </SheetHeader>
        <div class="flex-1 overflow-y-auto p-4">
          <table class="kv-table" v-if="detailRow">
            <tbody>
              <tr v-for="[k, v] in detailEntries" :key="k">
                <td class="k mono">{{ k }}</td>
                <td class="v mono">{{ v }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="detailRow?.payload && Object.keys(detailRow.payload).length" class="mt-3">
            <div class="section-title">payload 全字段</div>
            <pre class="payload-pre mono">{{ JSON.stringify(detailRow.payload, null, 2) }}</pre>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'
import { Button } from '@/components/ui/button'
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from '@/components/ui/sheet'
import {
  getExecutionEvents, getExecutionEventCounts,
  type ExecutionEventItem,
} from '@/api/executions'

const route = useRoute()
const router = useRouter()
const executionId = computed(() => Number(route.params.id))

const LEVELS = ['TRACE', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL']
const PAGE_SIZE = 200

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
const loadingMore = ref(false)
const error = ref('')
/** 分类下拉 = counts 出现过的类别(批 3:消除与引擎词表的双源漂移,
 *  未知类别自然出现;硬编码时代已缺 step/resolve/context) */
const categories = computed(() => Object.keys(counts.value).sort())

/** 行详情(右抽屉) */
const rowOpen = ref(false)
const detailRow = ref<ExecutionEventItem | null>(null)
const detailEntries = computed<[string, string][]>(() => {
  const r = detailRow.value
  if (!r) return []
  const keys: (keyof ExecutionEventItem)[] = [
    'id', 'seq', 'ts', 'kind', 'level', 'category', 'module', 'service',
    'protocol', 'unit', 'attempt', 'step', 'event_type', 'message',
  ]
  return keys
    .filter((k) => r[k] !== null && r[k] !== undefined && r[k] !== '')
    .map((k) => [k, String(r[k])])
})

function openRow(it: ExecutionEventItem): void {
  detailRow.value = it
  rowOpen.value = true
}

const hasMore = computed(() => items.value.length >= PAGE_SIZE
  && items.value.length % PAGE_SIZE === 0)

function _query(): Record<string, string | number> {
  const q: Record<string, string | number> = { limit: PAGE_SIZE }
  for (const [k, v] of Object.entries(filters)) {
    if (v !== '') (q as Record<string, string>)[k] = v
  }
  return q
}

async function reload(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const r = await getExecutionEvents(executionId.value, _query())
    items.value = r.items
  } catch (e) {
    error.value = e instanceof Error ? e.message : '查询失败'
  } finally {
    loading.value = false
  }
}

async function loadMore(): Promise<void> {
  if (loadingMore.value) return
  loadingMore.value = true
  try {
    // (ts,id) 时间轴翻页:after_ts/after_id 锚在末行(批 4 S2 的同源参数;
    // 本页先按服务端已支持的同面查询推进)
    const q = _query()
    const last = items.value[items.value.length - 1]
    if (last) { q.after_ts = last.ts; q.after_id = last.id }
    const r = await getExecutionEvents(executionId.value, q)
    // 服务端按过滤条件重查(含 after 锚);防重:过滤 id
    const seen = new Set(items.value.map((i) => i.id))
    items.value.push(...r.items.filter((i) => !seen.has(i.id)))
  } catch { /* 翻页失败保留现状 */ } finally {
    loadingMore.value = false
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
.row-click { cursor: pointer; }
.row-click:hover { outline: 1px solid #93c5fd; outline-offset: -1px; }
.load-more { display: flex; justify-content: center; padding: 12px 0; }
.load-more.dim, .dim { font-size: 12px; color: #71717a; }
.kv-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.kv-table td { padding: 3px 6px; border-bottom: 1px solid #f4f4f5; vertical-align: top; }
.kv-table .k { color: #71717a; width: 84px; white-space: nowrap; }
.kv-table .v { word-break: break-all; }
.section-title { font-size: 12px; color: #71717a; margin-bottom: 6px; }
.payload-pre {
  font-size: 11px; background: #f8fafc; border: 1px solid #e2e8f0;
  border-radius: 6px; padding: 8px; overflow-x: auto; max-height: 50vh;
}
.state { padding: 24px; text-align: center; color: #71717a; }
.state.error { color: #b91c1c; }
</style>
