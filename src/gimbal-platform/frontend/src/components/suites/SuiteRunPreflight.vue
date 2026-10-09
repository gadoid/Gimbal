<!-- SuiteRunPreflight.vue — 运行预检弹窗(原型 30)。
     摘要(单元数 · 预计 runs/上限 · 判定门数)+ 逐条预检:
     在途批次或运行 → 按钮变「查看」;超上限 → 禁用并列出前三大来源;
     方案多行但编排只跑一行 → 警告并直达单元改选(定位成员)。
     第 3 步接入 /suites/{id}/validate 后,逐条预检换服务端权威结论。 -->
<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="pf-dialog" data-testid="suite-preflight">
      <DialogHeader>
        <DialogTitle>运行预检</DialogTitle>
      </DialogHeader>

      <div v-if="loading" class="pf-loading">检查中…</div>
      <template v-else-if="detail">
        <p class="pf-summary" data-testid="suite-preflight-summary">
          {{ unitCount }} 个单元 · 预计 {{ estimatedRuns }} runs(上限 {{ runCap }})· 判定门 {{ gateCount }} 条
        </p>

        <ul class="pf-list">
          <li v-if="!unitCount" class="pf-item bad">
            <span class="pf-ico">×</span>
            <span>Suite 没有成员,无可执行场景</span>
          </li>
          <li v-if="inFlight" class="pf-item bad">
            <span class="pf-ico">×</span>
            <span>本人在该 Suite 上有未结束的{{ inFlight.kind === 'batch' ? '批次' : '运行' }}(先查看或等它结束)</span>
          </li>
          <li v-if="overCap" class="pf-item bad">
            <span class="pf-ico">×</span>
            <span>预计 {{ estimatedRuns }} runs 超过上限 {{ runCap }},前三大来源:{{ topSources }}</span>
          </li>
          <li v-if="hasCycle" class="pf-item bad">
            <span class="pf-ico">×</span>
            <span>依赖存在环 —— 执行器会拒绝编译,先解开再运行</span>
          </li>
          <li v-for="w in warnings" :key="w.key" class="pf-item" :class="w.tone">
            <span class="pf-ico">{{ w.tone === 'warn' ? '!' : '✓' }}</span>
            <span>{{ w.text }}</span>
            <button
              v-if="w.locate" type="button" class="pf-go"
              @click="$emit('locate', w.locate)"
            >去改选</button>
          </li>
          <li v-if="!warnings.length && unitCount && !inFlight && !overCap" class="pf-item ok">
            <span class="pf-ico">✓</span>
            <span>预检通过:成员方案有效、依赖图完整{{ orchNote }}</span>
          </li>
        </ul>
      </template>

      <DialogFooter>
        <button type="button" class="btn-ghost" @click="$emit('update:open', false)">取消</button>
        <button
          v-if="inFlight"
          type="button" class="btn-primary"
          data-testid="suite-preflight-view"
          @click="viewInFlight"
        >查看</button>
        <button
          v-else
          type="button" class="btn-primary"
          data-testid="suite-preflight-run"
          :disabled="!canRun || running"
          @click="$emit('run')"
        >{{ running ? '发起中…' : '开始运行' }}</button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import {
  getSuite, listSuiteRuns, type SuiteDetail, type SuiteRunItem,
} from '@/api/suites'
import { estimateOrchRuns, needsHasCycle } from '@/utils/suiteStructure'
import { useSuiteSchemes } from '@/composables/useSuiteSchemes'

const props = defineProps<{
  open: boolean
  suiteId: number
  runCap?: number
  running?: boolean
  /** 跳过详情重新拉取(外层已有最新 detail 时传进来省一次请求)。 */
  detail0?: SuiteDetail | null
}>()

defineEmits<{
  (e: 'update:open', v: boolean): void
  (e: 'run'): void
  (e: 'locate', scenarioId: string): void
}>()

const runCap = computed(() => props.runCap ?? 1000)
const loading = ref(false)
const detail = ref<SuiteDetail | null>(null)
const runs = ref<SuiteRunItem[]>([])
const { schemesOf, datasetOf } = useSuiteSchemes()

interface Warn { key: string; tone: 'ok' | 'warn'; text: string; locate?: string }
const warnings = ref<Warn[]>([])

const unitCount = computed(() => detail.value?.members.length ?? 0)
const gateCount = computed(
  () => (detail.value?.modeConfig?.gates as unknown[] | undefined)?.length ?? 0)
const isOrch = computed(
  () => !!detail.value && detail.value.mode !== 'aggregate')
const orchNote = computed(() => isOrch.value ? ',每单元只跑所选一行' : '')

const estRuns = ref(0)
const sourceRows = ref<{ name: string; runs: number }[]>([])
const estimatedRuns = computed(() => estRuns.value)

const inFlight = computed(() => runs.value.find(
  (r) => r.status === 'running' || r.status === 'queued') ?? null)
const overCap = computed(() => estRuns.value > runCap.value)
const hasCycle = computed(() => !!detail.value && isOrch.value
  && needsHasCycle(mainMembers.value, detail.value.modeConfig))
const topSources = computed(() => sourceRows.value
  .slice()
  .sort((a, b) => b.runs - a.runs)
  .slice(0, 3)
  .map((s) => `${s.name}(${s.runs})`).join('、'))

const canRun = computed(() =>
  unitCount.value > 0 && !overCap.value && !hasCycle.value && !inFlight.value)

const mainMembers = computed(() =>
  (detail.value?.members ?? []).filter((m) => m.role === 'main'))

