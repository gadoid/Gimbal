<!-- ScenarioDetailView.vue — 场景详情页(数据驱动的可读渲染)
     /scenarios/:scenarioId/detail

     定位:不做任何固定文案的"说明书",而是把该场景的真实数据
     (meta/config.vars/retry · 数据集 rows · 每步的 api/request/strategy)
     完整、按人阅读友好的排版渲染出来。数据里有什么就渲染什么;
     没有的块不出现。

     数据源全部为 composer_scenarios 的读侧结构(Scenario):
     meta / steps / config / resource + 场景名下 1:N 的数据集。
     Case 层解散后,"执行规格"(env/认证/重试)是运行时配方
     (RunDialog 中选择),不在本页持久化渲染。
-->
<template>
  <section class="doc" v-loading="loading">
    <!-- ── 题头 ───────────────────────────────────────────── -->
    <header class="head">
      <div class="head-top">
        <h1 class="title">{{ scenario?.meta?.name || '未命名场景' }}</h1>
        <span class="doc-no mono">{{ shortId }}</span>
      </div>
      <p v-if="scenario?.meta?.description" class="desc">{{ scenario.meta.description }}</p>
      <dl class="meta-grid">
        <div><dt>场景编号</dt><dd class="mono">{{ scenarioId }}</dd></div>
        <div><dt>模块 / 系统</dt><dd>{{ moduleText }}</dd></div>
        <div><dt>优先级</dt><dd>{{ priorityText }}</dd></div>
        <div><dt>标签</dt>
          <dd v-if="metaTags.length">{{ metaTags.join(' · ') }}</dd>
          <dd v-else>—</dd>
        </div>
        <div><dt>编制人</dt><dd>{{ scenario?.meta?.author || scenario?.meta?.owner || '—' }}</dd></div>
        <div><dt>数据规模</dt><dd>数据集 {{ dataSets.length }} 组 · {{ totalRows }} 行</dd></div>
        <div><dt>最后编辑</dt><dd>{{ updateTimeText }}</dd></div>
      </dl>
      <div class="head-actions">
        <button class="btn primary" @click="goRun">▶ 立即运行</button>
        <button class="btn" @click="goScenario(4)">修改编排</button>
        <button class="btn" @click="router.push(scenarioDataSetsUrl(scenarioId))">管理数据集</button>
        <button class="btn ghost" @click="router.back()">返回</button>
      </div>
    </header>

    <template v-if="scenario">
      <!-- ── 摘要(由数据统计生成)──────────────────────────── -->
      <section class="summary">
        <span v-for="s in summaryStats" :key="s.label" class="sum-item">
          <b class="mono">{{ s.value }}</b> {{ s.label }}
        </span>
      </section>

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
            <span class="mono dim ds-id">{{ d.datasetId }}</span>
          </div>
          <p v-if="dsFields(d).length" class="hint dim">字段:{{ dsFields(d).join(' · ') }}</p>
          <pre v-if="d.preview?.length" class="code">{{ JSON.stringify(d.preview, null, 2) }}</pre>
          <p v-else class="hint dim">（空数据集 — 运行时产生 1 次空输入执行）</p>
        </div>
        <p v-if="!dataSets.length" class="notice warn">
          ⚠ 尚无数据集。请先
          <button class="linklike" @click="router.push(scenarioDataSetsUrl(scenarioId))">创建一组数据</button>。
        </p>
      </article>

      <!-- ── 操作步骤(全量请求规格)────────────────────────── -->
      <article class="chapter">
        <h2>业务过程 <span class="count">{{ steps.length }} 步</span></h2>
        <ol class="proc">
          <li v-for="(s, i) in steps" :key="i" class="proc-step">
            <div class="proc-head">
              <span class="proc-no">{{ i + 1 }}</span>
              <b class="proc-name">{{ stepName(s, i) }}</b>
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
          ⚠ 该场景暂无编排步骤。请先到
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
      场景不存在或无权查看。
      <button class="linklike" @click="router.push('/scenarios')">返回场景库</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { composerUrl, scenarioDataSetsUrl } from '@/utils/links'
import { relTime } from '@/utils/datetime'
import type { ExtractView, AssignView, AssertionView } from '@/types/plate'

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()
const scenarioId = route.params.scenarioId as string

const loading = ref(false)

