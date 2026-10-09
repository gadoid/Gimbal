<!-- GatesPanel.vue — 右栏(原型 20):运行参数(并发 / 每单元重复 /
     预计 runs)+ 判定门(条件 chips,聚合模式置灰并说明)+ 横切断言
     (列表只读展示;表单编辑随第 3 步判定门结论一起做)。 -->
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

    <section class="gpan-group">
      <p class="gpan-title">横切断言</p>
      <div v-if="!checks.length" class="gpan-empty">无横切断言</div>
      <div v-for="(c, i) in checks" :key="i" class="gpan-check">
        <span class="gpan-check-chip">bracket: {{ bracketOf(c) }}</span>
        <span class="gpan-check-strat">{{ strategyLabel(c) }}</span>
        <button
          v-if="!readonly" type="button" class="gpan-x"
          title="移除此横切断言"
          @click="removeCheck(i)"
        >×</button>
      </div>
      <p v-if="!readonly" class="gpan-note">横切断言(选择器 + 断言表单)编辑随校验轮上线</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import type { SuiteModeConfig } from '@/api/suites'
import { estimateOrchRuns } from '@/utils/suiteStructure'

interface Gate { metric: string; op: string; value: number }
type Check = { on?: { bracket?: string }; strategy?: Record<string, unknown> }

const props = defineProps<{
  config: SuiteModeConfig
  members: { scenarioId: string }[]
  mode: string
  readonly?: boolean
  runCap?: number
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

function removeCheck(i: number): void {
  emit('patch', { checks: checks.value.filter((_, j) => j !== i) })
}

function strategyLabel(c: Check): string {
  const s = c.strategy ?? {}
  const keys = Object.keys(s)
  if (!keys.length) return '(空策略)'
  return keys.slice(0, 3).join(' / ')
}

function bracketOf(c: Check): string {
  return c.on?.bracket ?? 'main'
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
  color: #1d4ed8; background: rgb(59 130 246 / 10%);
  border: 1px solid rgb(59 130 246 / 40%);
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
  color: #2563eb; background: rgb(59 130 246 / 8%);
  border: 1px solid rgb(59 130 246 / 45%);
}
.gpan-check { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.gpan-check-chip {
  font-family: ui-monospace, monospace; font-size: 11px; padding: 2px 8px;
  border-radius: 6px; background: rgb(100 116 139 / 8%);
}
.gpan-check-strat { color: rgb(100 116 139); font-size: 11.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
</style>
