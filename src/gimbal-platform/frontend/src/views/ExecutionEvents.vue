<!-- ExecutionEvents.vue — 日志分析页(P2-07/C10;批 3/批 4/批 5 增强)。
     单执行的事件与日志组合筛选:标签列/级别下限/事件类型/全文搜索;
     category 聚合计计条(下拉同源驱动)。入口:执行详情页 + 工作台卡片。
     批 3:counts 驱动下拉;行点击右侧 Sheet(kv+payload);加载更多。
     批 4:S3 视图切换(日志/事件/混合时间轴 —— 混合=kind 不发,(ts,id)
     统一排序,事件与日志 interleaved 真实执行现场);S4 过滤态 URL 双向
     同步(进入读/变更 replace;深链分享);S1/S2 落地:around 深链
     (失败事件锚点,来自详情页「查看日志」),锚行高亮。
     批 5:S5 连续重复折叠(调用点键 (step,function,line,level),仅折叠
     视图呈现,不影响数据/导出;#304 实证 (step,message) 精确匹配可折
     行 0 —— 消息带插值变量,按调用点合并才是循环体);S7 行高恒定
     (消息列单行省略,全文走右抽屉)。 -->
<template>
  <ListPage title="日志分析" icon="history" width="wide"
    :subtitle="`执行 #${executionId} — 事件与日志按执行上下文标签筛选`">
    <template #actions>
      <Button variant="outline" size="sm" @click="goDetail">← 执行详情</Button>
      <Button variant="outline" size="sm" data-testid="copy-link" @click="copyLink">
        复制链接
      </Button>
    </template>

    <!-- 视图切换(S3):日志 / 事件 / 混合时间轴 -->
    <div class="view-tabs" role="tablist" aria-label="视图">
      <button
        v-for="v in (['log', 'event', 'mixed'] as const)" :key="v"
        role="tab" :aria-selected="viewMode === v"
        :class="['view-tab', { active: viewMode === v }]"
        :data-testid="`view-${v}`"
        @click="switchView(v)"
      >{{ { log: '日志', event: '事件', mixed: '混合时间轴' }[v] }}</button>
    </div>

    <!-- 筛选栏 -->
    <div class="filters">
      <select v-if="viewMode !== 'mixed'" v-model="filters.kind" data-testid="f-kind" class="f-select">
        <option value="">全部类型</option>
        <option value="event">事件</option>
        <option value="log">日志</option>
      </select>
      <select v-if="viewMode === 'log'" v-model="filters.level_min"
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
      <input v-if="viewMode !== 'log'" v-model="filters.event_type" class="f-input" placeholder="事件类型" />
      <input v-model="filters.search" data-testid="f-search" class="f-input grow"
             placeholder="message 全文搜索…" />
      <label class="fold-toggle" data-testid="f-fold">
        <input type="checkbox" v-model="foldOn" />
        折叠重复(调用点)
      </label>
      <Button size="sm" @click="reload" data-testid="f-apply">筛选</Button>
      <Button variant="outline" size="sm" @click="reset">重置</Button>
      <Button v-if="aroundActive" variant="outline" size="sm"
              data-testid="exit-around" @click="exitAround">
        退出上下文窗口
      </Button>
    </div>

    <!-- category 聚合(P2-07 验收);下拉同源驱动 -->
    <div class="counts" data-testid="category-counts">
      <span v-for="(n, c) in counts" :key="c"
            class="count-chip" :class="{ active: filters.category === c }"
            @click="toggleCategory(c as string)">
        {{ c }} · {{ n }}
      </span>
      <span v-if="!Object.keys(counts).length" class="count-empty">暂无事件</span>
    </div>

    <!-- 上下文窗口提示(S1/S2:失败事件锚点深链的落点) -->
    <div v-if="aroundActive" class="around-banner" data-testid="around-banner">
      以失败事件为中心的上下文窗口(前 {{ aroundN }} 行 · 后 {{ aroundN }} 行)
      —— 根因几乎总在失败点之前。
    </div>

    <!-- 结果表 -->
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
          <template v-for="d in displayItems" :key="d.kind === 'fold' ? `fold-${d.first.id}` : d.it.id">
            <tr v-if="d.kind === 'single'"
                :class="['row-click', `row-${d.it.kind}`,
                         { 'row-anchor': d.it.id === aroundId }]"
                :data-testid="`ev-${d.it.seq}`"
                :title="'点击查看完整字段'"
                @click="openRow(d.it)">
              <td class="mono">{{ d.it.seq }}</td>
              <td class="mono ts">{{ shortTs(d.it.ts) }}</td>
              <td><span class="kind-badge" :class="d.it.kind">{{ d.it.kind === 'log' ? '日志' : '事件' }}</span></td>
              <td><span v-if="d.it.level" class="lv" :class="lvClass(d.it.level)">{{ d.it.level }}</span></td>
              <td>{{ d.it.category ?? '—' }}</td>
              <td>{{ d.it.module ?? '—' }}</td>
              <td>{{ d.it.service ?? '—' }}</td>
              <td>{{ d.it.unit ?? '—' }}</td>
              <td>{{ d.it.step ?? '—' }}</td>
              <td class="msg">
                <span v-if="d.it.event_type" class="et mono">{{ d.it.event_type }}</span>
                {{ d.it.message ?? '' }}
              </td>
            </tr>
            <!-- S5 折叠组:首行概览 + ×N;展开走右抽屉(行高恒定,S7) -->
            <tr v-else
                :class="['row-click', 'row-fold',
                         { 'row-anchor': d.members.some((m) => m.id === aroundId) }]"
                :data-testid="`fold-${d.first.id}`"
                :title="`同调用点连续 ${d.count} 行 —— 点击查看明细`"
                @click="openFold(d)">
              <td class="mono dim">…</td>
              <td class="mono ts">{{ shortTs(d.first.ts) }}</td>
              <td><span class="kind-badge log">日志</span></td>
              <td><span v-if="d.first.level" class="lv" :class="lvClass(d.first.level)">{{ d.first.level }}</span></td>
              <td>{{ d.first.category ?? '—' }}</td>
              <td>{{ d.first.module ?? '—' }}</td>
              <td>{{ d.first.service ?? '—' }}</td>
              <td>{{ d.first.unit ?? '—' }}</td>
              <td>{{ d.first.step ?? '—' }}</td>
              <td class="msg">
                <span class="fold-badge" data-testid="fold-count">×{{ d.count }}</span>
                {{ d.first.message ?? '' }}
                <span class="fold-note dim">{{ foldCallSite(d.first) }}</span>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      <div v-if="!aroundActive && hasMore" class="load-more">
        <Button variant="outline" size="sm" data-testid="load-more"
                :disabled="loadingMore" @click="loadMore">
          {{ loadingMore ? '加载中…' : `加载更多(已 ${items.length} 行)` }}
        </Button>
      </div>
      <div v-else-if="!aroundActive && items.length >= PAGE_SIZE" class="load-more dim">
        已全部加载({{ items.length }} 行)
      </div>
    </template>

    <!-- 行详情/折叠组成员(右侧 Sheet:展开外移,列表行高恒定) -->
    <Sheet :open="rowOpen" @update:open="rowOpen = $event">
      <SheetContent side="right" class="w-[440px] max-w-[92vw] flex-col gap-0 p-0 sm:max-w-[440px]">
        <SheetHeader class="border-b border-signal-line px-4 py-3">
          <SheetTitle v-if="detailFold" class="text-left mono text-sm">
            折叠组 · ×{{ detailFold.count }} 行
          </SheetTitle>
          <SheetTitle v-else class="text-left mono text-sm">
            {{ detailRow?.kind === 'log' ? '日志行' : '事件行' }} · #{{ detailRow?.id }}
          </SheetTitle>
          <SheetDescription class="text-left">
            <template v-if="detailFold">
              同调用点连续 {{ detailFold.count }} 行(近似折叠 —— 变量值合并
              展示,点成员看全文/全字段):{{ foldCallSite(detailFold.first) }}
            </template>
            <template v-else>
              {{ detailRow?.level ?? detailRow?.event_type ?? '' }}
              {{ detailRow?.category ? `· ${detailRow.category}` : '' }}
              {{ detailRow?.step ? `· ${detailRow.step}` : '' }}
            </template>
          </SheetDescription>
        </SheetHeader>
        <div class="flex-1 overflow-y-auto p-4">
          <!-- S5 折叠组成员明细 -->
          <div v-if="detailFold" class="fold-members">
            <button v-for="m in detailFold.members" :key="m.id"
                    class="fold-member row-click" :data-testid="`fold-member-${m.id}`"
                    @click="openRow(m)">
              <span class="mono dim">{{ shortTs(m.ts) }}</span>
              <span class="mono msg-line">{{ m.message ?? '' }}</span>
            </button>
          </div>
          <template v-else>
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
          </template>
        </div>
      </SheetContent>
    </Sheet>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
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
import { toast } from '@/utils/toast'