const scenario = computed(() => store.scenarioById(scenarioId))
const dataSets = computed(() => store.dataSetsOfScenario(scenarioId))
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
const stepName = (s: unknown, i: number) =>
  pick<string>(s, 'name') || pick<string>(s, 'id') || `步骤 ${i + 1}`
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
  steps.value.reduce((n: number, s) => n + strategiesOf(s).filter(t => t.kind === 'assertion').length, 0),
)
const extractCount = computed(() =>
  steps.value.reduce((n: number, s) => n + strategiesOf(s).filter(t => t.kind === 'extract').length, 0),
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
const shortId = computed(() => (scenarioId.length > 18 ? `${scenarioId.slice(0, 18)}…` : scenarioId))
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
const updateTimeText = computed(() => {
  const t = scenario.value?.meta?.updateTime || scenario.value?.meta?.createTime
  return t ? relTime(t) : '—'
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
  if (t.kind === 'assertion' && (t as unknown as AssertionView).soft) parts.push('soft')
  if (t.message) parts.push(String(t.message))
  return parts.join(' · ')
}

// ── 跳转 ────────────────────────────────────────────────────
function goScenario(step = 4) {
  router.push(composerUrl(scenarioId, step))
}
/** 运行统一走编排器的 RunDialog(数据集/次数并发/用户与服务绑定) */
function goRun() {
  router.push(composerUrl(scenarioId))
}

onMounted(async () => {
  loading.value = true
  try {
    if (!store.scenarios.length) await store.fetchScenarios()
    await store.fetchDataSets(scenarioId)
  } catch (e) {
    showError('加载场景详情', undefined, (e as Error).message)
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
.btn:hover { color: #111827; border-color: #9ca3af; }
.btn.primary {
  color: #fff;
  background: #111827;
  border-color: #111827;
}
.btn.primary:hover { background: #374151; }
.btn.ghost { border-color: transparent; color: #6b7280; }
.btn.ghost:hover { color: #374151; border-color: #d1d5db; }
.linklike {
  padding: 0;
  font: inherit;
  color: #4338ca;
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}

/* 摘要 */
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 28px;
  padding: 14px 0;
  font-size: 12px;
  color: #4b5563;
  border-bottom: 1px solid #f3f4f6;
}
.sum-item b { font-size: 16px; font-weight: 700; color: #111827; margin-right: 4px; }

/* 章节 */
.chapter { padding: 22px 0 6px; }
.chapter > h2 {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 700;
  color: #111827;
  border-left: 3px solid #111827;
  padding-left: 10px;
}
.count {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
}
.hint { margin: 4px 0 8px; font-size: 12px; }

/* 表格 */
.kv-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.kv-table th, .kv-table td {
  padding: 7px 12px;
  text-align: left;
  vertical-align: top;
  border: 1px solid #f3f4f6;
}
.kv-table th {
  width: 220px;
  font-weight: 500;
  color: #6b7280;
  background: #fafafa;
}

/* 数据集 */
.ds-entry {
  margin: 10px 0;
  padding: 10px 14px;
  border: 1px solid #f3f4f6;
  border-radius: 4px;
}
.ds-title { display: flex; gap: 8px; align-items: center; }
.ds-idx {
  font-size: 11px;
  color: #fff;
  background: #111827;
  border-radius: 2px;
  padding: 1px 6px;
}
.ds-count {
  font-size: 11px;
  color: #6b7280;
  font-family: var(--font-mono, monospace);
}
.ds-id { font-size: 10px; margin-left: auto; }

/* 业务过程 */
.proc { margin: 0; padding: 0; list-style: none; }
.proc-step {
  margin: 14px 0;
  padding: 12px 16px;
  border: 1px solid #f3f4f6;
  border-radius: 4px;
}
.proc-head {
  display: flex;
  gap: 10px;
  align-items: baseline;
  flex-wrap: wrap;
}
.proc-no {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  color: #9ca3af;
}
.proc-name { font-size: 13px; }
.proc-method {
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 700;
  font-family: var(--font-mono, monospace);
  border-radius: 2px;
  color: #fff;
}
.proc-method.get { background: #0ea5e9; }
.proc-method.post { background: #22c55e; }
.proc-method.put { background: #f59e0b; }
.proc-method.delete { background: #ef4444; }
.proc-method.patch { background: #8b5cf6; }
.proc-service {
  font-size: 11px;
  color: #4338ca;
}
.proc-path {
  font-size: 11px;
  color: #6b7280;
  word-break: break-all;
}
.proc-desc { margin: 6px 0 0; font-size: 12px; color: #4b5563; }

.sub { margin-top: 10px; padding-top: 8px; border-top: 1px dashed #f3f4f6; }
.sub-title {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 4px;
}
.st-list { margin: 0; padding: 0; list-style: none; }
.st-item {
  display: flex;
  gap: 8px;
  align-items: baseline;
  padding: 3px 0;
  font-size: 12px;
}
.st-kind {
  font-size: 10px;
  color: #9ca3af;
}
.st-expr { font-size: 11.5px; word-break: break-all; }
.st-note { font-size: 11px; }

/* 代码块 */
.code {
  margin: 6px 0;
  padding: 10px 12px;
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  line-height: 1.6;
  color: #334155;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  border-radius: 4px;
  overflow-x: auto;
}
.req-detail summary {
  font-size: 11px;
  color: #4338ca;
  cursor: pointer;
  user-select: none;
}
.req-detail[open] summary { margin-bottom: 4px; }

/* 提示条 */
.notice {
  margin: 12px 0;
  padding: 10px 14px;
  font-size: 12px;
  border-radius: 4px;
}
.notice.warn {
  color: #92400e;
  background: #fffbeb;
  border: 1px solid #fde68a;
}
.notice.fatal {
  max-width: 400px;
  margin: 80px auto;
  text-align: center;
  color: #6b7280;
  background: #fafafa;
  border: 1px solid #f3f4f6;
}

/* 附注 */
.colophon {
  padding-top: 20px;
  margin-top: 10px;
  border-top: 1px solid #f3f4f6;
}
.colophon-line {
  margin: 0;
  font-size: 10.5px;
  color: #9ca3af;
}

</style>
