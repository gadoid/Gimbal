<!-- ExecutionReportPanel — 执行报告(B4,2026-11-06 日志报告整理)。

     数据只来自 GET /executions/{id}/report(后端从步骤表渲染,不读文本
     日志),回答四个问题:哪一步失败、哪条断言、期望/实际是什么、请求
     与响应长什么样。

     结构:概览条 → 失败聚焦(首个失败步骤 + 失败断言 + 调用证据)→
     按行(逐行链)/ 单元(graph 链)分组的步骤表,步骤可展开看全部断言
     与提取值。运行中每 3s 刷新,终态停止。 -->
<template>
  <section class="rp" data-testid="exec-report">
    <p v-if="loading && !report" class="rp-empty">报告加载中…</p>
    <p v-else-if="error" class="rp-empty rp-error" data-testid="report-error">{{ error }}</p>

    <template v-else-if="report">
      <!-- 概览 -->
      <div class="rp-summary" data-testid="report-summary">
        <span :class="['rp-verdict', `status-${report.execution.status}`]">
          {{ executionStatusText(report.execution.status) }}
        </span>
        <span class="rp-kv">步骤 <b>{{ report.summary.stepsPassed }}</b> / {{ report.summary.steps }} 通过</span>
        <span class="rp-kv">断言 <b>{{ report.summary.assertionsPassed }}</b> / {{ report.summary.assertions }} 通过</span>
        <span class="rp-kv">行 <b>{{ report.execution.passed }}</b> 通过 · <b>{{ report.execution.failed }}</b> 失败</span>
        <span v-if="report.execution.durationMs !== null" class="rp-kv">耗时 {{ fmtMs(report.execution.durationMs) }}</span>
      </div>

      <p v-if="!report.hasStepData" class="rp-empty" data-testid="report-no-steps">
        {{ running
          ? '还没有完成的步骤——步骤结束后这里会出现结果。'
          : '该执行没有步骤结果(早于步骤落库,或由旧版引擎执行);原始行级工件仅保留 14 天,过期后无可追溯细节。' }}
      </p>

      <!-- 失败聚焦 -->
      <div v-if="report.failure" class="rp-failure" data-testid="report-failure">
        <div class="rp-failure-head">
          <span class="rp-tag status-failed">首个失败</span>
          <span class="rp-step-title">{{ stepTitle(report.failure) }}</span>
          <span class="rp-dim">{{ groupLabelOf(report.failure) }} · 尝试 {{ report.failure.attempt || '—' }}</span>
          <button
            class="rp-locate" data-testid="report-failure-locate"
            title="深链到日志分析:以该 unit 最终失败事件为锚的上下文窗口(根因几乎总在失败点之前)"
            @click="gotoFailureLogs"
          >定位失败上下文 →</button>
        </div>
        <p v-if="report.failure.callSummary" class="rp-call mono">{{ report.failure.callSummary }}</p>
        <p v-if="report.failure.error" class="rp-err mono" data-testid="report-failure-error">{{ report.failure.error }}</p>

        <table v-if="report.failure.failedAssertions.length" class="rp-assert" data-testid="report-failed-assertions">
          <thead><tr><th>断言目标</th><th>操作符</th><th>期望</th><th>实际</th></tr></thead>
          <tbody>
            <tr v-for="(a, i) in report.failure.failedAssertions" :key="i">
              <td class="mono">{{ a.target ?? a.name }}</td>
              <td class="mono">{{ a.operator ?? '—' }}</td>
              <td class="mono">{{ show(a.expected) }}</td>
              <td class="mono rp-actual">{{ show(a.actual) }}</td>
            </tr>
          </tbody>
        </table>

        <div v-if="report.failure.evidence" class="rp-evidence" data-testid="report-evidence">
          <div class="rp-ev-col">
            <h4>请求</h4>
            <p class="mono">{{ report.failure.evidence.request?.method }} {{ report.failure.evidence.request?.url }}</p>
            <pre v-if="hasKeys(report.failure.evidence.request?.headers)" class="mono">{{ pretty(report.failure.evidence.request?.headers) }}</pre>
            <pre v-if="report.failure.evidence.request?.body !== undefined" class="mono">{{ pretty(report.failure.evidence.request?.body) }}</pre>
          </div>
          <div class="rp-ev-col">
            <h4>响应 <span class="mono">{{ show(report.failure.evidence.response?.status) }}</span></h4>
            <pre class="mono">{{ pretty(report.failure.evidence.response?.body) }}</pre>
          </div>
        </div>
        <p v-else class="rp-dim">该步骤没有调用证据(未发出请求,或为旧执行)。</p>
      </div>

      <!-- 分组步骤表 -->
      <div v-for="g in report.groups" :key="g.key" class="rp-group" :data-testid="`report-group-${g.key}`">
        <div class="rp-group-head">
          <span class="rp-group-title">{{ groupTitle(g) }}</span>
          <span v-if="g.status" :class="['rp-tag', groupStatusClass(g.status)]">{{ rowStatusText(g.status) }}</span>
          <span v-if="g.serverSlot !== null && g.serverSlot !== undefined" class="rp-dim"
                :title="`引擎日志在 run 目录的 ${slotLog(g.serverSlot)}`">server 槽位 {{ g.serverSlot }}</span>
        </div>
        <p v-if="!g.steps.length" class="rp-dim rp-pad">无步骤结果</p>
        <table v-else class="rp-steps">
          <thead>
            <tr><th>步骤</th><th>调用</th><th>状态</th><th>断言</th><th>耗时</th><th></th></tr>
          </thead>
          <tbody>
            <template v-for="s in g.steps" :key="stepKey(s)">
              <tr :class="{ 'rp-row-fail': isFail(s.status) }">
                <td>
                  <span class="rp-step-title">{{ stepTitle(s) }}</span>
                  <span v-if="s.attempt && s.attempt !== '1.1'" class="rp-dim"> · 尝试 {{ s.attempt }}</span>
                </td>
                <td class="mono rp-call-cell" :title="s.callSummary">{{ s.callSummary || '—' }}</td>
                <td><span :class="['rp-tag', stepStatusClass(s.status)]">{{ rowStatusText(s.status) }}</span></td>
                <td class="mono">{{ s.assertionPassed }}/{{ s.assertionCount }}</td>
                <td class="mono">{{ fmtMs(s.durationMs) }}</td>
                <td>
                  <button v-if="s.assertions.length || s.extracts.length || s.error"
                          class="rp-toggle" :data-testid="`report-step-toggle-${stepKey(s)}`"
                          @click="toggle(stepKey(s))">{{ open.has(stepKey(s)) ? '收起' : '详情' }}</button>
                </td>
              </tr>
              <tr v-if="open.has(stepKey(s))" class="rp-detail">
                <td colspan="6">
                  <p v-if="s.error" class="rp-err mono">{{ s.error }}</p>
                  <table v-if="s.assertions.length" class="rp-assert">
                    <thead><tr><th></th><th>断言目标</th><th>操作符</th><th>期望</th><th>实际</th></tr></thead>
                    <tbody>
                      <tr v-for="(a, i) in s.assertions" :key="i">
                        <td>{{ a.passed ? '✓' : '✗' }}</td>
                        <td class="mono">{{ a.target ?? a.name }}</td>
                        <td class="mono">{{ a.operator ?? '—' }}</td>
                        <td class="mono">{{ show(a.expected) }}</td>
                        <td :class="['mono', { 'rp-actual': !a.passed }]">{{ show(a.actual) }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <dl v-if="s.extracts.length" class="rp-extracts">
                    <template v-for="(x, i) in s.extracts" :key="i">
                      <dt class="mono">{{ x.target }}</dt>
                      <dd class="mono">{{ show(x.value) }}</dd>
                    </template>
                  </dl>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getExecutionEvents, getExecutionReport } from '@/api/executions'
