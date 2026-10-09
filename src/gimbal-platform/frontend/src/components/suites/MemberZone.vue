<!-- MemberZone.vue — Suite 管理页中栏(原型 20 四种模式)。
     前置区 / 主体区(按模式:聚合列表 · 串联链 · 扇出源+变体 · 依赖
     编排分层 DAG)/ 后置区 / 底部汇总行。行操作:▲▼ 排序、⋯(移除、
     设为前置/后置、单元设置);单元设置 = 方案 / 数据行 / ×重复
     (约束 5:编排模式每单元只跑一行)。拖拽:从左栏拖入落位到对应区。
     只读态:全部操作隐藏,拖拽不响应。 -->
<template>
  <div class="mzone" data-testid="suite-member-zone">
    <!-- 前置区 -->
    <section
      class="mz-bracket"
      :class="{ dragover: dragOver === 'before' }"
      @dragover.prevent="onDragOver('before')"
      @dragleave="dragOver = null"
      @drop.prevent="onDrop('before', $event)"
    >
      <p class="mz-bracket-title">前置<span class="mz-bracket-hint">先于所有主体运行</span></p>
      <div v-if="before.length" class="mz-rows">
        <div v-for="m in before" :key="m.scenarioId" class="mz-row">
          <MemberRow
            :member="m" :unit="unitOf(m.scenarioId)" :readonly="readonly"
            :scheme-name="schemeNameOf(m.scenarioId)"
            :orchestrate="isOrch" :highlight="highlighted === m.scenarioId"
            :multi-row="multiRowIds.has(m.scenarioId)"
            @move="(d) => $emit('move-member', m.scenarioId, d)"
            @remove="$emit('remove-member', m.scenarioId)"
            @role="(r) => $emit('set-role', m.scenarioId, r)"
            @settings="toggleSettings(m.scenarioId)"
          />
          <UnitSettings
            v-if="settingsId === m.scenarioId"
            :member="m" :unit="unitOf(m.scenarioId)" :orchestrate="isOrch"
            :schemes="schemesFor(m.scenarioId)" :loading="settingsLoading"
            :dataset-rows="datasetRows"
            @patch="(p) => $emit('unit-config', m.scenarioId, p)"
          />
        </div>
      </div>
      <p v-if="!readonly" class="mz-drop">＋ 拖入前置场景(先于所有主体运行)</p>
    </section>

    <!-- 主体区:按模式 -->
    <section class="mz-main">
      <p class="mz-main-title">主体<span class="mz-bracket-hint">{{ mainHint }}</span></p>
      <div v-if="!main.length" class="mz-empty">
        还没有主体成员 —— 从左侧「我的场景」加入,或拖入下方放置框
      </div>

      <!-- 聚合:列表 -->
      <div v-else-if="mode === 'aggregate'" class="mz-rows">
        <div v-for="(m, i) in main" :key="m.scenarioId" class="mz-row">
          <MemberRow
            :idx="i + 1" :member="m" :unit="unitOf(m.scenarioId)" :readonly="readonly"
            :scheme-name="schemeNameOf(m.scenarioId)"
            :orchestrate="false" :highlight="highlighted === m.scenarioId"
            @move="(d) => $emit('move-member', m.scenarioId, d)"
            @remove="$emit('remove-member', m.scenarioId)"
            @role="(r) => $emit('set-role', m.scenarioId, r)"
            @settings="toggleSettings(m.scenarioId)"
          />
          <UnitSettings
            v-if="settingsId === m.scenarioId"
            :member="m" :unit="unitOf(m.scenarioId)" :orchestrate="false"
            :schemes="schemesFor(m.scenarioId)" :loading="settingsLoading"
            :dataset-rows="datasetRows"
            @patch="(p) => $emit('unit-config', m.scenarioId, p)"
          />
        </div>
      </div>

      <!-- 串联:链(序号 + 连接线) -->
      <div v-else-if="mode === 'chain'" class="mz-chain">
        <div v-for="(m, i) in main" :key="m.scenarioId" class="mz-chain-step">
          <span class="mz-chain-num">{{ i + 1 }}</span>
          <div class="mz-row">
            <MemberRow
              :member="m" :unit="unitOf(m.scenarioId)" :readonly="readonly"
              :scheme-name="schemeNameOf(m.scenarioId)"
              :orchestrate="true" :highlight="highlighted === m.scenarioId"
              :multi-row="multiRowIds.has(m.scenarioId)"
              @move="(d) => $emit('move-member', m.scenarioId, d)"
              @remove="$emit('remove-member', m.scenarioId)"
              @role="(r) => $emit('set-role', m.scenarioId, r)"
              @settings="toggleSettings(m.scenarioId)"
            />
            <UnitSettings
              v-if="settingsId === m.scenarioId"
              :member="m" :unit="unitOf(m.scenarioId)" :orchestrate="true"
              :schemes="schemesFor(m.scenarioId)" :loading="settingsLoading"
              :dataset-rows="datasetRows"
              @patch="(p) => $emit('unit-config', m.scenarioId, p)"
            />
          </div>
        </div>
        <div v-if="main.length && !readonly" class="mz-stepto">
          <label>
            只跑到某一步:
            <select
              :value="stepTo ?? ''"
              data-testid="suite-stepto"
              @change="onStepTo($event)"
            >
              <option value="">跑完全部</option>
              <option v-for="(m, i) in main" :key="m.scenarioId" :value="refOf(m.scenarioId)">
                第 {{ i + 1 }} 步 · {{ m.name }}
              </option>
            </select>
          </label>
          <span class="mz-stepto-note">被跳过的步骤不执行,上游输出照常传给后续</span>
        </div>
      </div>

      <!-- 扇出:源 + 变体 -->
      <div v-else-if="mode === 'fanout'" class="mz-fanout">
        <template v-if="main.length">
          <div class="mz-row">
            <MemberRow
              :idx="1" :member="main[0]" :unit="unitOf(main[0].scenarioId)"
              :readonly="readonly" :source="true"
              :scheme-name="schemeNameOf(main[0].scenarioId)"
              :orchestrate="true" :highlight="highlighted === main[0].scenarioId"
              :multi-row="multiRowIds.has(main[0].scenarioId)"
              @move="(d) => $emit('move-member', main[0].scenarioId, d)"
              @remove="$emit('remove-member', main[0].scenarioId)"
              @role="(r) => $emit('set-role', main[0].scenarioId, r)"
              @settings="toggleSettings(main[0].scenarioId)"
            />
            <UnitSettings
              v-if="settingsId === main[0].scenarioId"
              :member="main[0]" :unit="unitOf(main[0].scenarioId)" :orchestrate="true"
              :schemes="schemesFor(main[0].scenarioId)" :loading="settingsLoading"
              :dataset-rows="datasetRows"
              @patch="(p) => $emit('unit-config', main[0].scenarioId, p)"
            />
          </div>
          <p class="mz-fanout-note">登录一次,其余场景用它的结果(源固定排在第一位)</p>
          <div class="mz-fanout-variants">
            <div v-for="(m, i) in main.slice(1)" :key="m.scenarioId" class="mz-row">
              <MemberRow
                :idx="i + 2" :member="m" :unit="unitOf(m.scenarioId)"
                :readonly="readonly"
                :scheme-name="schemeNameOf(m.scenarioId)"
                :orchestrate="true" :highlight="highlighted === m.scenarioId"
                :multi-row="multiRowIds.has(m.scenarioId)"
                @move="(d) => $emit('move-member', m.scenarioId, d)"
                @remove="$emit('remove-member', m.scenarioId)"
                @role="(r) => $emit('set-role', m.scenarioId, r)"
                @settings="toggleSettings(m.scenarioId)"
              />
              <UnitSettings
                v-if="settingsId === m.scenarioId"
                :member="m" :unit="unitOf(m.scenarioId)" :orchestrate="true"
                :schemes="schemesFor(m.scenarioId)" :loading="settingsLoading"
                :dataset-rows="datasetRows"
                @patch="(p) => $emit('unit-config', m.scenarioId, p)"
              />
            </div>
          </div>
        </template>
      </div>

      <!-- 依赖编排:分层 DAG -->
      <div v-else class="mz-dag">
        <div v-for="(layer, li) in dag.layers" :key="li" class="mz-dag-layer">
          <span class="mz-dag-tag">L{{ li }}</span>
          <div class="mz-dag-cells">
            <div v-for="id in layer" :key="id" class="mz-row">
              <MemberRow
                :member="memberById(id)!" :unit="unitOf(id)" :readonly="readonly"
                :scheme-name="schemeNameOf(id)"
                :orchestrate="true" :highlight="highlighted === id"
                :multi-row="multiRowIds.has(id)"
                @move="(d) => $emit('move-member', id, d)"
                @remove="$emit('remove-member', id)"
                @role="(r) => $emit('set-role', id, r)"
                @settings="toggleSettings(id)"
              />
              <UnitSettings
                v-if="settingsId === id"
                :member="memberById(id)!" :unit="unitOf(id)" :orchestrate="true"
                :schemes="schemesFor(id)" :loading="settingsLoading"
                :dataset-rows="datasetRows"
                @patch="(p) => $emit('unit-config', id, p)"
              />
            </div>
          </div>
        </div>
        <p v-if="dag.hasCycle" class="mz-cycle">⚠ needs 存在环 —— 保存前请先解开(执行器会拒绝编译)</p>
      </div>
    </section>

    <!-- 后置区 -->
    <section
      class="mz-bracket"
      :class="{ dragover: dragOver === 'after' }"
      @dragover.prevent="onDragOver('after')"
      @dragleave="dragOver = null"
      @drop.prevent="onDrop('after', $event)"
    >
      <p class="mz-bracket-title">后置<span class="mz-bracket-hint">在所有主体之后运行,含失败时</span></p>
      <div v-if="after.length" class="mz-rows">
        <div v-for="m in after" :key="m.scenarioId" class="mz-row">
          <MemberRow
            :member="m" :unit="unitOf(m.scenarioId)" :readonly="readonly"
            :scheme-name="schemeNameOf(m.scenarioId)"
            :orchestrate="isOrch" :highlight="highlighted === m.scenarioId"
            :multi-row="multiRowIds.has(m.scenarioId)"
            @move="(d) => $emit('move-member', m.scenarioId, d)"
            @remove="$emit('remove-member', m.scenarioId)"
            @role="(r) => $emit('set-role', m.scenarioId, r)"
            @settings="toggleSettings(m.scenarioId)"
          />
          <UnitSettings
            v-if="settingsId === m.scenarioId"
            :member="m" :unit="unitOf(m.scenarioId)" :orchestrate="isOrch"
            :schemes="schemesFor(m.scenarioId)" :loading="settingsLoading"
            :dataset-rows="datasetRows"
            @patch="(p) => $emit('unit-config', m.scenarioId, p)"
          />
        </div>
      </div>
      <p v-if="!readonly" class="mz-drop">＋ 拖入后置场景(在所有主体之后运行,含失败时)</p>
    </section>

    <p class="mz-summary" data-testid="suite-summary-line">
      总 {{ totalUnits }} 单元 · 并发 {{ parallel }} · {{ summaryRuns }} · 上限 {{ runCap }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type {
  MemberRole, SuiteDetail, SuiteModeConfig, SuiteUnitConfig,
} from '@/api/suites'
import { layeredUnits, estimateOrchRuns } from '@/utils/suiteStructure'
import { useSuiteSchemes } from '@/composables/useSuiteSchemes'
import type { SchemeV2 } from '@/api/scenario-composer'
import MemberRow from './MemberRow.vue'
import UnitSettings from './UnitSettings.vue'

const props = defineProps<{
  detail: SuiteDetail
  config: SuiteModeConfig
  readonly?: boolean
  highlighted?: string | null
  runCap?: number
}>()

const emit = defineEmits<{
  (e: 'add-member', scenarioId: string, role: MemberRole): void
  (e: 'remove-member', scenarioId: string): void
  (e: 'move-member', scenarioId: string, delta: number): void
  (e: 'set-role', scenarioId: string, role: MemberRole): void
  (e: 'unit-config', scenarioId: string, patch: Partial<SuiteUnitConfig>): void
  (e: 'stepto', ref: string | null): void
}>()

const runCap = computed(() => props.runCap ?? 1000)
const isOrch = computed(() => props.detail.mode !== 'aggregate')
const mode = computed(() => props.detail.mode)

const before = computed(() => props.detail.members.filter((m) => m.role === 'before'))
const after = computed(() => props.detail.members.filter((m) => m.role === 'after'))
const main = computed(() => props.detail.members.filter((m) => m.role === 'main'))
const totalUnits = computed(() => props.detail.members.length)
const parallel = computed(() => Number(props.config.parallel) || 1)

const mainHint = computed(() => ({
  aggregate: '各成员独立执行,共用一个批次',
  chain: '按顺序执行,第 1 步失败即停',
  fanout: '源 + 变体:其余成员并行、共用源的结果',
  compose: 'needs 决定顺序与传值',
}[props.detail.mode] ?? ''))

const dag = computed(() => layeredUnits(main.value, props.config))
const summaryRuns = computed(() => {
  if (isOrch.value) {
    return `约 ${estimateOrchRuns(main.value, props.config)} runs`
  }
  return `${totalUnits.value} 个独立执行`
})

function memberById(id: string) {
  return props.detail.members.find((m) => m.scenarioId === id)
}
function unitOf(id: string): SuiteUnitConfig {
  return (props.config.units as Record<string, SuiteUnitConfig>)?.[id] || {}
}
function refOf(id: string): string {
  return unitOf(id).ref || id
}

// ── 单元设置(懒加载方案 + 数据集行)────────────────────────────
const settingsId = ref<string | null>(null)
const settingsLoading = ref(false)
const schemeList = ref<SchemeV2[]>([])
const datasetRows = ref<{ datasetId: string; name: string; rowCount: number }[]>([])
const { schemesOf, datasetOf } = useSuiteSchemes()

async function toggleSettings(scenarioId: string): Promise<void> {
  if (settingsId.value === scenarioId) {
    settingsId.value = null
    return
  }
  settingsId.value = scenarioId
  settingsLoading.value = true
  schemeList.value = []
  datasetRows.value = []
  try {
    const schemes = await schemesOf(scenarioId)
    schemeList.value = schemes
    const scheme = schemes.find((s) => s.schemeId === (unitOf(scenarioId).schemeId
      ?? schemes.find((x) => x.isDefault)?.schemeId)) ?? schemes[0]
    const ids = [...new Set([...(scheme?.dataSetIds ?? []),
      ...(scheme?.dataSetSelection ?? []).map((d) => d.datasetId)])]
    const rows: { datasetId: string; name: string; rowCount: number }[] = []
    for (const id of ids) {
      const ds = await datasetOf(id)
      if (ds) rows.push({ datasetId: ds.datasetId, name: ds.name, rowCount: ds.rowCount })
    }
    datasetRows.value = rows
  } finally {
    settingsLoading.value = false
  }
}

function schemesFor(scenarioId: string): SchemeV2[] {
  return settingsId.value === scenarioId ? schemeList.value : []
}

// 方案名 chip:默认方案 / 具体方案名(缓存;无方案 = 裸基线)
const schemeNames = ref(new Map<string, string>())
watch(() => props.detail.members, (ms) => {
  for (const m of ms) {
    if (schemeNames.value.has(m.scenarioId)) continue
    void schemesOf(m.scenarioId).then((list) => {
      const unit = unitOf(m.scenarioId)
      const pick = unit.schemeId
        ? list.find((s) => s.schemeId === unit.schemeId)
        : (list.find((s) => s.isDefault) ?? null)
      schemeNames.value = new Map(schemeNames.value).set(
        m.scenarioId, pick ? `${pick.isDefault && !unit.schemeId ? '默认方案' : pick.name}` : '裸基线')
    })
  }
}, { immediate: true })

function schemeNameOf(id: string): string {
  return schemeNames.value.get(id) ?? ''
}

// 多行方案标记(约束 5:编排模式只跑一行;从聚合切编排时提示选行)
const multiRowIds = ref(new Set<string>())
watch([() => props.detail.members, () => props.detail.mode], async ([ms]) => {
  const next = new Set<string>()
  for (const m of ms as SuiteDetail['members']) {
    const unit = unitOf(m.scenarioId)
    if (unit.row) continue   // 已选定行
    const schemes = await schemesOf(m.scenarioId)
    const pick = unit.schemeId
      ? schemes.find((s) => s.schemeId === unit.schemeId)
      : (schemes.find((s) => s.isDefault) ?? null)
    const n = (pick?.dataSetSelection ?? []).reduce(
      (sum, d) => sum + Math.max(1, d.rowIndexes?.length ?? 1), 0)
    if (n > 1) next.add(m.scenarioId)
  }
  multiRowIds.value = next
}, { immediate: true })

// ── 串联「只跑到某一步」(运行参数,不落编排配置)──────────────
const stepTo = ref<string | null>(null)
function onStepTo(ev: Event): void {
  const v = (ev.target as HTMLSelectElement).value || null
  stepTo.value = v
  emit('stepto', v)
}

// ── 拖拽落位(左栏 → 前置/后置区)───────────────────────────────
const dragOver = ref<'before' | 'after' | null>(null)
function onDragOver(zone: 'before' | 'after'): void {
  if (!props.readonly) dragOver.value = zone
}
function onDrop(zone: 'before' | 'after', ev: DragEvent): void {
  dragOver.value = null
  if (props.readonly) return
  const sid = ev.dataTransfer?.getData('application/x-gimbal-scenario')
  if (sid) emit('add-member', sid, zone)
}
</script>

<style scoped>
.mzone { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.mz-bracket {
  border: 1px dashed rgb(100 116 139 / 45%); border-radius: 10px;
  padding: 8px 12px; display: flex; flex-direction: column; gap: 6px;
}
.mz-bracket.dragover { border-color: #4338ca; background: var(--accent-soft); }
.mz-bracket-title { margin: 0; font-size: 12.5px; font-weight: 600; }
.mz-bracket-hint { margin-left: 8px; font-weight: 400; font-size: 11.5px; color: rgb(100 116 139); }
.mz-drop { margin: 0; font-size: 12px; color: rgb(100 116 139 / 80%); }
.mz-main {
  border: 1px solid rgb(100 116 139 / 22%); border-radius: 10px;
  padding: 10px 12px; display: flex; flex-direction: column; gap: 8px;
}
.mz-main-title { margin: 0; font-size: 12.5px; font-weight: 600; }
.mz-empty { font-size: 12.5px; color: rgb(100 116 139); padding: 16px 0; text-align: center; }
.mz-rows { display: flex; flex-direction: column; gap: 4px; }
.mz-row { display: flex; flex-direction: column; }

.mz-chain { display: flex; flex-direction: column; gap: 0; }
.mz-chain-step { display: flex; gap: 10px; }
.mz-chain-num {
  flex: none; width: 22px; height: 22px; margin-top: 6px;
  display: grid; place-items: center; font-size: 11.5px;
  border: 1px solid var(--accent-soft-border); border-radius: 999px; color: #4338ca;
  position: relative;
}
.mz-chain-step:not(:last-child) .mz-chain-num::after {
  content: ''; position: absolute; top: 22px; left: 50%;
  width: 1px; height: 14px; background: var(--accent-soft-border);
}
.mz-chain-step { margin-bottom: 10px; }
.mz-stepto {
  display: flex; align-items: center; gap: 10px; margin: 4px 0 0 32px;
  font-size: 12.5px;
}
.mz-stepto select {
  padding: 4px 8px; font-size: 12.5px; border-radius: 6px;
  border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit;
}
.mz-stepto-note { font-size: 11px; color: rgb(100 116 139); }

.mz-fanout-note {
  margin: 2px 0 6px 32px; font-size: 11.5px; color: rgb(100 116 139);
}
.mz-fanout-variants { display: flex; flex-direction: column; gap: 4px; margin-left: 32px;
  border-left: 1px solid rgb(59 130 246 / 40%); padding-left: 10px; }

.mz-dag { display: flex; flex-direction: column; gap: 8px; }
.mz-dag-layer { display: flex; gap: 10px; align-items: flex-start; }
.mz-dag-tag {
  flex: none; width: 24px; margin-top: 8px; font-size: 11px;
  color: rgb(100 116 139); font-family: ui-monospace, monospace;
}
.mz-dag-cells { display: flex; flex-wrap: wrap; gap: 6px; flex: 1; min-width: 0; }
.mz-dag-layer:not(:last-child) { padding-bottom: 8px; border-bottom: 1px dashed rgb(100 116 139 / 25%); }
.mz-cycle { margin: 0; font-size: 12px; color: #b45309; }

.mz-summary {
  margin: 0; font-size: 12px; color: rgb(100 116 139);
  padding: 4px 2px 0; border-top: 1px solid rgb(100 116 139 / 15%);
}
</style>
