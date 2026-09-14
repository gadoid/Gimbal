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
      <span class="zone-count">{{ dataSets.length }}</span>
      <span class="zone-spacer"></span>
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
          <span class="ds-name">{{ d.name || d.datasetId }}</span>
          <span class="row-count">{{ rowsOf(d).length }} 行</span>
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
      <div v-if="!dataSets.length" class="empty-state">
        <p>场景暂无数据集 — 不选即基线执行。</p>
        <el-button size="small" type="primary" plain
          @click="router.push(scenarioDataSetUrl(scenarioId, 'new'))">+ 新建数据集</el-button>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* 分区卡片:对齐平台卡片体系(CaseDataSetsList .card / 编辑器 .meta) */
.wb-section {
  background: #fff; border: 1px solid var(--color-border-tertiary);
  border-radius: 8px; padding: 12px 16px;
  display: flex; flex-direction: column; gap: 10px;
}
/* zone-head 体系(CaseDataSetsList 同款):左竖线标题 + 计数徽标 + 弹性空位 */
.zone-head { display: flex; align-items: center; gap: 10px; }
.zone-name {
  font-size: 14px; font-weight: 700; color: var(--color-text-primary);
  padding-left: 10px; border-left: 3px solid var(--accent);
}
.zone-count {
  padding: 1px 6px; font-size: 11px; font-weight: 600;
  color: var(--color-text-secondary); background: #f1f5f9; border-radius: 3px;
}
.zone-spacer { flex: 1; }

/* 失效行:amber 软提示条(DataSetEditor dead-keys-bar 同款语言) */
.dead-row {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 5px 10px; font-size: 11px; color: #b45309;
  background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px;
}

/* tile 网格:平台卡片网格形制(CaseDataSetsList .grid auto-fill) */
.ds-tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; }
.ds-tile {
  background: #fff; border: 1px solid var(--color-border-tertiary); border-radius: 8px;
  padding: 10px 12px; transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.ds-tile:hover { border-color: var(--accent); box-shadow: 0 1px 6px rgba(67, 56, 202, 0.12); }
/* 选中态:浅 accent 底 + 左侧竖条(与左栏选中项同一语言) */
.ds-tile.on {
  border-color: var(--accent-soft-border); background: #f0f5ff;
  box-shadow: inset 2px 0 0 var(--accent);
}
.ds-tile label {
  display: flex; align-items: center; gap: 8px; cursor: pointer;
}
.ds-tile input[type="checkbox"] { accent-color: var(--accent); flex: none; }
.ds-name {
  flex: 1; min-width: 0; font-size: 13px; font-weight: 600;
  color: var(--color-text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
/* 行数徽标:CaseDataSetsList .row-count 同款 chip */
.row-count {
  flex: none; padding: 1px 6px; font-family: var(--font-mono); font-size: 10px;
  font-weight: 600; color: var(--color-text-secondary);
  background: #f1f5f9; border-radius: 3px; white-space: nowrap;
}

/* 行级勾选展开态:换行排版 + 虚线分隔(选中 tile 的附属区) */
.row-picks {
  display: flex; flex-wrap: wrap; gap: 4px 6px; margin-top: 8px; padding-top: 8px;
  border-top: 1px dashed var(--color-border-tertiary);
}
.row-pick {
  display: inline-flex; align-items: center; gap: 4px; cursor: pointer;
  padding: 2px 8px; border: 1px solid transparent; border-radius: 4px;
  font-size: 12px; color: var(--color-text-secondary);
}
.row-pick:hover { border-color: var(--color-border-tertiary); background: #fff; }
.row-pick input[type="checkbox"] { accent-color: var(--accent); margin: 0; }

/* 空态(三处统一形状:dashed 框 + muted 文案 + 引导按钮) */
.empty-state {
  grid-column: 1 / -1;
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  padding: 18px 16px; text-align: center;
  border: 1px dashed var(--color-border-tertiary); border-radius: 8px;
}
.empty-state p { margin: 0; font-size: 12px; color: var(--color-text-tertiary); }
</style>
