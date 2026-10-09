<!-- UnitSettings.vue — 单元设置行内面板(原型 20 检查器的管理页子集):
     运行方案(空 = 默认方案)/ ×重复 / nRuns;编排模式(约束 5)另有
     「数据行」选择(空 = 裸基线,选定 = 只跑那行)。 -->
<template>
  <div class="uset" :data-testid="`suite-unit-settings-${member.scenarioId}`">
    <label class="uset-field">
      <span>运行方案</span>
      <select
        :value="unit.schemeId ?? ''"
        :disabled="loading"
        @change="patch({ schemeId: ($event.target as HTMLSelectElement).value || null })"
      >
        <option value="">默认方案</option>
        <option v-for="s in schemes" :key="s.schemeId" :value="s.schemeId">{{ s.name }}</option>
      </select>
    </label>

    <label v-if="orchestrate" class="uset-field">
      <span>数据行</span>
      <select
        :value="rowKey"
        :disabled="loading"
        @change="onRow($event)"
      >
        <option value="">裸基线(不带数据集行)</option>
        <option
          v-for="opt in rowOptions"
          :key="opt.key"
          :value="opt.key"
        >{{ opt.label }}</option>
      </select>
      <em v-if="!loading && !datasetRows.length" class="uset-note">方案未选数据集</em>
    </label>

    <label class="uset-field">
      <span>×重复</span>
      <input
        type="number" min="1" max="20"
        :value="unit.repeat ?? 1"
        @change="patch({ repeat: Math.max(1, Number(($event.target as HTMLInputElement).value) || 1) })"
      />
    </label>

    <label class="uset-field">
      <span>runs</span>
      <input
        type="number" min="1" max="100"
        :value="unit.nRuns ?? 1"
        @change="patch({ nRuns: Math.max(1, Number(($event.target as HTMLInputElement).value) || 1) })"
      />
    </label>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SuiteMemberItem, SuiteUnitConfig } from '@/api/suites'

const props = defineProps<{
  member: SuiteMemberItem
  unit: SuiteUnitConfig
  schemes: { schemeId: string; name: string }[]
  datasetRows: { datasetId: string; name: string; rowCount: number }[]
  orchestrate?: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'patch', patch: Partial<SuiteUnitConfig>): void
}>()

const rowOptions = computed(() => props.datasetRows.flatMap((d) =>
  Array.from({ length: d.rowCount }, (_, i) => ({
    key: `${d.datasetId}#${i}`,
    label: `${d.name || d.datasetId} · 第 ${i} 行`,
  }))))

const rowKey = computed(() => (props.unit.row
  ? `${props.unit.row!.datasetId}#${props.unit.row!.rowIndex}` : ''))

function onRow(ev: Event): void {
  const v = (ev.target as HTMLSelectElement).value
  if (!v) {
    emit('patch', { row: null })
    return
  }
  const [datasetId, idx] = v.split('#')
  emit('patch', { row: { datasetId, rowIndex: Number(idx) } })
}

function patch(p: Partial<SuiteUnitConfig>): void {
  emit('patch', p)
}
</script>

<style scoped>
.uset {
  display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
  margin: 4px 0 6px 26px; padding: 8px 12px;
  border: 1px solid rgb(59 130 246 / 30%); border-radius: 8px;
  background: rgb(59 130 246 / 5%); font-size: 12px;
}
.uset-field { display: flex; align-items: center; gap: 6px; }
.uset-field > span { color: rgb(100 116 139); }
.uset select, .uset input {
  padding: 4px 8px; font-size: 12px; border-radius: 6px;
  border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit;
}
.uset input { width: 56px; }
.uset-note { font-style: normal; font-size: 11px; color: rgb(100 116 139); }
</style>