function viewInFlight(): void {
  const f = inFlight.value
  if (!f) return
  if (f.kind === 'suite_graph' && f.executionId) {
    window.location.assign(`/executions/${f.executionId}`)
  } else if (f.batchId) {
    window.location.assign(`/executions?batch_id=${encodeURIComponent(f.batchId)}`)
  }
}

async function check(): Promise<void> {
  loading.value = true
  warnings.value = []
  try {
    detail.value = props.detail0 ?? await getSuite(props.suiteId)
    const d = detail.value
    const [runList] = await Promise.all([
      listSuiteRuns(props.suiteId).catch(() => [] as SuiteRunItem[]),
      estimate(),
    ])
    runs.value = runList
  } finally {
    loading.value = false
  }
}

/** 逐成员:方案有效性 + 多行只跑一行(约束 5);顺带算精确 runs。 */
async function estimate(): Promise<void> {
  const d = detail.value
  if (!d) return
  const units = (d.modeConfig?.units ?? {}) as Record<string, {
    repeat?: number; nRuns?: number; schemeId?: string | null;
    row?: { datasetId: string; rowIndex: number } | null
  }>
  let total = 0
  const rows: { name: string; runs: number }[] = []
  const warns: Warn[] = []
  for (const m of d.members) {
    const schemes = await schemesOf(m.scenarioId)
    const u = units[m.scenarioId] || {}
    const per = Math.max(1, u.repeat || 1) * Math.max(1, u.nRuns || 1)
    if (d.mode === 'aggregate') {
      const def = schemes.find((s) => s.isDefault) ?? schemes[0] ?? null
      if (!def) {
        warns.push({
          key: `noscheme-${m.scenarioId}`, tone: 'warn',
          text: `「${m.name}」没有运行方案,将以裸基线发起`,
        })
        total += per
        rows.push({ name: m.name, runs: per })
        continue
      }
      let rowCount = 0
      for (const sel of def.dataSetSelection ?? []) {
        if (sel.rowIndexes?.length) rowCount += sel.rowIndexes.length
        else {
          const ds = await datasetOf(sel.datasetId)
          rowCount += ds?.rowCount ?? 1
        }
      }
      const inj = def.injectionEntryIds?.length ?? 0
      const est = Math.max(1, rowCount) * Math.max(1, inj) * Math.max(1, def.nRuns || 1)
      total += est
      rows.push({ name: m.name, runs: est })
    } else {
      total += per
      rows.push({ name: m.name, runs: per })
      const scheme = u.schemeId
        ? schemes.find((s) => s.schemeId === u.schemeId)
        : (schemes.find((s) => s.isDefault) ?? null)
      if (!scheme) {
        warns.push({
          key: `bare-${m.scenarioId}`, tone: 'warn',
          text: `「${m.name}」无运行方案,该单元将跑裸基线`,
          locate: m.scenarioId,
        })
        continue
      }
      let selected = 0
      for (const sel of scheme.dataSetSelection ?? []) {
        if (sel.rowIndexes?.length) selected += sel.rowIndexes.length
        else {
          const ds = await datasetOf(sel.datasetId)
          selected += ds?.rowCount ?? 1
        }
      }
      if (!u.row && selected > 1) {
        warns.push({
          key: `norow-${m.scenarioId}`, tone: 'warn',
          text: `「${m.name}」的方案选了 ${selected} 行数据,编排模式只会跑所选那行 —— 当前未选行,将跑裸基线`,
          locate: m.scenarioId,
        })
      } else if (u.row && selected > 1) {
        warns.push({
          key: `row1-${m.scenarioId}`, tone: 'warn',
          text: `「${m.name}」的方案选了 ${selected} 行,只会跑 ${u.row.datasetId} 第 ${u.row.rowIndex} 行`,
        })
      }
    }
  }
  estRuns.value = total
  sourceRows.value = rows
  warnings.value = warns
}

watch(() => props.open, (v) => { if (v) void check() })
</script>

<style scoped>
.pf-dialog { display: flex; flex-direction: column; gap: 12px; max-width: 520px; }
.pf-loading { padding: 18px 0; text-align: center; color: rgb(100 116 139); font-size: 13px; }
.pf-summary { margin: 0; font-size: 13px; }
.pf-list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.pf-item {
  display: flex; align-items: center; gap: 8px; font-size: 12.5px;
  padding: 6px 10px; border-radius: 8px;
  border: 1px solid rgb(100 116 139 / 18%); background: rgb(100 116 139 / 4%);
}
.pf-item.ok { border-color: rgb(34 197 94 / 35%); background: rgb(34 197 94 / 6%); }
.pf-item.warn { border-color: rgb(245 158 11 / 40%); background: rgb(245 158 11 / 7%); }
.pf-item.bad { border-color: rgb(220 38 38 / 35%); background: rgb(220 38 38 / 6%); }
.pf-ico { flex: none; width: 16px; text-align: center; font-weight: 700; }
.pf-item.ok .pf-ico { color: #15803d; }
.pf-item.warn .pf-ico { color: #b45309; }
.pf-item.bad .pf-ico { color: #dc2626; }
.pf-go {
  flex: none; font-size: 11.5px; padding: 3px 9px; border-radius: 6px; cursor: pointer;
  color: #2563eb; background: rgb(59 130 246 / 8%); border: 1px solid rgb(59 130 246 / 45%);
}
.btn-ghost, .btn-primary {
  padding: 7px 16px; font-size: 13px; border-radius: 8px; cursor: pointer;
}
.btn-ghost { border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit; }
.btn-primary { font-weight: 600; border: none; color: #fff; background: #2563eb; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
</style>