import { httpStatusOf } from '@/api/http'
import type { ExecutionReport, ReportGroup, ReportStep } from '@/api/executions'
import { executionStatusText, rowStatusText } from '@/utils/executionStatus'

const props = defineProps<{ executionId: number; running: boolean }>()
const router = useRouter()

const report = ref<ExecutionReport | null>(null)
const loading = ref(false)
const error = ref('')
const open = ref(new Set<string>())

const POLL_MS = 3000
let timer: ReturnType<typeof setTimeout> | null = null

async function load(): Promise<void> {
  loading.value = true
  try {
    report.value = await getExecutionReport(props.executionId)
    error.value = ''
  } catch (e) {
    error.value = httpStatusOf(e) === 404 ? '执行不存在或无权查看' : '报告加载失败'
  } finally {
    loading.value = false
  }
  schedule()
}

function schedule(): void {
  if (timer) clearTimeout(timer)
  timer = null
  if (props.running) timer = setTimeout(() => { void load() }, POLL_MS)
}

watch(() => props.executionId, () => { report.value = null; open.value = new Set(); void load() },
  { immediate: true })
// 运行 → 终态:再拉一次拿最终结果,并停止轮询
watch(() => props.running, (now, before) => { if (before && !now) void load() })
onUnmounted(() => { if (timer) clearTimeout(timer) })

