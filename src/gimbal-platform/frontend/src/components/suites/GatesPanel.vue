<!-- GatesPanel.vue — 右栏(原型 20):运行参数(并发 / 每单元重复 /
     预计 runs)+ 判定门(条件 chips,聚合模式置灰并说明)+ 横切断言
     (选择器 + 断言表单:括号段 / 单元 refs 不选=该段全部,断言只产
     kind=assertion —— 追加到命中单元策略列表尾,编译期注入)。 -->
<template>
  <div class="gpan" data-testid="suite-gates-panel">
    <section class="gpan-group">
      <p class="gpan-title">运行参数</p>
      <div class="gpan-row">
        <label class="gpan-field">
          <span>并发</span>
          <input
            type="number" min="1" max="200"
            :value="config.parallel ?? 1" :disabled="readonly"
            data-testid="suite-parallel"
            @change="num('parallel', $event)"
          />
        </label>
        <label class="gpan-field">
          <span>每单元重复</span>
          <input
            type="number" min="1" max="20"
            :value="config.nRuns ?? 1" :disabled="readonly"
            data-testid="suite-nruns"
            @change="num('nRuns', $event)"
          />
        </label>
      </div>
      <p class="gpan-note">{{ estimate }} · 上限 {{ runCap }}</p>
    </section>

    <section class="gpan-group" :class="{ off: aggregate }">
      <p class="gpan-title">
        判定门
        <span v-if="aggregate" class="gpan-off-tag">聚合模式不支持</span>
        <span v-else-if="gates.length" class="gpan-count">×{{ gates.length }}</span>
      </p>
      <p v-if="aggregate" class="gpan-off-note">
        判定门只在编排模式(串联 / 扇出 / 依赖编排)下生效;
        聚合按批次逐成员判定,无需整体门。
      </p>
      <template v-else>
        <div v-if="!gates.length" class="gpan-empty">无判定门(全部通过即通过)</div>
        <div v-for="(g, i) in gates" :key="i" class="gpan-gate">
          <span class="gpan-gate-chip" :title="gateTitle(g)">
            {{ METRIC_LABEL[g.metric] || g.metric }} {{ g.op }} {{ g.value }}
          </span>
          <button
            v-if="!readonly" type="button" class="gpan-x"
            :data-testid="`suite-gate-remove-${i}`"
            title="移除此判定门"
            @click="removeGate(i)"
          >×</button>
        </div>
        <form v-if="!readonly" class="gpan-add" @submit.prevent="addGate">
          <select v-model="draft.metric" data-testid="suite-gate-metric">
            <option v-for="(label, key) in METRIC_LABEL" :key="key" :value="key">{{ label }}</option>
          </select>
          <select v-model="draft.op">
            <option v-for="op in OPS" :key="op" :value="op">{{ op }}</option>
          </select>
          <input
            v-model="draft.value" type="number" step="any" required
            data-testid="suite-gate-value"
          />
          <button type="submit" class="gpan-add-btn" data-testid="suite-gate-add">+ 判定门</button>
        </form>
      </template>
    </section>

    <section class="gpan-group" :class="{ off: aggregate }">
      <p class="gpan-title">
        横切断言
        <span class="gpan-title-sub">编译期注入命中单元</span>
        <span v-if="aggregate" class="gpan-off-tag">聚合模式不消费</span>
        <span v-else-if="checks.length" class="gpan-count">×{{ checks.length }}</span>
      </p>
      <p v-if="aggregate" class="gpan-off-note">
        横切断言随编排执行在编译期注入命中单元;聚合走批次通道,
        逐成员按自身方案断言,不消费横切断言。
      </p>
      <template v-else>
        <div v-if="!checks.length" class="gpan-empty">无横切断言</div>
        <div
          v-for="(c, i) in checks" :key="i"
          class="gpan-check" :data-testid="`suite-check-${i}`"
        >
          <div class="gpan-check-body">
            <span class="gpan-check-on">作用于 · {{ checkScope(c) }}</span>
            <span class="gpan-check-assert mono">{{ checkAssert(c) }}</span>
          </div>
          <button
            v-if="!readonly" type="button" class="gpan-x"
            :data-testid="`suite-check-remove-${i}`"
            title="移除此横切断言"
            @click="removeCheck(i)"
          >×</button>
        </div>

        <form v-if="!readonly" class="gpan-cform" data-testid="suite-check-form" @submit.prevent="addCheck">
          <p class="gpan-form-cap">作用于</p>
          <select v-model="checkDraft.bracket" data-testid="suite-check-bracket">
            <option value="main">主体段</option>
            <option value="before">前置段</option>
            <option value="after">后置段</option>
          </select>
          <div v-if="bracketRefs.length" class="gpan-refs" data-testid="suite-check-refs">
            <button
              v-for="r in bracketRefs" :key="r" type="button"
              class="gpan-ref" :class="{ on: checkDraft.refs.includes(r) }"
              :data-testid="`suite-check-ref-${r}`"
              @click="toggleRef(r)"
            >{{ r }}</button>
          </div>
          <p class="gpan-form-hint">
            {{ checkDraft.refs.length ? '只注入所选单元' : '不选单元 = 该段全部单元' }}
          </p>

          <p class="gpan-form-cap">断言(追加到命中单元的策略列表尾)</p>
          <input
            v-model="checkDraft.target" class="gpan-w mono"
            placeholder="$.call.response.status" required
            data-testid="suite-check-target"
          />
          <div class="gpan-form-row">
            <select v-model="checkDraft.operator" data-testid="suite-check-op">
              <option v-for="(label, k) in ASSERT_OPS" :key="k" :value="k">{{ label }}</option>
            </select>
            <input
              v-if="opNeedsExpected"
              v-model="checkDraft.expected" class="gpan-w"
              :placeholder="expectedPlaceholder"
              data-testid="suite-check-expected"
            />
          </div>
          <input
            v-model="checkDraft.message" class="gpan-w"
            placeholder="失败提示(可选)"
            data-testid="suite-check-message"
          />
          <button type="submit" class="gpan-add-btn" data-testid="suite-check-add">
            + 横切断言
          </button>
        </form>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import type { SuiteModeConfig } from '@/api/suites'
