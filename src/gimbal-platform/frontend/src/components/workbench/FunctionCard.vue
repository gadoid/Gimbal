<!-- FunctionCard.vue — 集成「功能」通用卡(外部系统集成 §7)。
     P1 = status 模板(保活/状态):S 状态灯、M +最近执行/错误摘要、
     L +周期/下次执行 + 立即执行。卡槽注入 def(fn:<id>) → 批量取数
     接口(30s 轮询,错误隔离);状态叠加:未执行/执行中/正常/失败/
     凭证失效/缺少凭证/过期(stale>1h)/已移除。 -->
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
      <!-- S:状态灯 + 结论 -->
      <div v-if="size === 'S'" class="fn-s" :data-testid="t">
        <span class="fn-dot" :class="tone" />
        <span class="fn-status">{{ statusText }}</span>
      </div>

      <!-- M/L -->
      <template v-else>
        <div class="fn-main">
          <span class="fn-dot" :class="tone" />
          <div class="fn-main-text">
            <span class="fn-status">{{ statusText }}</span>
            <span v-if="data.lastRunAt" class="fn-sub">
              最近执行 {{ relTime(data.lastRunAt) }}
            </span>
            <span v-else class="fn-sub">等待首次执行</span>
          </div>
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
</style>
