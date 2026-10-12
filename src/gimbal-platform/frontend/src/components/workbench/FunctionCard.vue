<!-- FunctionCard.vue — 集成「功能」通用卡(外部系统集成 §7)。
     模板(Y4):status(S 状态灯/M 摘要/L+操作,缺省)、kv(全部输出
     键值)、counter(首个数值键大数字)、list(首个数组键,S 条数/
     M 前 5/L 前 10)。数据 = cards 批量接口的 outputs 投影
     (output_mapping;已脱敏)。卡槽注入 def(fn:<id>) → 30s 轮询,
     错误隔离;状态叠加:未执行/执行中/失败/凭证失效/缺少凭证/
     过期(stale>1h)/已移除。 -->
<template>
  <div class="wcard fn-card" :data-testid="`wb-card-${cardId}`">
    <header class="chead">
      <span class="chead-icon ci-blue">
        <SlibIcon name="layers" :size="14" />
      </span>
      <span class="chead-title">{{ data?.name || '功能' }}</span>
      <span class="chead-spacer" />
      <router-link to="/integrations" class="manage-link">详情 →</router-link>
    </header>

    <!-- 已移除 / 不可见 -->
    <div v-if="removed" class="card-empty" :data-testid="`${t}-removed`">
      <p>该功能已移除或不可见 — 可直接删卡</p>
    </div>

    <template v-else-if="data">
      <!-- S:按模板 —— status 状态灯 / counter 大数字 / kv 首键 / list 条数 -->
      <div v-if="size === 'S'" class="fn-s" :data-testid="t">
        <template v-if="tplKind === 'counter'">
          <span class="fn-counter-num mono">{{ counterText }}</span>
        </template>
        <template v-else-if="tplKind === 'kv'">
          <span class="fn-status">{{ kvEntries[0] ? `${kvEntries[0][0]} ${fmt(kvEntries[0][1])}` : '暂无输出' }}</span>
        </template>
        <template v-else-if="tplKind === 'list'">
          <span class="fn-status">{{ listCount }} 条</span>
        </template>
        <template v-else>
          <span class="fn-dot" :class="tone" />
          <span class="fn-status">{{ statusText }}</span>
        </template>
      </div>

      <!-- M/L:按模板分派(Y4:status/kv/counter/list) -->
      <template v-else>
        <div v-if="tplKind === 'status'" class="fn-main">
          <span class="fn-dot" :class="tone" />
          <div class="fn-main-text">
            <span class="fn-status">{{ statusText }}</span>
            <span v-if="data.lastRunAt" class="fn-sub">
              最近执行 {{ relTime(data.lastRunAt) }}
            </span>
            <span v-else class="fn-sub">等待首次执行</span>
          </div>
        </div>
        <!-- kv:全部映射键值(S 档 = 第一个键) -->
        <div v-else-if="tplKind === 'kv'" class="fn-kv-list" :data-testid="`${t}-kv`">
          <div v-for="e in kvEntries" :key="e[0]" class="fn-kv-row">
            <span class="fn-kv-key">{{ e[0] }}</span>
            <span class="fn-kv-val mono">{{ fmt(e[1]) }}</span>
          </div>
          <p v-if="!kvEntries.length" class="fn-sub">暂无输出</p>
        </div>
        <!-- counter:大数字 + 最近执行 -->
        <div v-else-if="tplKind === 'counter'" class="fn-counter" :data-testid="`${t}-counter`">
          <span class="fn-counter-num mono">{{ counterText }}</span>
          <span class="fn-sub">{{ data.lastRunAt ? `最近执行 ${relTime(data.lastRunAt)}` : '等待首次执行' }}</span>
        </div>
        <!-- list:M 前 5 / L 前 10 -->
        <div v-else-if="tplKind === 'list'" class="fn-list" :data-testid="`${t}-list`">
          <p class="fn-sub">共 {{ listCount }} 条</p>
          <ul class="fn-list-items">
            <li v-for="(item, i) in listItems" :key="i" class="fn-list-item mono">
              {{ fmt(item) }}
            </li>
          </ul>
        </div>
        <p v-if="staleNote" class="fn-note warn">{{ staleNote }}</p>
        <p v-if="data.lastError && data.lastStatus === 'failed'"
           class="fn-note err" :title="data.lastError">
          {{ data.lastError.slice(0, 120) }}
        </p>
        <div v-if="size === 'L'" class="fn-l-rows">
          <span class="fn-kv">周期 {{ data.cronText || '—' }}</span>
          <button
            type="button" class="fn-run" :data-testid="`${t}-run`"
            :disabled="running || removed"
            @click="runNow"
          >{{ running ? '执行中…' : '立即执行' }}</button>
        </div>
      </template>
    </template>

    <div v-else-if="failed" class="card-empty">
      <p>取数失败 — 稍后自动重试</p>
    </div>
    <div v-else class="card-empty"><p>加载中…</p></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import {
  fetchFunctionCards, runIntegrationTask, integrationErr,
  type FunctionCardData,
} from '@/api/integration'
import { useCardSize, useCardDef } from './registry'
import { toast } from '@/utils/toast'

const size = useCardSize()
const def = useCardDef()

const cardId = computed(() => def.value?.id || 'fn:0')
const data = ref<FunctionCardData | null>(null)
const failed = ref(false)
const running = ref(false)
let timer: number | null = null