import { estimateOrchRuns } from '@/utils/suiteStructure'

interface Gate { metric: string; op: string; value: number }
interface Check {
  on?: { bracket?: string; refs?: string[] }
  strategy?: Record<string, unknown>
}

const props = defineProps<{
  config: SuiteModeConfig
  members: { scenarioId: string }[]
  mode: string
  readonly?: boolean
  runCap?: number
  /** 横切断言选择器的单元名册(带角色;缺省只有主体成员可选)。 */
  roster?: { scenarioId: string; role?: string }[]
}>()

const emit = defineEmits<{
  (e: 'patch', patch: Partial<SuiteModeConfig>): void
}>()

const runCap = computed(() => props.runCap ?? 1000)
const aggregate = computed(() => props.mode === 'aggregate')

const METRIC_LABEL: Record<string, string> = {
  pass_rate: '通过率', fail_count: '失败数', total: '总单元数',
  avg_duration_ms: '平均耗时', max_duration_ms: '最长耗时',
}
const OPS = ['gte', 'lte', 'gt', 'lt', 'eq', 'ne']

/** 断言算子(执行器 AssertOperator 全表;exists/empty 不带期望值)。 */
const ASSERT_OPS: Record<string, string> = {
  eq: '等于', ne: '不等', gt: '大于', gte: '大于等于',
  lt: '小于', lte: '小于等于', in: '属于', not_in: '不属于',
  contains: '包含', not_contains: '不包含',
  exists: '存在', empty: '为空',
}

const gates = computed<Gate[]>(
  () => (props.config.gates as Gate[] | undefined) ?? [])
const checks = computed<Check[]>(
  () => (props.config.checks as Check[] | undefined) ?? [])

const estimate = computed(() => aggregate.value
  ? `聚合:${props.members.length} 个独立执行(精确 runs 在预检中按方案计算)`
  : `本次预计 ${estimateOrchRuns(props.members, props.config)} runs`)

const draft = reactive<{ metric: string; op: string; value: number | '' }>({
  metric: 'pass_rate', op: 'gte', value: 1,
})

function gateTitle(g: Gate): string {
  const metric = METRIC_LABEL[g.metric] ?? g.metric
  return `${metric} ${g.op} ${g.value}(任一门不满足 → 整体判失败)`
}

function addGate(): void {
  if (draft.value === '' || draft.value === null) return
  emit('patch', { gates: [...gates.value, {
    metric: draft.metric, op: draft.op, value: Number(draft.value) }] })
}

