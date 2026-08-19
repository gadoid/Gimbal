<!-- CaseDetailView.vue — 用例详情页(数据驱动的可读渲染)
     /cases/:caseId

     定位:不做任何固定文案的"说明书",而是把该用例的真实数据
     (场景 meta/config.vars/retry · case env/auth · 数据集 rows ·
      每步的 api/request/strategy)完整、按人阅读友好的排版渲染出来。
     数据里有什么就渲染什么;没有的块不出现。
-->
<template>
  <section class="doc" v-loading="loading">
    <!-- ── 题头 ───────────────────────────────────────────── -->
    <header class="head">
      <div class="head-top">
        <h1 class="title">{{ currentCase?.name || '未命名用例' }}</h1>
        <span class="doc-no mono">{{ shortId }}</span>
      </div>
      <p v-if="scenario?.meta?.description" class="desc">{{ scenario.meta.description }}</p>
      <dl class="meta-grid">
        <div><dt>用例编号</dt><dd class="mono">{{ caseId }}</dd></div>
        <div><dt>所属场景</dt>
          <dd>
            <button class="linklike" @click="goScenario()">{{ scenario?.meta?.name || scenarioId || '—' }}</button>
          </dd>
        </div>
        <div><dt>模块 / 系统</dt><dd>{{ moduleText }}</dd></div>
        <div><dt>优先级</dt><dd>{{ priorityText }}</dd></div>
        <div><dt>标签</dt>
          <dd v-if="metaTags.length">{{ metaTags.join(' · ') }}</dd>
          <dd v-else>—</dd>
        </div>
        <div><dt>编制人</dt><dd>{{ scenario?.meta?.owner || scenario?.meta?.author || currentCase?.createdBy || '—' }}</dd></div>
        <div><dt>最后运行</dt><dd>{{ lastRunText }}</dd></div>
        <div><dt>更新时间</dt><dd>{{ updateTimeText }}</dd></div>
      </dl>
      <div class="head-actions">
        <button class="btn primary" @click="goRun">▶ 立即运行</button>
        <button class="btn" @click="goScenario(2)">修改执行规格</button>
        <button class="btn" @click="router.push(caseDataSetsUrl(caseId))">管理数据集</button>
        <button class="btn ghost" @click="router.back()">返回</button>
      </div>
    </header>

    <template v-if="currentCase">
      <!-- ── 摘要(由数据统计生成)──────────────────────────── -->
      <section class="summary">
        <span v-for="s in summaryStats" :key="s.label" class="sum-item">
          <b class="mono">{{ s.value }}</b> {{ s.label }}
        </span>
      </section>

      <!-- ── 执行规格 ─────────────────────────────────────── -->
      <article class="chapter">
        <h2>执行规格</h2>
        <table class="spec-table">
          <tbody>
            <tr>
              <th>执行环境</th>
              <td><code class="mono">{{ currentCase.env || '（未指定）' }}</code></td>
            </tr>
            <tr>
              <th>登录身份</th>
              <td>
                <code class="mono">{{ currentCase.auth?.name || '（无）' }}</code>
                <span v-if="currentCase.auth?.type" class="dim"> · {{ currentCase.auth.type }}</span>
              </td>
            </tr>
            <tr v-if="retryText">
              <th>失败重试</th>
              <td>{{ retryText }}</td>
            </tr>
            <tr v-if="timePolicyText">
              <th>时间策略</th>
              <td>{{ timePolicyText }}</td>
            </tr>
            <tr>
              <th>输入规模</th>
              <td>数据集 {{ dataSets.length }} 组 · {{ totalRows }} 行 · 每行 1 次完整执行</td>
            </tr>
          </tbody>
        </table>
      </article>

      <!-- ── 变量(仅当有变量)────────────────────────────── -->
      <article v-if="varEntries.length" class="chapter">
        <h2>变量 <span class="count">{{ varEntries.length }}</span></h2>
        <table class="kv-table">
          <tbody>
            <tr v-for="[k, v] in varEntries" :key="k">
              <th class="mono">{{ k }}</th>
              <td><code class="mono">{{ prettyVal(v) }}</code></td>
            </tr>
          </tbody>
        </table>
      </article>

      <!-- ── 数据集 ───────────────────────────────────────── -->
      <article class="chapter">
        <h2>数据集 <span class="count">{{ dataSets.length }}</span></h2>
        <p v-if="dataSets.length" class="hint dim">
          每组数据的每一行都是一次独立运行的输入;行内字段以
          <code class="mono">${'{'}var.字段名{'}'}</code> 方式注入各步骤。
        </p>
        <div v-for="(d, i) in dataSets" :key="d.datasetId" class="ds-entry">
          <div class="ds-title">
            <span class="ds-idx">{{ i + 1 }}</span>
            <b>{{ d.name }}</b>
            <span class="ds-count">{{ d.rowCount }} 行</span>
            <StatusBadge v-if="d.lastRunStatus" :status="d.lastRunStatus" />
            <span class="mono dim ds-id">{{ d.datasetId }}</span>
          </div>
          <p v-if="dsFields(d).length" class="hint dim">字段:{{ dsFields(d).join(' · ') }}</p>
          <pre v-if="d.preview?.length" class="code">{{ JSON.stringify(d.preview, null, 2) }}</pre>
          <p v-else class="hint dim">（空数据集 — 运行时产生 1 次空输入执行）</p>
        </div>
        <p v-if="!dataSets.length" class="notice warn">
          ⚠ 尚无数据集。请先
          <button class="linklike" @click="router.push(caseDataSetsUrl(caseId))">创建一组数据</button>。
        </p>
      </article>

      <!-- ── 操作步骤(全量请求规格)────────────────────────── -->
      <article class="chapter">
        <h2>业务过程 <span class="count">{{ steps.length }} 步</span></h2>
        <ol class="proc">
          <li v-for="(s, i) in steps" :key="i" class="proc-step">
            <div class="proc-head">
              <span class="proc-no">{{ i + 1 }}</span>
              <b class="proc-name">{{ stepName(s) }}</b>
              <span v-if="methodOf(s)" class="proc-method" :class="(methodOf(s) || '').toLowerCase()">{{ methodOf(s) }}</span>
              <span v-if="serviceOf(s)" class="proc-service mono">{{ serviceOf(s) }}</span>
              <span v-if="pathOf(s)" class="mono proc-path">{{ pathOf(s) }}</span>
            </div>
            <p v-if="descOf(s)" class="proc-desc">{{ descOf(s) }}</p>

            <!-- 入参结构概要(默认收起,点击可查完整请求结构) -->
            <div v-if="hasBody(s)" class="sub">
              <div class="sub-title">入参 <span class="count">{{ bodyFields(s).join(' · ') }}</span></div>
              <details class="req-detail">
                <summary>查看完整请求结构</summary>
                <pre class="code">{{ prettyBody(s) }}</pre>
              </details>
            </div>

            <!-- 业务结果:校验 / 记录 / 赋值 -->
            <div v-for="g in strategyGroups(s)" :key="g.kind" class="sub">
              <div class="sub-title">{{ g.label }} <span class="count">{{ g.items.length }}</span></div>
              <ul class="st-list">
                <li v-for="(it, j) in g.items" :key="j" class="st-item">
                  <span class="st-kind mono">{{ g.kind }}</span>
                  <code class="mono st-expr">{{ strategyText(it) }}</code>
                  <span v-if="strategyNote(it)" class="dim st-note">{{ strategyNote(it) }}</span>
                </li>
              </ul>
            </div>
          </li>
        </ol>
        <p v-if="!steps.length" class="notice warn">
          ⚠ 所属场景暂无编排步骤。请先到
          <button class="linklike" @click="goScenario()">场景编排器</button> 完成步骤设计。
        </p>
      </article>

      <!-- ── 附注 ─────────────────────────────────────────── -->
      <footer v-if="scenario?.meta?.version || scenario?.meta?.createTime" class="colophon">
        <p class="colophon-line mono">
          <template v-if="scenario?.meta?.version">v{{ scenario.meta.version }} · </template>
          <template v-if="scenario?.meta?.createTime">{{ scenario.meta.createTime }}</template>
          · 本页由平台根据最新编排数据自动生成
        </p>
      </footer>
    </template>

    <div v-else-if="!loading" class="notice fatal">
      用例不存在或无权查看。
      <button class="linklike" @click="router.push('/scenarios')">返回场景库</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StatusBadge from '@/components/StatusBadge.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { caseDataSetsUrl, composerUrl } from '@/utils/links'
