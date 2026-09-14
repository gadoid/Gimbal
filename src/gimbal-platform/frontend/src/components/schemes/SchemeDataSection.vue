<script setup lang="ts">
/** 方案工作台 · 数据区:数据集多选(行级勾选)、失效标注与移除。 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { DataSetSummary } from '@/types/scenario-composer'
import { scenarioDataSetUrl } from '@/utils/links'

const router = useRouter()

type Sel = { datasetId: string; rowIndexes?: number[] }

const props = defineProps<{
  modelValue: Sel[]
  dataSets: DataSetSummary[]
  scenarioId: string
}>()
const emit = defineEmits<{ 'update:modelValue': [v: Sel[]] }>()

const liveIds = computed(() => new Set(props.dataSets.map((d) => d.datasetId)))
const dead = computed(() => props.modelValue.filter((s) => !liveIds.value.has(s.datasetId)))
const rowsOf = (d: DataSetSummary) =>
  Array.from({ length: (d as { rowCount?: number }).rowCount ?? 0 }, (_, i) => i)

function toggleDataset(ds: DataSetSummary, on: boolean) {
  const rest = props.modelValue.filter((s) => s.datasetId !== ds.datasetId)
  emit('update:modelValue', on
    ? [...rest, { datasetId: ds.datasetId, rowIndexes: rowsOf(ds) }]
    : rest)
}
function toggleRow(dsId: string, idx: number, on: boolean) {
  const cur = props.modelValue.find((s) => s.datasetId === dsId)
  if (!cur) return
  const set = new Set(cur.rowIndexes ?? [])
  on ? set.add(idx) : set.delete(idx)
  const next = [...set].sort((a, b) => a - b)
  if (!next.length) {  // 行全清 = 取消整库
    emit('update:modelValue', props.modelValue.filter((s) => s.datasetId !== dsId))
    return
  }
  emit('update:modelValue',
    props.modelValue.map((s) => (s.datasetId === dsId ? { ...s, rowIndexes: next } : s)))
}
const isSelected = (dsId: string) => props.modelValue.some((s) => s.datasetId === dsId)
const rowChecked = (dsId: string, i: number) =>
  props.modelValue.find((s) => s.datasetId === dsId)?.rowIndexes?.includes(i) ?? false

function dropDead() {
  emit('update:modelValue', props.modelValue.filter((s) => liveIds.value.has(s.datasetId)))
}
</script>

<template>
  <section class="wb-section">
    <header class="zone-head">
      <span class="zone-name">数据</span>
      <el-button size="small" text type="primary"
        @click="router.push(scenarioDataSetUrl(scenarioId, 'new'))">+ 新建数据集</el-button>
    </header>

    <div v-if="dead.length" class="dead-row" data-testid="dead-row">
      <span>{{ dead.map((d) => d.datasetId).join('、') }} 已删除</span>
      <el-button size="small" type="danger" text data-testid="drop-dead" @click="dropDead">一键移除</el-button>
    </div>

    <div class="ds-tiles">
      <div v-for="d in dataSets" :key="d.datasetId" class="ds-tile" :class="{ on: isSelected(d.datasetId) }">
        <label data-testid="ds-tile">
          <input type="checkbox" :checked="isSelected(d.datasetId)"
            @change="toggleDataset(d, ($event.target as HTMLInputElement).checked)" />
          {{ d.name || d.datasetId }}({{ rowsOf(d).length }} 行)
        </label>
        <div v-if="isSelected(d.datasetId)" class="row-picks">
          <!-- rowsOf 已是 0 基索引数组,v-for 取数组值后直接用 r(原稿 i-1 会错位成 -1,0,1) -->
          <label v-for="r in rowsOf(d)" :key="r" class="row-pick">
            <input type="checkbox" :checked="rowChecked(d.datasetId, r)"
              @change="toggleRow(d.datasetId, r, ($event.target as HTMLInputElement).checked)" />
            行{{ r }}
          </label>
        </div>
      </div>
      <p v-if="!dataSets.length" class="hint">场景暂无数据集 — 不选即基线执行。</p>
    </div>
  </section>
</template>

<style scoped>
.wb-section { border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 12px 16px; display: flex; flex-direction: column; gap: 8px; }
.zone-head { display: flex; align-items: center; justify-content: space-between; }
.zone-name { font-weight: 600; }
.dead-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 10px; border: 1px dashed var(--el-color-danger-light-5); border-radius: 6px; color: var(--el-color-danger); font-size: 12px; }
.ds-tiles { display: flex; flex-direction: column; gap: 8px; }
.ds-tile { border: 1px solid var(--el-border-color-light); border-radius: 6px; padding: 8px 10px; }
.ds-tile.on { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.ds-tile label { cursor: pointer; }
.row-picks { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 6px; font-size: 12px; color: var(--el-text-color-secondary); }
.row-pick { cursor: pointer; }
</style>
