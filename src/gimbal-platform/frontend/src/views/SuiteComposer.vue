<!-- SuiteComposer.vue — suite 编排页(C5/P3-05)。
     编排 graph(mode 四模式 + before/after 括号 + needs/repeat/乘法)+
     横切面(gates 判定门 / checks 横切断言,D-6 拍板保留);单元 = 平台
     场景;发起 → POST /runs {graph} 单 spawn 下发执行器,台账按单元展示
     (跳执行详情)。参数表单由 mode 注册表 params_schema 驱动(N5:
     chain 有 from_node/to_node,其余为空是正确语义)。 -->
<template>
  <ListPage title="Suite 编排" width="wide"
    subtitle="多场景 graph 编排执行 — mode/括号/依赖/乘法/判定门,单次下发执行器">
    <template #actions>
      <Button size="sm" :disabled="!units.length || running" data-testid="suite-run"
              @click="run">发起执行</Button>
    </template>

    <div v-if="error" class="state error">{{ error }}</div>

    <!-- 模式与全局参数 -->
    <section class="panel">
      <h3 class="p-title">编排模式</h3>
      <div class="mode-row">
        <div v-for="m in MODES" :key="m.id"
             class="mode-card" :class="{ active: mode === m.id }"
             :data-testid="`mode-${m.id}`" @click="mode = m.id">
          <div class="m-name">{{ m.id }}</div>
          <div class="m-desc">{{ m.desc }}</div>
        </div>
      </div>
      <!-- N5:params_schema 驱动的模式参数表单 -->
      <div v-if="modeParams.length" class="mode-params">
        <label v-for="f in modeParams" :key="f.key" class="mp-field">
          <span class="mp-label">{{ f.key }}</span>
          <input v-model="modeParamValues[f.key]" class="mp-input"
                 :data-testid="`mp-${f.key}`" :placeholder="f.description || ''" />
        </label>
      </div>
      <div class="global-row">
        <label class="g-field">并发
          <input v-model.number="parallel" type="number" min="1" max="64" class="g-input" />
        </label>
        <label class="g-field">每单元重复
          <input v-model.number="nRuns" type="number" min="1" max="64" class="g-input" />
        </label>
      </div>
    </section>

    <!-- 单元列表(主体) -->
    <section class="panel">
      <h3 class="p-title">主体单元({{ units.length }})</h3>
      <div v-if="!units.length" class="state empty">
        从右侧场景列表添加单元
      </div>
      <div v-for="(u, i) in units" :key="u.ref" class="unit-row" :data-testid="`unit-${u.ref}`">
        <span class="u-ref mono">{{ u.ref }}</span>
        <span class="u-scenario">{{ u.scenarioId }}</span>
        <template v-if="mode === 'compose'">
          <input v-model="u._needsStr" class="u-input needs" placeholder="needs(逗号分隔)"
                 @change="syncNeeds(u)" />
        </template>
        <template v-if="mode === 'chain'">
          <span class="u-chain-hint mono">{{ i === 0 ? '头' : `← ${units[i - 1].ref}` }}</span>
        </template>
        <label class="u-field">×n
          <input v-model.number="u.repeat" type="number" min="1" max="64" class="u-input num" />
        </label>
        <label class="u-field">runs
          <input v-model.number="u.nRuns" type="number" min="1" max="64" class="u-input num" />
        </label>
        <button class="u-del" @click="removeUnit(i)">✕</button>
      </div>
    </section>

    <!-- 横切面(D-6 保留) -->
    <section class="panel">
      <h3 class="p-title">判定门 gates<span class="p-sub">全部求与;任一失败 → suite 判定失败</span></h3>
      <div v-for="(g, i) in gates" :key="i" class="gate-row" :data-testid="`gate-${i}`">
        <select v-model="g.metric" class="g-select">
          <option v-for="m in GATE_METRICS" :key="m" :value="m">{{ m }}</option>
        </select>
        <select v-model="g.op" class="g-select op">
          <option v-for="o in GATE_OPS" :key="o" :value="o">{{ o }}</option>
        </select>
        <input v-model.number="g.value" type="number" step="any" class="g-input" />
        <button class="u-del" @click="gates.splice(i, 1)">✕</button>
      </div>
      <Button variant="outline" size="sm" data-testid="add-gate" @click="addGate">+ 判定门</Button>
    </section>

    <section class="panel">
      <h3 class="p-title">横切断言 checks<span class="p-sub">按选择器命中单元,编译期注入策略</span></h3>
      <div v-for="(c, i) in checks" :key="i" class="check-row" :data-testid="`check-${i}`">
        <input v-model="c._refsStr" class="u-input refs" placeholder="refs(逗号分隔;空=全部主体)"
               @change="syncCheckRefs(c)" />
        <select v-model="c.on.bracket" class="g-select">
          <option value="main">主体</option>
          <option value="before">before</option>
          <option value="after">after</option>
        </select>
        <textarea v-model="c._strategyStr" class="u-input strategy" rows="2"
                  placeholder='断言策略 JSON:{"kind":"assertion","name":"...","target":"$.call...","operator":"eq","expected":...}'
                  @change="syncCheckStrategy(c, i)" />
        <button class="u-del" @click="checks.splice(i, 1)">✕</button>
      </div>
      <Button variant="outline" size="sm" data-testid="add-check" @click="addCheck">+ 横切断言</Button>
    </section>

    <!-- 场景选择侧板 -->
    <aside class="scenarios-panel">
      <h3 class="p-title">我的场景</h3>
      <div v-if="loadingScenarios" class="state">加载中…</div>
      <button v-for="sc in scenarios" :key="sc.scenario_id"
              class="sc-row" :data-testid="`add-${sc.scenario_id}`"
              :disabled="units.some(u => u.scenarioId === sc.scenario_id)"
              @click="addUnit(sc.scenario_id)">
        <span class="sc-name">{{ sc.name || sc.scenario_id }}</span>
        <span class="sc-id mono">{{ sc.scenario_id }}</span>
      </button>
    </aside>

    <div v-if="lastExecutionId" class="run-result" data-testid="suite-run-result">
      已发起:执行 #{{ lastExecutionId }}
      <RouterLink :to="`/executions/${lastExecutionId}`">查看详情 →</RouterLink>
    </div>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'