import { relTime } from '@/utils/datetime'
import type { ExtractView, AssignView, AssertionView } from '@/types/plate'

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()
const caseId = route.params.caseId as string

const loading = ref(false)

const currentCase = computed(() => store.caseById(caseId))
const scenarioId = computed(() => currentCase.value?.scenarioId ?? '')
const scenario = computed(() => store.scenarioById(scenarioId.value))
const dataSets = computed(() => store.dataSetsOfCase(caseId))
const totalRows = computed(() => dataSets.value.reduce((s, d) => s + d.rowCount, 0))
const steps = computed(() => (scenario.value?.steps ?? []) as unknown[])

// ── 防御式读取(steps 为 plate 形,但字段可能缺失)────────────
function pick<T = unknown>(s: unknown, ...path: string[]): T | undefined {
  let cur: unknown = s
  for (const key of path) {
    if (!cur || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[key]
  }
  return cur as T | undefined
}
const stepName = (s: unknown) => pick<string>(s, 'name') || pick<string>(s, 'id') || `步骤 ${(steps.value.indexOf(s) + 1) || '·'}`
const methodOf = (s: unknown) => pick<string>(s, 'api', 'method') || pick<string>(s, 'request', 'method')
const pathOf = (s: unknown) => pick<string>(s, 'api', 'path') || pick<string>(s, 'request', 'path')
const serviceOf = (s: unknown) => pick<string>(s, 'api', 'service')
const descOf = (s: unknown) => pick<string>(s, 'description')
const bodyOf = (s: unknown) => pick<unknown>(s, 'request', 'body')
const hasBody = (s: unknown) => {
  const b = bodyOf(s)
  return b != null && b !== '' && !(typeof b === 'object' && Object.keys(b as object).length === 0)
}
const prettyBody = (s: unknown) => {
  const b = bodyOf(s)
  return typeof b === 'string' ? b : JSON.stringify(b, null, 2)
}
/** 入参字段名概要(业务视角:只看传了什么,不看具体值) */
const bodyFields = (s: unknown): string[] => {
  const b = bodyOf(s)
  if (typeof b === 'string') return b.length <= 40 ? [b] : [`${b.slice(0, 40)}…`]
  if (Array.isArray(b)) return [`[${b.length} 项]`]
  if (b && typeof b === 'object') {
    return Object.entries(b as Record<string, unknown>).map(([k, v]) =>
      v && typeof v === 'object' ? `${k}{…}` : k,
    )
  }
  return []
}
const strategiesOf = (s: unknown) => (pick<unknown[]>(s, 'strategy') || []) as Array<Record<string, unknown>>

// ── 摘要:全部由数据统计 ─────────────────────────────────────
const assertionCount = computed(() =>
  steps.value.reduce((n, s) => n + strategiesOf(s).filter(t => t.kind === 'assertion').length, 0),
)
const extractCount = computed(() =>
  steps.value.reduce((n, s) => n + strategiesOf(s).filter(t => t.kind === 'extract').length, 0),
)
const summaryStats = computed(() => {
  const items: { label: string; value: number | string }[] = [
    { label: '步骤', value: steps.value.length },
    { label: '断言', value: assertionCount.value },
    { label: '变量提取', value: extractCount.value },
    { label: '场景变量', value: varEntries.value.length },
    { label: '数据集', value: dataSets.value.length },
    { label: '输入行', value: totalRows.value },
  ]
  const sys = scenario.value?.meta?.system || []
  if (sys.length) items.push({ label: `涉及系统 ${sys.join('/')}`, value: sys.length })
  return items
})

// ── 文案推导 ────────────────────────────────────────────────
const shortId = computed(() => (caseId.length > 18 ? `${caseId.slice(0, 18)}…` : caseId))
const moduleText = computed(() => {
  const m = scenario.value?.meta
  if (!m) return '—'
  return [m.module || '未分类', (m.system || []).join(' / ') || '—'].filter(Boolean).join(' / ')
})
const metaTags = computed(() => (scenario.value?.meta?.tags || []).filter(Boolean))
const priorityText = computed(() => {
  const p = scenario.value?.meta?.priority
  if (p === 1) return 'P1 · 核心链路'
  if (p === 2) return 'P2 · 常规'
  if (p === 3) return 'P3 · 低频'
  return p != null ? `P${p}` : '未定级'
})
const lastRunText = computed(() => {
  const c = currentCase.value
  if (!c?.lastRunStatus) return '从未运行'
  const label = c.lastRunStatus === 'PASS' ? '通过' : c.lastRunStatus === 'FAIL' ? '失败' : '跳过'
  return `${label} · ${relTime(c.lastRunAt)}`
})
const updateTimeText = computed(() => {
  const t = (scenario.value as unknown as { updateTime?: string } | undefined)?.updateTime
    || scenario.value?.meta?.createTime
  return t ? relTime(t) : '—'
})
const retryText = computed(() => {
  // case 自身 retry 优先;否则展示场景级 config.retry
  const r = (currentCase.value as unknown as { retry?: { maxAttempts?: number; intervalMs?: number } } | undefined)?.retry
    || (scenario.value?.config as { retry?: { maxAttempts?: number; backoffSeconds?: number } } | undefined)?.retry
  if (!r?.maxAttempts) return ''
  const interval = (r as { intervalMs?: number; backoffSeconds?: number }).intervalMs
    ?? ((r as { backoffSeconds?: number }).backoffSeconds != null ? `${(r as { backoffSeconds?: number }).backoffSeconds}s` : undefined)
  return `失败后重试 ${r.maxAttempts} 次${interval != null ? ` · 间隔 ${interval}` : ''}`
})
const timePolicyText = computed(() => {
  const tp = (scenario.value?.config as { timePolicy?: { kind?: string; seconds?: number } } | undefined)?.timePolicy
  if (!tp) return ''
  return tp.kind === 'timeout' ? `超时上限 ${tp.seconds}s` : '仅记录耗时'
})

// ── 变量清单 ────────────────────────────────────────────────
const varEntries = computed<[string, unknown][]>(() =>
  Object.entries(((scenario.value?.config as Record<string, unknown> | undefined)?.vars as Record<string, unknown>) || {}),
)
const prettyVal = (v: unknown) => (typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v))