/** S1 失败根因直达(2026-11-12 自行级明细「查看日志」迁入):失败
 *  unit → 该 unit 的 step.failed 事件 (ts,id) 为锚,深链进混合时间轴
 *  上下文窗口。锚点查询限定本 unit(按全局前 50 条找锚会锚到别的
 *  unit 的失败点);取末条(有重试时锚在最终那次失败 —— 首次失败的
 *  根因上下文已被后续重试日志推远);查不到 → 退化为 unit 过滤视图,
 *  不跨 unit 回落。 */
async function gotoFailureLogs(): Promise<void> {
  const exId = props.executionId
  const uid = report.value?.failure?.unit ?? ''
  try {
    const r = await getExecutionEvents(exId, {
      kind: 'event', event_type: 'step.failed', limit: 50,
      ...(uid ? { unit: uid } : {}),
    })
    const hit = r.items[r.items.length - 1]
    const query: Record<string, string> = { view: 'mixed' }
    if (hit) {
      query.around_ts = hit.ts
      query.around_id = String(hit.id)
      query.n = '80'
    }
    if (uid) query.unit = uid
    void router.push({ path: `/executions/${exId}/events`, query })
  } catch {
    void router.push(`/executions/${exId}/events`)
  }
}

function toggle(key: string): void {
  const s = new Set(open.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  open.value = s
}

function stepKey(s: ReportStep): string {
  return `${s.rowSeq}:${s.unit}:${s.attempt}:${s.stepId}`
}
function stepTitle(s: ReportStep): string {
  // 步骤说明优先(编排时写的人话),否则步骤 id
  return s.description || s.stepName || s.stepId
}
function groupTitle(g: ReportGroup): string {
  if (g.rowSeq < 0) return `单元 ${g.unit || '—'}`
  const ds = g.datasetId ? `数据集 ${g.datasetId} · 第 ${g.rowIndex} 行` : '场景本体'
  return `行 #${g.rowSeq} · ${ds}${g.rep ? ` · 重复 ${g.rep}` : ''}`
}
function groupLabelOf(s: ReportStep): string {
  const g = report.value?.groups.find((x) =>
    s.rowSeq >= 0 ? x.rowSeq === s.rowSeq : x.unit === s.unit)
  return g ? groupTitle(g) : (s.unit || '—')
}
function isFail(status: string): boolean {
  return status === 'failed' || status === 'error'
}
function stepStatusClass(status: string): string {
  if (status === 'passed') return 'status-done'
  if (isFail(status)) return 'status-failed'
  return 'status-canceled'
}
function groupStatusClass(status: string): string {
  if (status === 'passed') return 'status-done'
  if (status === 'queued' || status === 'dispatched') return 'status-running'
  if (status === 'canceled' || status === 'skipped') return 'status-canceled'
  return 'status-failed'
}
function slotLog(slot: number): string {
  return slot === 0 ? 'server-engine.log' : `server-engine-${slot}.log`
}
function fmtMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)}s`
}
function show(v: unknown): string {
  if (v === undefined) return '—'
  if (typeof v === 'string') return JSON.stringify(v)
  try { return JSON.stringify(v) } catch { return String(v) }
}
function pretty(v: unknown): string {
  if (v === undefined || v === null) return '(空)'
  if (typeof v === 'string') return v
  try { return JSON.stringify(v, null, 2) } catch { return String(v) }
}
function hasKeys(v: unknown): boolean {
  return !!v && typeof v === 'object' && Object.keys(v as object).length > 0
}
</script>

<style scoped>
.rp { display: flex; flex-direction: column; gap: 14px; margin-bottom: 16px; }
.rp-empty {
  @apply text-label font-normal;
  margin: 0; padding: 18px; color: var(--color-text-tertiary);
  background: #fff; border: 0.5px dashed #e2e8f0; border-radius: 8px;
}
.rp-error { color: #dc2626; }
.rp-summary {
  display: flex; flex-wrap: wrap; gap: 8px 20px; align-items: center;
  padding: 12px 16px; background: #fff; border: 0.5px solid #e2e8f0; border-radius: 8px;
  @apply text-label font-normal;
}
.rp-verdict { @apply text-label font-semibold; padding: 2px 10px; border-radius: 4px; }
.rp-kv { color: var(--color-text-secondary); }
.rp-kv b { color: var(--color-text-primary); font-weight: 600; }
.rp-failure {
  padding: 14px 16px; background: #fff; border: 0.5px solid #fecaca;
  border-left: 3px solid #dc2626; border-radius: 8px;
  display: flex; flex-direction: column; gap: 8px;
}
.rp-failure-head { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: baseline; }
/* S1 深链入口(自「查看日志」迁入):链接式按钮,推到行尾 */
.rp-locate {
  @apply text-label font-normal; color: #2f6fed; background: none;
  border: 0; cursor: pointer; padding: 0; margin-left: auto; white-space: nowrap;
}
.rp-step-title { color: var(--color-text-primary); font-weight: 600; }
.rp-dim { color: var(--color-text-tertiary); @apply text-label font-normal; }
.rp-pad { padding: 8px 12px; margin: 0; }
.rp-call { margin: 0; color: var(--color-text-secondary); @apply text-label font-normal; }
.rp-err {
  margin: 0; padding: 6px 10px; color: #991b1b; background: #fef2f2;
  border-radius: 4px; @apply text-label font-normal; white-space: pre-wrap; word-break: break-all;
}
.rp-tag { @apply text-micro font-semibold; display: inline-flex; padding: 2px 8px; border-radius: 4px; white-space: nowrap; }
.rp-assert, .rp-steps {
  width: 100%; border-collapse: collapse; @apply text-label font-normal; background: #fff;
}
.rp-assert th, .rp-steps th {
  text-align: left; padding: 6px 10px; color: var(--color-text-secondary);
  font-weight: 500; border-bottom: 0.5px solid #e2e8f0;
}
.rp-assert td, .rp-steps td { padding: 6px 10px; border-bottom: 0.5px solid #f1f5f9; vertical-align: top; }
.rp-actual { color: #dc2626; font-weight: 600; }
.rp-evidence { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.rp-ev-col h4 { margin: 0 0 4px; @apply text-label font-semibold; color: var(--color-text-secondary); }
.rp-ev-col p { margin: 0 0 4px; word-break: break-all; }
.rp-ev-col pre {
  margin: 0 0 6px; padding: 8px 10px; max-height: 260px; overflow: auto;
  background: #f8fafc; border: 0.5px solid #e2e8f0; border-radius: 4px;
  @apply text-micro font-normal; white-space: pre-wrap; word-break: break-all;
}
.rp-group { background: #fff; border: 0.5px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
.rp-group-head {
  display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center;
  padding: 8px 12px; background: #f8fafc; border-bottom: 0.5px solid #e2e8f0;
}
.rp-group-title { @apply text-label font-semibold; color: var(--color-text-primary); }
.rp-row-fail td { background: #fffafa; }
.rp-call-cell { max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-text-secondary); }
.rp-detail td { background: #fcfcfd; }
.rp-toggle { @apply text-label font-normal; color: #2f6fed; background: none; border: 0; cursor: pointer; padding: 0; }
.rp-extracts { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; margin: 8px 0 0; }
.rp-extracts dt { color: var(--color-text-secondary); }
.rp-extracts dd { margin: 0; word-break: break-all; }
.mono { font-family: var(--font-mono, monospace); }
</style>

<style src="@/styles/status-colors.css"></style>