function removeGate(i: number): void {
  emit('patch', { gates: gates.value.filter((_, j) => j !== i) })
}

// ── 横切断言:选择器(括号段 + refs,不选 = 该段全部)+ 断言表单 ──
// 语义对执行器 CheckDecl:命中单元在编译期追加 kind=assertion 策略到
// 其策略列表尾;refs 空数组省略(= 该段全部)。
const checkDraft = reactive<{
  bracket: 'main' | 'before' | 'after'
  refs: string[]
  target: string
  operator: string
  expected: string
  message: string
}>({ bracket: 'main', refs: [], target: '', operator: 'eq', expected: '', message: '' })

/** 该段可选单元的 ref 名册(units.ref 缺省回落 scenarioId)。 */
const bracketRefs = computed<string[]>(() => {
  const roster = props.roster?.length
    ? props.roster
    : props.members.map((m) => ({ scenarioId: m.scenarioId, role: 'main' }))
  return roster
    .filter((m) => (m.role ?? 'main') === checkDraft.bracket)
    .map((m) => refOf(m.scenarioId))
})

function refOf(scenarioId: string): string {
  const units = (props.config.units as Record<string, { ref?: string }> | undefined) ?? {}
  return units[scenarioId]?.ref || scenarioId
}

function toggleRef(ref: string): void {
  checkDraft.refs = checkDraft.refs.includes(ref)
    ? checkDraft.refs.filter((r) => r !== ref)
    : [...checkDraft.refs, ref]
}

const opNeedsExpected = computed(
  () => checkDraft.operator !== 'exists' && checkDraft.operator !== 'empty')
const expectedPlaceholder = computed(() =>
  checkDraft.operator === 'in' || checkDraft.operator === 'not_in'
    ? '值1, 值2(逗号分隔)'
    : '期望值(数字 / 字符串)')

/** 宽松解析:合法 JSON 原样(number/bool/null/数组/带引号串);
 * in/not_in 落到逗号分列表;其余按字符串。 */
function parseExpected(raw: string, op: string): unknown {
  const t = raw.trim()
  if (!t || !opNeedsExpected.value) return null
  try {
    return JSON.parse(t)
  } catch {
    if (op === 'in' || op === 'not_in') {
      return t.split(',').map((s) => s.trim()).filter(Boolean)
    }
    return t
  }
}

function addCheck(): void {
  const target = checkDraft.target.trim()
  if (!target) return
  const strategy: Record<string, unknown> = {
    kind: 'assertion',
    target,
    operator: checkDraft.operator,
    expected: parseExpected(checkDraft.expected, checkDraft.operator),
  }
  if (checkDraft.message.trim()) strategy.message = checkDraft.message.trim()
  const on: { bracket: string; refs?: string[] } = { bracket: checkDraft.bracket }
  if (checkDraft.refs.length) on.refs = [...checkDraft.refs]
  emit('patch', { checks: [...checks.value, { on, strategy }] })
  // 选择器保留(连续配同段的多条断言常见),断言部分重置
  checkDraft.target = ''
  checkDraft.expected = ''
  checkDraft.message = ''
}

function removeCheck(i: number): void {
  emit('patch', { checks: checks.value.filter((_, j) => j !== i) })
}

const BRACKET_LABEL: Record<string, string> = {
  main: '主体', before: '前置', after: '后置',
}

/** 列表展示:「主体段 · 全部单元」或「前置段 · x, y」。 */
function checkScope(c: Check): string {
  const bracket = BRACKET_LABEL[c.on?.bracket ?? 'main'] ?? '主体'
  const refs = c.on?.refs ?? []
  return refs.length ? `${bracket}段 · ${refs.join('、')}` : `${bracket}段全部单元`
}

/** 列表展示:断言一行($.path 算子 期望值);非 assertion 策略回落原始键。 */
function checkAssert(c: Check): string {
  const s = c.strategy ?? {}
  if (s.kind !== 'assertion') {
    return Object.keys(s).length ? `${String(s.kind)}(${Object.keys(s).join(' / ')})` : '(空策略)'
  }
  const op = ASSERT_OPS[String(s.operator)] ?? String(s.operator)
  const noExpected = s.operator === 'exists' || s.operator === 'empty'
  const expected = noExpected ? '' : ` ${JSON.stringify(s.expected ?? null)}`
  return `${String(s.target)} ${op}${expected}`
}