// ── 数据集字段 ──────────────────────────────────────────────
function dsFields(d: { preview?: Record<string, unknown>[] }): string[] {
  return Object.keys(d.preview?.[0] ?? {})
}

// ── 策略分组渲染 ────────────────────────────────────────────
const GROUP_DEFS = [
  { kind: 'assertion', label: '校验' },
  { kind: 'extract', label: '记录' },
  { kind: 'assign', label: '赋值' },
] as const
function strategyGroups(s: unknown) {
  const all = strategiesOf(s)
  return GROUP_DEFS
    .map(g => ({ ...g, items: all.filter(t => t.kind === g.kind) }))
    .filter(g => g.items.length > 0)
}
function strategyText(t: Record<string, unknown>): string {
  if (t.kind === 'extract') {
    const e = t as unknown as ExtractView
    return `${e.target} ⇐ ${e.expression}`
  }
  if (t.kind === 'assign') {
    const a = t as unknown as AssignView
    return `${a.target} = ${typeof a.source === 'object' ? JSON.stringify(a.source) : String(a.source)}`
  }
  const a = t as unknown as AssertionView
  const exp = a.expected !== undefined
    ? (typeof a.expected === 'object' ? JSON.stringify(a.expected) : String(a.expected))
    : ''
  return `${a.target} ${a.operator}${exp ? ` ${exp}` : ''}`
}
function strategyNote(t: Record<string, unknown>): string {
  const parts: string[] = []
  if (t.name) parts.push(String(t.name))
  if (t.kind === 'assertion' && (t as AssertionView).soft) parts.push('soft')
  if (t.message) parts.push(String(t.message))
  return parts.join(' · ')
}