const route = useRoute()
const router = useRouter()
const executionId = computed(() => Number(route.params.id))

const LEVELS = ['TRACE', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL']
const PAGE_SIZE = 200

type ViewMode = 'log' | 'event' | 'mixed'
const viewMode = ref<ViewMode>('log')

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

/** S1/S2:上下文窗口锚(深链 around_ts/around_id 带 unit) */
const aroundTs = ref('')
const aroundId = ref<number | null>(null)
const aroundN = ref(50)
const aroundActive = computed(() => aroundTs.value !== '' && aroundId.value !== null)

const items = ref<ExecutionEventItem[]>([])
const counts = ref<Record<string, number>>({})
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')
const categories = computed(() => Object.keys(counts.value).sort())

/** 行详情(右抽屉) */
const rowOpen = ref(false)
const detailRow = ref<ExecutionEventItem | null>(null)
/** S5 折叠组展开态(同一抽屉;点成员切回行详情) */
const detailFold = ref<FoldGroup | null>(null)

type FoldGroup = {
  kind: 'fold'
  count: number
  first: ExecutionEventItem
  members: ExecutionEventItem[]
}
type DisplayItem = { kind: 'single'; it: ExecutionEventItem } | FoldGroup

/** S5 折叠开关(仅折叠视图呈现,不影响数据/导出/URL)。 */
const foldOn = ref(true)

/** 折叠键 = 调用点 (step,function,line,level):JsonSink 已序列化
 * function/line(payload 携带),同调用点的连续行即循环体 —— #304 实证
 * (step,message) 精确匹配可折行 0(消息带插值变量),按调用点才折得动。
 * 近似折叠:同调用点不同变量值合并展示,明细走抽屉。 */
function foldKey(it: ExecutionEventItem): string | null {
  if (it.kind !== 'log') return null
  const p = it.payload as Record<string, unknown> | null | undefined
  const fn = p?.function
  const ln = p?.line
  if (typeof fn !== 'string' || !fn) return null
  if (typeof ln !== 'number') return null
  return `${it.step ?? ''}\u0000${fn}\u0000${ln}\u0000${it.level ?? ''}`
}

const displayItems = computed<DisplayItem[]>(() => {
  if (!foldOn.value) {
    return items.value.map((it) => ({ kind: 'single' as const, it }))
  }
  const out: DisplayItem[] = []
  let cur: FoldGroup | null = null
  let curKey: string | null = null
  const flush = (): void => {
    // 组结束:≥2 行才是折叠组;单次出现的调用点保持普通行(×1 无信息)
    if (cur) out.push(cur.count > 1 ? cur : { kind: 'single', it: cur.first })
    cur = null
    curKey = null
  }
  for (const it of items.value) {
    const k = foldKey(it)
    if (k !== null && cur !== null && k === curKey) {
      cur.count += 1
      cur.members.push(it)
      continue
    }
    flush()
    if (k !== null) {
      cur = { kind: 'fold', count: 1, first: it, members: [it] }
      curKey = k
    } else {
      out.push({ kind: 'single', it })
    }
  }
  flush()
  return out
})

function foldCallSite(it: ExecutionEventItem): string {
  const p = it.payload as Record<string, unknown> | null | undefined
  const fn = typeof p?.function === 'string' ? p.function : ''
  const ln = typeof p?.line === 'number' ? p.line : ''
  return `${fn}:${ln}`
}

function openRow(it: ExecutionEventItem): void {
  detailFold.value = null
  detailRow.value = it
  rowOpen.value = true
}

function openFold(g: FoldGroup): void {
  detailRow.value = null
  detailFold.value = g
  rowOpen.value = true
}
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

const hasMore = computed(() => !aroundActive.value
  && items.value.length >= PAGE_SIZE
  && items.value.length % PAGE_SIZE === 0)

// ── S4:过滤态 URL 双向同步 ─────────────────────────────────
const URL_KEYS = ['kind', 'level_min', 'category', 'module', 'service',
  'unit', 'step', 'event_type', 'search'] as const

function readFiltersFromUrl(): void {
  const q = route.query
  const v = q.view as ViewMode | undefined
  if (v === 'log' || v === 'event' || v === 'mixed') viewMode.value = v
  for (const k of URL_KEYS) {
    const val = q[k]
    if (typeof val === 'string') (filters as Record<string, string>)[k] = val
  }
  const ats = q.around_ts, aid = q.around_id
  aroundTs.value = typeof ats === 'string' ? ats : ''
  aroundId.value = aid !== undefined && aid !== null ? Number(aid) : null
  const n = q.n
  if (n !== undefined && !Number.isNaN(Number(n))) aroundN.value = Math.min(500, Math.max(1, Number(n)))
}

function syncFiltersToUrl(): void {
  const q: Record<string, string> = { view: viewMode.value }
  for (const k of URL_KEYS) {
    const v = (filters as Record<string, string>)[k]
    if (v !== '') q[k] = v
  }
  if (aroundActive.value) {
    q.around_ts = aroundTs.value
    q.around_id = String(aroundId.value)
    q.n = String(aroundN.value)
  }
  void router.replace({ query: q })
}

function switchView(v: ViewMode): void {
  viewMode.value = v
  // 视图即 kind 的语义层:log/event 固定 kind;mixed 不发 kind
  filters.kind = v === 'mixed' ? '' : v
  void reload()
}

function exitAround(): void {
  aroundTs.value = ''
  aroundId.value = null
  void reload()
}

function _query(): Record<string, string | number> {
  const q: Record<string, string | number> = { limit: PAGE_SIZE }
  for (const [k, v] of Object.entries(filters)) {
    if (v !== '') (q as Record<string, string>)[k] = v
  }
  if (aroundActive.value) {
    q.around_ts = aroundTs.value
    q.around_id = aroundId.value as number
    q.n_before = aroundN.value
    q.n_after = aroundN.value
  }
  return q
}

async function reload(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const r = await getExecutionEvents(executionId.value, _query())
    items.value = r.items
    syncFiltersToUrl()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '查询失败'
  } finally {
    loading.value = false
  }
}