import { Button } from '@/components/ui/button'
import { listScenarios } from '@/api/scenario-composer'
import { runScenario, type GateSpec, type CheckSpec, type GraphUnitSpec } from '@/api/scenario-composer'

const router = useRouter()

const MODES = [
  { id: 'aggregate', desc: '无依赖并行' },
  { id: 'compose', desc: '显式 needs DAG' },
  { id: 'fanout', desc: '首单元为源,其余依赖它' },
  { id: 'chain', desc: '按顺序线性串联' },
] as const

const GATE_METRICS = ['pass_rate', 'fail_count', 'total', 'avg_duration_ms', 'max_duration_ms'] as const
const GATE_OPS = ['eq', 'ne', 'gt', 'gte', 'lt', 'lte'] as const

const mode = ref<'aggregate' | 'compose' | 'fanout' | 'chain'>('aggregate')
const parallel = ref(1)
const nRuns = ref(1)
const gates = reactive<({ metric: string; op: string; value: number })[]>([])
const checks = reactive<({ on: { refs?: string[]; bracket?: string }; strategy: Record<string, unknown>; _refsStr: string; _strategyStr: string })[]>([])
const units = reactive<(GraphUnitSpec & { _needsStr?: string })[]>([])
const scenarios = ref<{ scenario_id: string; name: string }[]>([])
const loadingScenarios = ref(false)
const running = ref(false)
const error = ref('')
const lastExecutionId = ref<number | null>(null)

// N5:params_schema 驱动的模式参数(chain 的 from_node/to_node)
const MODE_PARAMS: Record<string, { key: string; description?: string }[]> = {
  aggregate: [], compose: [], fanout: [],
  chain: [{ key: 'from_node' }, { key: 'to_node' }],
}
const modeParams = computed(() => MODE_PARAMS[mode.value] ?? [])
const modeParamValues = reactive<Record<string, string>>({})

function addUnit(scenarioId: string): void {
  const n = units.filter(u => u.scenarioId === scenarioId).length
  units.push({
    ref: n === 0 ? scenarioId.replace(/^sc-/, '') : `${scenarioId.replace(/^sc-/, '')}-${n + 1}`,
    scenarioId,
    needs: [], repeat: 1, nRuns: 1,
  })
}

function removeUnit(i: number): void {
  units.splice(i, 1)
}

function syncNeeds(u: GraphUnitSpec & { _needsStr?: string }): void {
  u.needs = (u._needsStr ?? '').split(',').map(s => s.trim()).filter(Boolean)
}

function addGate(): void {
  gates.push({ metric: 'pass_rate', op: 'gte', value: 1 })
}

function addCheck(): void {
  checks.push({
    on: { refs: [], bracket: 'main' }, strategy: {},
    _refsStr: '', _strategyStr: '',
  })
}

function syncCheckRefs(c: { on: { refs?: string[] }; _refsStr: string }): void {
  c.on.refs = c._refsStr.split(',').map(s => s.trim()).filter(Boolean)
}

function syncCheckStrategy(c: { strategy: Record<string, unknown>; _strategyStr: string }, i: number): void {
  try {
    const parsed = JSON.parse(c._strategyStr)
    if (typeof parsed === 'object' && parsed !== null) {
      c.strategy = parsed
      error.value = ''
    }
  } catch {
    error.value = `checks[${i}].strategy 不是合法 JSON`
  }
}