const t = computed(() => `fn-card-${cardId.value}`)

const removed = computed(() => data.value?.state === 'removed')
const runningState = computed(() => data.value?.state === 'running')

const tone = computed<'ok' | 'bad' | 'run' | 'muted'>(() => {
  if (removed.value || !data.value) return 'muted'
  if (runningState.value) return 'run'
  if (!data.value.lastRunAt) return 'muted'
  if (data.value.stale) return 'muted'
  if (data.value.lastStatus === 'passed') return 'ok'
  if (data.value.lastStatus) return 'bad'
  return 'muted'
})

const statusText = computed(() => {
  if (removed.value) return '已移除'
  if (runningState.value) return '执行中'
  if (!data.value?.lastRunAt) return '未执行'
  if (data.value.stale) return '数据可能过期'
  if (data.value.lastStatus === 'passed') return '正常'
  if (data.value.lastStatus === 'failed') return '失败'
  if (data.value.lastStatus === 'timeout') return '超时'
  return data.value.lastStatus || '—'
})

const staleNote = computed(() =>
  data.value?.stale ? '超过 1 小时未刷新 — 调度器可能已停摆' : '')

// ── Y4:模板渲染面(status|kv|counter|list;缺省 status)──────────
const tplKind = computed(() =>
  ['kv', 'counter', 'list'].includes(data.value?.cardTemplate || '')
    ? (data.value!.cardTemplate as string) : 'status')

/** kv 条目 = outputs 全部键值(S 档只显第一个,CSS 截) */
const kvEntries = computed<[string, unknown][]>(() =>
  Object.entries(data.value?.outputs || {}))

const counterText = computed(() => {
  const outs = data.value?.outputs || {}
  // 首个数值键;无 → 条目数
  const first = Object.values(outs)[0]
  return typeof first === 'number' ? String(first)
    : Array.isArray(first) ? String(first.length) : (first ?? '—')
})

const listItems = computed<unknown[]>(() => {
  const first = Object.values(data.value?.outputs || {})[0]
  return Array.isArray(first) ? first.slice(0, size.value === 'L' ? 10 : 5) : []
})
const listCount = computed(() => {
  const first = Object.values(data.value?.outputs || {})[0]
  return Array.isArray(first) ? first.length : 0
})

function fmt(v: unknown): string {
  if (v == null) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

async function load(): Promise<void> {
  try {
    const items = await fetchFunctionCards([cardId.value])
    data.value = items[0] ?? { id: cardId.value, state: 'removed' }
    failed.value = false
  } catch {
    failed.value = true
  }
}

async function runNow(): Promise<void> {
  const tid = Number(cardId.value.slice(3))
  if (!tid || running.value) return
  running.value = true
  try {
    const out = await runIntegrationTask(tid)
    toast.success(`已执行:${out.result.status === 'passed' ? '通过' : '失败'}`)
    await load()
  } catch (e) {
    toast.error(integrationErr(e))
  } finally {
    running.value = false
  }
}

function relTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime()
  const m = Math.floor(ms / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m} 分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} 小时前`
  return `${Math.floor(h / 24)} 天前`
}

onMounted(() => {
  void load()
  timer = window.setInterval(() => void load(), 30_000)
})
onUnmounted(() => { if (timer !== null) window.clearInterval(timer) })
</script>

<style scoped>
.fn-card { gap: 6px; }
.fn-s { display: flex; align-items: center; gap: 8px; }
.fn-dot { width: 10px; height: 10px; border-radius: 999px; flex: none; }
.fn-dot.ok { background: var(--green, #22c55e); }
.fn-dot.bad { background: var(--red, #e24b4a); }
.fn-dot.run { background: #2f6fed; animation: fn-pulse 1.2s infinite; }
.fn-dot.muted { background: rgb(100 116 139 / 40%); }
@keyframes fn-pulse { 50% { opacity: .35; } }
.fn-status { font-size: 13px; font-weight: 600; }
.fn-main { display: flex; align-items: center; gap: 10px; }
.fn-main-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.fn-sub { font-size: 11.5px; color: rgb(100 116 139); }
.fn-note { margin: 0; font-size: 11.5px; }
.fn-note.warn { color: #b45309; }
.fn-note.err {
  color: #dc2626; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap;
}
.fn-l-rows { display: flex; align-items: center; gap: 10px; margin-top: 2px; }
.fn-kv { font-size: 11.5px; color: rgb(100 116 139); flex: 1; }
.fn-run {
  font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  color: #4338ca; background: var(--accent-soft, #eef2ff);
  border: 1px solid var(--accent-soft-border, #c7d2fe);
}
.fn-run:disabled { opacity: .5; cursor: not-allowed; }
/* Y4 模板 */
.fn-kv-list { display: flex; flex-direction: column; gap: 4px; }
.fn-kv-row { display: flex; justify-content: space-between; gap: 8px;
  font-size: 12.5px; }
.fn-kv-key { color: rgb(100 116 139); }
.fn-kv-val { font-weight: 600; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; max-width: 60%; }
.fn-counter { display: flex; align-items: baseline; gap: 10px; }
.fn-counter-num { font-size: 28px; font-weight: 700; line-height: 1; }
.fn-list-items { margin: 0; padding: 0 0 0 2px; list-style: none;
  display: flex; flex-direction: column; gap: 3px; }
.fn-list-item { font-size: 12px; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
</style>