async function loadMore(): Promise<void> {
  if (loadingMore.value || aroundActive.value) return
  loadingMore.value = true
  try {
    const q = _query()
    const last = items.value[items.value.length - 1]
    if (last) { q.after_ts = last.ts; q.after_id = last.id }
    const r = await getExecutionEvents(executionId.value, q)
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
  aroundTs.value = ''
  aroundId.value = null
  void reload()
}

function toggleCategory(c: string): void {
  filters.category = filters.category === c ? '' : c
  void reload()
}

function goDetail(): void {
  void router.push(`/executions/${executionId.value}`)
}

/** S4:复制当前过滤态链接(权限跟随执行可见性,§4 总则)。 */
async function copyLink(): Promise<void> {
  try {
    await navigator.clipboard.writeText(window.location.href)
    toast.success('链接已复制 — 过滤态完整保留,打开即同视图')
  } catch {
    toast.error('复制失败,请手动复制地址栏')
  }
}

function shortTs(ts: string): string {
  return ts.replace('T', ' ').replace('Z', '').slice(11, 23)
}

function lvClass(lv: string): string {
  return ['WARNING', 'ERROR', 'CRITICAL'].includes(lv) ? 'warn' : ''
}

onMounted(() => {
  readFiltersFromUrl()
  // 初始视图语义:log/event 固定 kind(冷开未带 kind query 时保持默认
  // 视图的筛选语义;URL 显式带了 kind 则以 URL 为准)
  if (!route.query.kind && viewMode.value !== 'mixed' && !filters.kind) {
    filters.kind = viewMode.value
  }
  void reload()
  void reloadCounts()
})

// 深链参数外部变化(浏览器前进/后退)重新应用
watch(() => route.query, () => {
  const ats = route.query.around_ts
  if (typeof ats === 'string' && ats !== aroundTs.value) {
    readFiltersFromUrl()
    void reload()
  }
})

// 执行号变化但路由记录复用(/executions/12/events → /executions/13/events,
// 连点通知/深链直达)时组件不重挂载 —— 与详情页同款:盯参数重新取数。
watch(executionId, (next, prev) => {
  if (!next || next === prev) return
  readFiltersFromUrl()
  void reload()
  void reloadCounts()
})
</script>

<style scoped>
.view-tabs { display: inline-flex; gap: 2px; margin-bottom: 10px; border: 1px solid var(--border, #d4d4d8); border-radius: 8px; padding: 2px; }
.view-tab {
  border: none; background: transparent; padding: 4px 14px; font-size: 13px;
  border-radius: 6px; cursor: pointer; color: var(--muted-fg, #5B6472);
}
.view-tab.active { background: #eff6ff; color: #1d4ed8; font-weight: 600; }
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
.around-banner {
  font-size: 12px; background: #fef9c3; color: #a16207;
  border: 1px solid #fde68a; border-radius: 6px; padding: 6px 12px; margin-bottom: 10px;
}
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
.msg {
  /* S7 行高恒定:单行省略,全文走右抽屉 */
  max-width: 420px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.row-log { background: #fffbeb; }
.row-fold { background: #fefce8; }
.fold-badge {
  font-size: 11px; background: #fde68a; color: #92400e;
  padding: 0 6px; border-radius: 4px; margin-right: 6px;
}
.fold-note { font-size: 11px; margin-left: 8px; }
.dim { color: #71717a; }
.fold-toggle {
  display: inline-flex; align-items: center; gap: 4px; font-size: 13px;
  white-space: nowrap; cursor: pointer; color: var(--muted-fg, #5B6472);
}
.fold-members { display: flex; flex-direction: column; gap: 2px; }
.fold-member {
  display: flex; gap: 8px; text-align: left; font-size: 12px;
  border: none; background: #f8fafc; border-radius: 6px; padding: 4px 8px;
  cursor: pointer;
}
.fold-member:hover { background: #eff6ff; }
.fold-member .msg-line {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.row-anchor { outline: 2px solid #f59e0b; outline-offset: -2px; }
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
