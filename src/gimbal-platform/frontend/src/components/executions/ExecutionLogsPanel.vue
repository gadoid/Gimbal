/**
 * ExecutionLogsPanel — 执行详情页行内实时日志面板(结构化日志批 3/AD7)。
 *
 * 形态:行内抽屉(D3 拍板)—— 展开即 tail `/logs/stream`,**收起即断开
 * 日志流**(连接数预算 §8:详情页已有事件流,日志流只在面板展开期间存在)。
 *
 * 行为契约(设计 §5/S7):
 * - tail 按 id 收行(AD5),展示按 (ts,id) 插入排序 —— 晚到行插入视口
 *   上方时**视口锚定**(保持首个可见行不动,按其 key 补偿偏移,滚动
 *   查看不跳动);
 * - 自动滚动贴底;用户向上滚动即暂停自动滚动,回到底部恢复;
 * - 级别/类别/step 服务端筛选(变更重连流,backfill 回看最近窗口);
 * - done 帧 → 状态徽标收口;断线指数退避重连(Last-Event-ID 精确续传);
 * - 虚拟滚动不做(批 3 范围单执行数千行 DOM 可承受;万行级优化挂 S7)。
 */
<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { executionLogsStreamUrl } from '@/api/executions'
import { readSseStream } from '@/utils/sse'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'

interface LogRow {
  id: number
  ts: string
  level: string
  category: string | null
  step: string | null
  message: string | null
}

const props = defineProps<{ executionId: number; running: boolean }>()

const LEVELS = ['ALL', 'INFO', 'WARNING', 'ERROR'] as const
const levelMin = ref<(typeof LEVELS)[number]>('ALL')
const category = ref('')
const step = ref('')
const rows = ref<LogRow[]>([])
const categories = computed(() =>
  Array.from(new Set(rows.value.map((r) => r.category).filter((c): c is string => !!c))))
const connState = ref<'idle' | 'connecting' | 'live' | 'done' | 'failed'>('idle')
const MAX_ROWS = 5000          // 面板缓冲上限:超出丢最旧(与日志面「可丢」语义一致)

const scrollBox = ref<HTMLElement | null>(null)
let autoScroll = true
let abort: AbortController | null = null
let reconnects = 0
let generation = 0             // 筛选/收起换流时作废在飞泵

/** (ts,id) 插入排序(排序轴;tail 到达序不保证 ts 序)。 */
function insertRow(row: LogRow): void {
  const arr = rows.value
  let lo = 0, hi = arr.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    const m = arr[mid]!
    if (m.ts < row.ts || (m.ts === row.ts && m.id < row.id)) lo = mid + 1
    else hi = mid
  }
  arr.splice(lo, 0, row)
  if (arr.length > MAX_ROWS) arr.splice(0, arr.length - MAX_ROWS)
}

/** 视口锚定(S7):晚到行插入在视口上方时,按首个可见行 key 补偿偏移。 */
function withViewportAnchor(mutate: () => void): void {
  const el = scrollBox.value
  if (!el || autoScroll) { mutate(); return }
  const key = (node: Element) => (node as HTMLElement).dataset.rowId
  const firstVisible = Array.from(el.children).find(
    (n) => (n as HTMLElement).offsetTop >= el.scrollTop)
  const anchorKey = firstVisible ? key(firstVisible) : null
  const anchorTop = firstVisible ? (firstVisible as HTMLElement).offsetTop : 0
  mutate()
  void nextTick(() => {
    if (anchorKey === null) return
    const restored = Array.from(el.children).find((n) => key(n) === anchorKey)
    if (restored) el.scrollTop = (restored as HTMLElement).offsetTop - anchorTop + el.scrollTop
    else el.scrollTop = el.scrollTop   // 锚行被上限裁掉:保持现位置
  })
}

function onScroll(): void {
  const el = scrollBox.value
  if (!el) return
  autoScroll = el.scrollTop + el.clientHeight >= el.scrollHeight - 24
  if (autoScroll) void nextTick(() => { el.scrollTop = el.scrollHeight })
}

async function pump(gen: number): Promise<void> {
  if (gen !== generation) return
  const auth = useAuthStore()
  const ctrl = new AbortController()
  abort = ctrl
  connState.value = 'connecting'
  const params: Record<string, string | number> = { backfill: 200 }
  if (levelMin.value !== 'ALL') params.level_min = levelMin.value
  if (category.value) params.category = category.value
  if (step.value.trim()) params.step = step.value.trim()
  try {
    const resp = await fetch(executionLogsStreamUrl(props.executionId, params), {
      headers: { Authorization: `Bearer ${auth.accessToken}` },
      signal: ctrl.signal,
    })
    if (resp.status === 404) { connState.value = 'failed'; return }
    if (!resp.ok || !resp.body) throw Object.assign(
      new Error(`stream ${resp.status}`), { status: resp.status })
    connState.value = 'live'
    reconnects = 0
    await readSseStream(resp, (frame) => {
      if (frame.event === 'done') {
        connState.value = 'done'
        return false
      }
      if (frame.event !== 'log' || frame.data === undefined) return
      try {
        const d = JSON.parse(frame.data) as LogRow
        if (d.id !== undefined) {
          withViewportAnchor(() => insertRow(d))
          if (autoScroll) void nextTick(() => {
            if (scrollBox.value) scrollBox.value.scrollTop = scrollBox.value.scrollHeight
          })
        }
      } catch { /* 坏帧忽略,流继续 */ }
    })
    if (connState.value !== ('done' as typeof connState.value) && gen === generation) {
      throw new Error('stream closed')     // 未终态关流 → 重连路径
    }
  } catch (e) {
    if (ctrl.signal.aborted || gen !== generation) return
    reconnects += 1
    if (reconnects <= 5) {
      await new Promise((r) => setTimeout(r, Math.min(1000 * 2 ** (reconnects - 1), 8000)))
      return pump(gen)
    }
    connState.value = 'failed'
  }
}