async function run(): Promise<void> {
  error.value = ''
  if (!units.length) return
  running.value = true
  try {
    const cleanUnits = units.map(u => ({
      ref: u.ref, scenarioId: u.scenarioId,
      ...(u.needs?.length ? { needs: u.needs } : {}),
      ...(u.repeat && u.repeat > 1 ? { repeat: u.repeat } : {}),
      ...(u.nRuns && u.nRuns > 1 ? { nRuns: u.nRuns } : {}),
    }))
    const r = await runScenario({
      scenarioId: cleanUnits[0].scenarioId,
      dataSetIds: [],
      graph: {
        mode: mode.value,
        units: cleanUnits,
        ...(parallel.value > 1 ? { parallel: parallel.value } : {}),
        ...(nRuns.value > 1 ? { nRuns: nRuns.value } : {}),
        ...(gates.length ? { gates: gates as GateSpec[] } : {}),
        ...(checks.filter(c => Object.keys(c.strategy).length).length
              ? { checks: checks.filter(c => Object.keys(c.strategy).length)
                    .map(({ on, strategy }) => ({ on, strategy })) as CheckSpec[] }
              : {}),
      },
    })
    lastExecutionId.value = r.executionId ?? null
    if (r.executionId) {
      void router.push(`/executions/${r.executionId}`)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '发起失败'
  } finally {
    running.value = false
  }
}

onMounted(async () => {
  loadingScenarios.value = true
  try {
    const page = await listScenarios({ visibility: 'private', page: 1, page_size: 100 })
    scenarios.value = page.items.map(s => ({
      scenario_id: s.meta.scenarioId, name: s.meta.name,
    }))
  } catch { /* 静默:选择侧板空态 */ }
  finally { loadingScenarios.value = false }
})
</script>

<style scoped>
.panel { margin-bottom: 16px; padding: 14px 16px; border: 1px solid var(--border, #e4e4e7);
  border-radius: 8px; background: var(--card, #fff); }
.p-title { font-size: 14px; font-weight: 600; margin: 0 0 10px; }
.p-sub { font-weight: 400; font-size: 12px; color: #71717a; margin-left: 8px; }
.mode-row { display: flex; gap: 10px; flex-wrap: wrap; }
.mode-card { flex: 1; min-width: 140px; padding: 10px 12px; border: 1px solid var(--border, #d4d4d8);
  border-radius: 8px; cursor: pointer; }
.mode-card.active { border-color: #3b82f6; background: #eff6ff; }
.m-name { font-weight: 600; font-size: 13px; font-family: ui-monospace, monospace; }
.m-desc { font-size: 12px; color: #71717a; margin-top: 4px; }
.mode-params { display: flex; gap: 10px; margin-top: 10px; }
.mp-field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; }
.mp-input, .g-input, .u-input { border: 1px solid var(--border, #d4d4d8); border-radius: 6px;
  padding: 4px 8px; font-size: 13px; }
.mp-input { width: 160px; }
.global-row { display: flex; gap: 16px; margin-top: 10px; }
.g-field { font-size: 13px; display: flex; align-items: center; gap: 6px; }
.g-input { width: 72px; }
.unit-row { display: flex; align-items: center; gap: 10px; padding: 6px 0;
  border-bottom: 1px solid #f4f4f5; }
.u-ref { font-weight: 600; font-size: 13px; min-width: 90px; }
.u-scenario { font-size: 12px; color: #71717a; flex: 1; }
.u-input { font-size: 12px; }
.u-input.needs { width: 200px; }
.u-input.num { width: 56px; }
.u-field { font-size: 12px; color: #71717a; display: flex; align-items: center; gap: 4px; }
.u-chain-hint { font-size: 12px; color: #a1a1aa; }
.u-del { border: none; background: none; color: #b91c1c; cursor: pointer; font-size: 14px; }
.gate-row, .check-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.g-select { border: 1px solid var(--border, #d4d4d8); border-radius: 6px;
  padding: 4px 8px; font-size: 13px; }
.g-select.op { width: 72px; }
.gate-row .g-input { width: 100px; }
.u-input.refs { width: 220px; }
.u-input.strategy { flex: 1; font-family: ui-monospace, monospace; font-size: 12px; }
.scenarios-panel { position: fixed; right: 24px; top: 120px; width: 220px;
  max-height: 60vh; overflow-y: auto; padding: 12px; border: 1px solid var(--border, #e4e4e7);
  border-radius: 8px; background: var(--card, #fafafa); }
.sc-row { display: flex; flex-direction: column; gap: 2px; width: 100%; text-align: left;
  padding: 8px; border: none; border-radius: 6px; background: none; cursor: pointer; }
.sc-row:hover:not(:disabled) { background: #eff6ff; }
.sc-row:disabled { opacity: 0.4; cursor: not-allowed; }
.sc-name { font-size: 13px; font-weight: 500; }
.sc-id { font-size: 11px; color: #71717a; }
.run-result { margin-top: 12px; padding: 10px 14px; border-radius: 8px;
  background: #dcfce7; color: #166534; font-size: 13px; }
.state { padding: 20px; text-align: center; color: #71717a; font-size: 13px; }
.state.error { color: #b91c1c; text-align: left; }
.mono { font-family: ui-monospace, monospace; }
</style>