// ── 跳转 ────────────────────────────────────────────────────
function goScenario(step = 4) {
  if (scenarioId.value) router.push(composerUrl(scenarioId.value, step))
}
/** 运行统一走编排器的 RunDialog(数据集选择/次数/并发/凭证合并策略) */
function goRun() {
  if (scenarioId.value) router.push(composerUrl(scenarioId.value))
}

onMounted(async () => {
  loading.value = true
  try {
    if (!store.cases.length) await store.fetchCases()
    if (currentCase.value && !store.scenarios.length) await store.fetchScenarios()
    await store.fetchDataSets()
  } catch (e) {
    showError('加载用例详情', undefined, (e as Error).message)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* 通用文档排版:窄幅、细线表格、代码块;内容随数据伸缩 */
.doc {
  max-width: 920px;
  padding: 36px 44px 64px;
  margin: 0 auto;
  font-size: 13px;
  line-height: 1.8;
  color: #1f2937;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  box-sizing: border-box;
  min-height: calc(100vh - 48px);
}

/* 题头 */
.head { padding-bottom: 18px; border-bottom: 2px solid #111827; }
.head-top { display: flex; gap: 16px; align-items: baseline; justify-content: space-between; }
.title {
  margin: 0;
  font-family: 'Noto Serif SC', 'Songti SC', serif;
  font-size: 26px;
  font-weight: 900;
  color: #111827;
}
.doc-no { font-size: 11px; color: #9ca3af; }
.desc { margin: 6px 0 14px; font-size: 12.5px; color: #4b5563; }
.meta-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px 24px;
  margin: 0;
}
.meta-grid > div { display: flex; gap: 6px; font-size: 12px; min-width: 0; }
.meta-grid dt { flex-shrink: 0; color: #9ca3af; }
.meta-grid dt::after { content: "："; }
.meta-grid dd { margin: 0; word-break: break-all; }
.head-actions { display: flex; gap: 8px; margin-top: 16px; }

.btn {
  padding: 6px 14px;
  font-size: 12px;
  color: #374151;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 3px;
  cursor: pointer;
}
.btn:hover { border-color: #111827; }
.btn.primary { color: #fff; background: #111827; border-color: #111827; }
.btn.primary:hover { background: #1f2937; }
.btn.ghost { border-color: transparent; color: #6b7280; }

/* 摘要条 */
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 28px;
  padding: 12px 2px;
  border-bottom: 1px solid #f3f4f6;
}
.sum-item { font-size: 12px; color: #6b7280; }
.sum-item b { font-size: 15px; color: #111827; }

/* 章节 */
.chapter { padding: 22px 0 4px; }
.chapter h2 {
  display: flex;
  gap: 8px;
  align-items: baseline;
  margin: 0 0 10px;
  font-family: 'Noto Serif SC', 'Songti SC', serif;
  font-size: 16px;
  font-weight: 700;
  color: #111827;
}
.chapter h2::before {
  content: "";
  display: inline-block;
  width: 4px;
  height: 14px;
  background: #111827;
  transform: translateY(1px);
}
.count {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 400;
  color: #9ca3af;
}
.hint { margin: 0 0 6px; font-size: 12px; }
.dim { color: #9ca3af; }

/* 表格 */
.spec-table, .kv-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.spec-table th, .spec-table td,
.kv-table th, .kv-table td {
  padding: 7px 12px;
  border: 1px solid #e5e7eb;
  vertical-align: top;
  text-align: left;
}
.spec-table th, .kv-table th {
  font-weight: 700;
  color: #374151;
  background: #f9fafb;
  white-space: nowrap;
}
.spec-table th { width: 96px; }
.kv-table.tight th, .kv-table.tight td { padding: 4px 10px; font-size: 12px; }
.kv-table th { width: 200px; }

/* 代码块 */
.code {
  margin: 6px 0;
  padding: 10px 12px;
  overflow: auto;
  max-height: 220px;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.6;
  color: #374151;
  background: #f9fafb;
  border: 1px solid #f3f4f6;
  border-radius: 3px;
}

/* 数据集条目 */
.ds-entry { padding: 10px 0; border-bottom: 1px dashed #e5e7eb; }
.ds-entry:last-of-type { border-bottom: 0; }
.ds-title { display: flex; gap: 10px; align-items: center; font-size: 12.5px; flex-wrap: wrap; }
.ds-idx {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: #111827;
  border: 1px solid #111827;
  border-radius: 50%;
}
.ds-count {
  padding: 0 6px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  background: #f3f4f6;
  border-radius: 2px;
}
.ds-id { margin-left: auto; font-size: 10px; }

/* 步骤 */
.proc { padding: 0; margin: 0; list-style: none; }
.proc-step { padding: 12px 0; border-bottom: 1px dotted #f3f4f6; }
.proc-step:last-of-type { border-bottom: 0; }
.proc-head { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; min-width: 0; }
.proc-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: #374151;
  border-radius: 50%;
}
.proc-name { font-size: 13px; }
.proc-method {
  padding: 0 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: #6b7280;
  border-radius: 2px;
  line-height: 16px;
}
.proc-method.get { background: #1d4ed8; }
.proc-method.post { background: #047857; }
.proc-method.put, .proc-method.patch { background: #b45309; }
.proc-method.delete { background: #b91c1c; }
.proc-service {
  padding: 0 6px;
  font-size: 10.5px;
  color: #4b5563;
  background: #f3f4f6;
  border-radius: 2px;
  line-height: 16px;
}
.proc-path { font-size: 11px; color: #6b7280; word-break: break-all; }
.proc-desc { margin: 4px 0 0 30px; font-size: 12px; color: #4b5563; }

/* 步骤内子块(入参/策略) */
.sub { margin: 8px 0 0 30px; }
.req-detail { margin-top: 2px; }
.req-detail summary {
  font-size: 11px;
  color: #1d4ed8;
  cursor: pointer;
  user-select: none;
}
.req-detail summary:hover { text-decoration: underline; }
.req-detail[open] summary { margin-bottom: 2px; }
.sub-title {
  margin-bottom: 4px;
  font-size: 11.5px;
  font-weight: 700;
  color: #6b7280;
  letter-spacing: 0.08em;
}
.st-list { padding: 0; margin: 0; list-style: none; }
.st-item {
  display: flex;
  gap: 8px;
  align-items: baseline;
  flex-wrap: wrap;
  padding: 3px 0;
  font-size: 12px;
}
.st-kind {
  flex-shrink: 0;
  padding: 0 5px;
  font-size: 10px;
  color: #4b5563;
  background: #f3f4f6;
  border-radius: 2px;
}
.st-expr { word-break: break-all; }
.st-note { font-size: 11px; }

/* 提示框 */
.notice {
  padding: 10px 14px;
  font-size: 12px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 3px;
}
.notice.fatal {
  margin-top: 32px;
  background: #fef2f2;
  border-color: #fecaca;
}

/* 附注 */
.colophon { padding-top: 20px; margin-top: 16px; border-top: 1px solid #e5e7eb; }
.colophon-line { margin: 0; font-size: 11px; color: #9ca3af; text-align: right; }

.mono { font-family: var(--font-mono); }
.linklike {
  padding: 0;
  font: inherit;
  color: #1d4ed8;
  background: transparent;
  border: 0;
  cursor: pointer;
}
.linklike:hover { text-decoration: underline; }

@media (max-width: 720px) {
  .doc { padding: 22px 16px 48px; }
  .meta-grid { grid-template-columns: 1fr 1fr; }
  .title { font-size: 20px; }
  .sub { margin-left: 0; }
  .proc-desc { margin-left: 0; }
}
</style>