function start(): void {
  generation += 1
  rows.value = []
  connState.value = 'connecting'
  void pump(generation)
}

function stop(): void {
  generation += 1             // 作废在飞泵/延迟重连
  abort?.abort()
  abort = null
}

watch(() => [levelMin.value, category.value, step.value], () => {
  if (connState.value !== 'idle') { stop(); start() }   // 筛选变更重连(带 backfill 回看)
})

defineExpose({
  open: () => { start() },
  close: () => { stop() },    // 收起即断流(D3/§8)
})

onUnmounted(stop)
</script>

<template>
  <div class="logs-panel" data-testid="exec-logs-panel">
    <div class="logs-toolbar">
      <span class="logs-title">实时日志</span>
      <select v-model="levelMin" data-testid="logs-level" class="logs-select">
        <option v-for="lv in LEVELS" :key="lv" :value="lv">{{ lv === 'ALL' ? '全部级别' : lv + ' 以上' }}</option>
      </select>
      <select v-model="category" data-testid="logs-category" class="logs-select">
        <option value="">全部分类</option>
        <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
      </select>
      <input
        v-model="step" data-testid="logs-step" class="logs-input mono"
        placeholder="step 过滤(如 step-002)" />
      <span :class="['logs-state', `st-${connState}`]" data-testid="logs-state">
        {{ { idle: '未连接', connecting: '连接中…', live: '实时', done: '已收口', failed: '连接失败' }[connState] }}
      </span>
      <span class="logs-count dim mono">{{ rows.length }} 行</span>
    </div>
    <div ref="scrollBox" class="logs-scroll mono" @scroll.passive="onScroll">
      <div
        v-for="r in rows" :key="r.id" :data-row-id="r.id"
        :class="['log-row', `lv-${(r.level || 'INFO').toLowerCase()}`]"
      >
        <span class="log-ts dim">{{ r.ts.slice(11, 23) }}</span>
        <span class="log-lv">{{ r.level }}</span>
        <span v-if="r.category" class="log-cat">{{ r.category }}</span>
        <span v-if="r.step" class="log-step dim">{{ r.step }}</span>
        <span class="log-msg">{{ r.message }}</span>
      </div>
      <div v-if="rows.length === 0" class="logs-empty dim">
        {{ connState === 'live' ? '暂无匹配日志行…' : '等待日志…' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.logs-panel { border: 1px solid var(--border, #e2e8f0); border-radius: 8px; overflow: hidden; }
.logs-toolbar {
  display: flex; align-items: center; gap: 8px; padding: 6px 10px;
  border-bottom: 1px solid var(--border, #e2e8f0); background: #f8fafc; flex-wrap: wrap;
}
.logs-title { font-size: 13px; font-weight: 600; }
.logs-select, .logs-input {
  font-size: 12px; padding: 2px 6px; border: 1px solid #cbd5e1;
  border-radius: 4px; background: #fff; height: 24px;
}
.logs-input { width: 130px; }
.logs-state { font-size: 11px; padding: 1px 8px; border-radius: 10px; }
.st-live { background: #dcfce7; color: #15803d; }
.st-connecting { background: #fef9c3; color: #a16207; }
.st-done { background: #e0e7ff; color: #4338ca; }
.st-failed, .st-idle { background: #fee2e2; color: #b91c1c; }
.logs-count { font-size: 11px; margin-left: auto; }
.logs-scroll { height: 300px; overflow-y: auto; padding: 4px 0; background: #fff; }
.log-row {
  display: flex; gap: 8px; padding: 1px 10px; font-size: 12px;
  line-height: 1.55; white-space: nowrap; align-items: baseline;
}
.log-row:hover { background: #f1f5f9; }
.log-ts { color: #94a3b8; flex: none; width: 86px; }
.log-lv { flex: none; width: 64px; font-weight: 600; }
.lv-warning .log-lv { color: #b45309; }
.lv-error .log-lv, .lv-critical .log-lv { color: #b91c1c; }
.lv-success .log-lv { color: #15803d; }
.lv-info .log-lv, .lv-debug .log-lv, .lv-trace .log-lv { color: #475569; }
.log-cat {
  flex: none; font-size: 11px; background: #eff6ff; color: #1d4ed8;
  padding: 0 6px; border-radius: 4px;
}
.log-step { flex: none; width: 76px; overflow: hidden; text-overflow: ellipsis; }
.log-msg { overflow: hidden; text-overflow: ellipsis; }
.logs-empty { text-align: center; padding: 24px 0; font-size: 12px; }
</style>