function num(key: 'parallel' | 'nRuns', ev: Event): void {
  const v = Math.max(1, Number((ev.target as HTMLInputElement).value) || 1)
  emit('patch', { [key]: v } as Partial<SuiteModeConfig>)
}
</script>

<style scoped>
.gpan { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.gpan-group {
  border: 1px solid rgb(100 116 139 / 22%); border-radius: 10px;
  padding: 10px 12px; display: flex; flex-direction: column; gap: 8px;
}
.gpan-group.off { opacity: .75; }
.gpan-title { margin: 0; font-size: 12.5px; font-weight: 600; display: flex; gap: 8px; align-items: center; }
.gpan-count { font-size: 11px; color: rgb(100 116 139); font-weight: 400; }
.gpan-off-tag {
  font-size: 11px; font-weight: 400; color: rgb(100 116 139);
  border: 1px solid rgb(100 116 139 / 30%); border-radius: 999px; padding: 1px 8px;
}
.gpan-off-note { margin: 0; font-size: 11.5px; color: rgb(100 116 139); }
.gpan-row { display: flex; gap: 12px; }
.gpan-field { display: flex; align-items: center; gap: 6px; font-size: 12.5px; }
.gpan-field > span { color: rgb(100 116 139); }
.gpan input, .gpan select {
  width: 64px; padding: 4px 8px; font-size: 12px; border-radius: 6px;
  border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit;
}
.gpan select { width: auto; }
.gpan input:disabled, .gpan select:disabled { opacity: .5; }
.gpan-note { margin: 0; font-size: 11.5px; color: rgb(100 116 139); }
.gpan-empty { font-size: 12px; color: rgb(100 116 139); }
.gpan-gate { display: flex; align-items: center; gap: 6px; }
.gpan-gate-chip {
  font-size: 12px; padding: 4px 10px; border-radius: 999px;
  color: #4338ca; background: var(--accent-soft);
  border: 1px solid var(--accent-soft-border);
}
.gpan-x {
  width: 20px; height: 20px; border-radius: 6px; cursor: pointer;
  border: 1px solid rgb(100 116 139 / 30%); background: transparent; color: inherit;
  font-size: 12px; line-height: 1; padding: 0;
}
.gpan-add { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.gpan-add input { width: 76px; }
.gpan-add-btn {
  font-size: 12px; padding: 5px 10px; border-radius: 6px; cursor: pointer;
  color: #4338ca; background: var(--accent-soft);
  border: 1px solid var(--accent-soft-border);
}
.gpan-check {
  display: flex; align-items: flex-start; gap: 8px; font-size: 12px;
  padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 6px;
  background: #f8fafc; flex-direction: column;
}
.gpan-check-body { display: flex; flex-direction: column; gap: 3px; flex: 1; min-width: 0; }
.gpan-check .gpan-x { flex: none; }
.gpan-check-on { font-size: 11px; color: rgb(100 116 139); }
.gpan-check-assert {
  font-size: 11.5px; color: #334155; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}
.gpan-title-sub { font-size: 11px; color: rgb(100 116 139); font-weight: 400; }

.gpan-cform {
  display: flex; flex-direction: column; gap: 6px;
  padding: 10px; border: 1px dashed rgb(100 116 139 / 35%);
  border-radius: 8px;
}
.gpan-form-cap { margin: 2px 0 0; font-size: 11px; color: rgb(100 116 139); font-weight: 600; }
.gpan-form-hint { margin: 0; font-size: 10.5px; color: rgb(100 116 139); }
.gpan-form-row { display: flex; gap: 6px; }
.gpan-form-row select { flex: none; }
.gpan-form-row input { flex: 1; min-width: 0; }
.gpan-w { width: 100%; box-sizing: border-box; }
.gpan .gpan-cform input { width: 100%; }
.gpan-refs { display: flex; flex-wrap: wrap; gap: 4px; }
.gpan-ref {
  font-family: ui-monospace, monospace; font-size: 11px; padding: 2px 8px;
  border-radius: 999px; cursor: pointer;
  border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit;
}
.gpan-ref.on {
  color: #4338ca; background: var(--accent-soft);
  border-color: var(--accent-soft-border);
}
.mono { font-family: ui-monospace, monospace; }
</style>
