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

    <!-- 同名改名(map,第 3 步):上游输出名 → 本地输入名 —— 预检报
         INPUT_AMBIGUOUS(同名歧义)时在此消解;对应执行器 UnitDecl.map。 -->
    <div
      v-if="orchestrate"
      class="uset-map"
      data-testid="suite-unit-map"
    >
      <span class="uset-map-label">同名改名</span>
      <div
        v-for="(row, i) in mapRows"
        :key="i"
        class="uset-map-row"
      >
        <input
          class="uset-map-in"
          :value="row[0]"
          placeholder="上游输出名"
          @change="onMapRow(i, 0, ($event.target as HTMLInputElement).value)"
        />
        <span class="uset-map-arrow">→</span>
        <input
          class="uset-map-in"
          :value="row[1]"
          placeholder="本地输入名"
          @change="onMapRow(i, 1, ($event.target as HTMLInputElement).value)"
        />
        <button
          type="button" class="uset-map-x"
          :data-testid="`suite-unit-map-remove-${i}`"
          title="删除这行改名"
          @click="removeMapRow(i)"
        >×</button>
      </div>
      <button
        type="button" class="uset-map-add"
        data-testid="suite-unit-map-add"
        @click="addMapRow"
      >+ 改名</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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

// ── 同名改名(map)编辑:本地行态(新加的空行先留在本地,两端都填好
// 才随 change 提交;空端点的行不落 map)──────────────────────────
const mapRows = ref<[string, string][]>(Object.entries(props.unit.map ?? {}))
watch(() => props.unit.map, (m) => {
  // 外部(如服务端冲突重拉)更新 map 时重同步本地行
  const next = Object.entries(m ?? {})
  const same = next.length === mapRows.value.length
    && next.every(([k, v], i) => mapRows.value[i][0] === k && mapRows.value[i][1] === v)
  if (!same) mapRows.value = next
})

function commitMap(): void {
  const map: Record<string, string> = {}
  let incomplete = false
  for (const [k, v] of mapRows.value) {
    if (k.trim() && v.trim()) map[k.trim()] = v.trim()
    else if (k.trim() || v.trim()) incomplete = true
  }
  // 还有半填的行且 map 为空时不能回传:父级会把 map:{} 流回来,
  // watch 重同步把正在编辑的半行冲掉(上游名失焦的瞬间行就没了)。
  // 清空 map 的唯一路径是行被删光(removeMapRow)。
  if (incomplete && !Object.keys(map).length) return
  emit('patch', { map })
}

function addMapRow(): void {
  mapRows.value = [...mapRows.value, ['', '']]
}

function removeMapRow(i: number): void {
  mapRows.value = mapRows.value.filter((_, j) => j !== i)
  commitMap()
}

function onMapRow(i: number, pos: 0 | 1, value: string): void {
  mapRows.value = mapRows.value.map((r, j) =>
    (j === i ? [...r.slice(0, pos), value, ...r.slice(pos + 1)] as [string, string] : r))
  commitMap()
}
</script>

<style scoped>
.uset {
  display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
  margin: 4px 0 6px 26px; padding: 8px 12px;
  border: 1px solid var(--accent-soft-border); border-radius: 8px;
  background: var(--accent-soft); font-size: 12px;
}
.uset-field { display: flex; align-items: center; gap: 6px; }
.uset-field > span { color: rgb(100 116 139); }
.uset select, .uset input {
  padding: 4px 8px; font-size: 12px; border-radius: 6px;
  border: 1px solid rgb(100 116 139 / 35%); background: transparent; color: inherit;
}
.uset input { width: 56px; }
.uset-note { font-style: normal; font-size: 11px; color: rgb(100 116 139); }

/* 同名改名(map)编辑区 */
.uset-map {
  display: flex; flex-direction: column; gap: 6px;
  padding: 8px 10px; border-left: 1px dashed rgb(100 116 139 / 35%);
  padding-left: 12px; min-width: 250px;
}
.uset-map-label { font-size: 11.5px; color: rgb(100 116 139); }
.uset-map-row { display: flex; align-items: center; gap: 6px; }
.uset-map-in {
  width: 110px; padding: 3px 7px; font-size: 11.5px;
  font-family: ui-monospace, monospace;
  border-radius: 6px; border: 1px solid rgb(100 116 139 / 35%);
  background: transparent; color: inherit;
}
.uset-map-arrow { color: rgb(100 116 139); font-size: 11px; }
.uset-map-x {
  width: 18px; height: 18px; border-radius: 5px; cursor: pointer;
  border: 1px solid rgb(100 116 139 / 30%); background: transparent;
  color: inherit; font-size: 11px; line-height: 1; padding: 0;
}
.uset-map-add {
  align-self: flex-start; font-size: 11.5px; padding: 3px 9px;
  border-radius: 6px; cursor: pointer; color: #4338ca; background: var(--accent-soft);
  background: var(--accent-soft); border: 1px solid var(--accent-soft-border);
}
</style>
