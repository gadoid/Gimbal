<!--
  FieldStateSearch.vue — 字段找回搜索框(2026-09-07 spec §2.2)

  定位手段不是添加机制(09-05 §5.4):扫全量语料(含 carry 与容器,
  carry 正是搜索语料),命中行直接切状态 —— carry 字段由此可找回。
  组件只上抛 select(path, target) / reset(path):级联增量与批量
  落地由 Canvas 统一(与行尾下拉同通路,§2.3/§2.4)。
-->
<template>
  <div class="fss-search">
    <input
      v-model="raw"
      class="fss-search-input"
      type="text"
      placeholder="搜索字段(含 carry 传递面)"
      @focus="panelOpen = true"
      @blur="panelOpen = false"
      @keydown.esc="clear"
    />
    <div
      v-if="query && hits.length && panelOpen"
      class="fss-search-panel"
      @mousedown.prevent
    >
      <div v-if="hits.length > LIMIT" class="fss-search-more">
        命中 {{ hits.length }} 条,显示前 {{ LIMIT }} 条(继续输入缩小范围)
      </div>
      <div v-for="row in shown" :key="row.path" class="fss-search-row">
        <span class="fss-search-path">
          <span v-if="row.breadcrumb" class="fss-breadcrumb">{{ row.breadcrumb }} › </span>{{ row.name }}
          <code class="fss-search-type">{{ row.type }}</code>
        </span>
        <span class="fss-search-res" :data-state="row.resolved">{{ row.resolved }}</span>
        <FieldStateSelect
          :state="row.resolved"
          :overlay="row.overlay"
          @change="(t) => emit('select', row.path, t)"
          @reset="emit('reset', row.path)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import FieldStateSelect from './FieldStateSelect.vue'
import type { FieldSearchRow } from '@/utils/declarations'
import type { FieldState } from '@/types/plate'

const props = defineProps<{
  /** 搜索语料(searchCorpus 预计算,Canvas 传入;含解析态与 overlay) */
  corpus: FieldSearchRow[]
}>()

const emit = defineEmits<{
  /** 命中行选择状态(级联与批量落地归 Canvas,§2.4) */
  'select': [path: string, target: FieldState]
  /** ↺ 重置:清该条增量(仅自身,§2.3) */
  'reset': [path: string]
}>()

/** 防撞上限(200+ 字段端点防淹没,§2.1) */
const LIMIT = 50
/** 防抖 200ms(§2.5) */
const DEBOUNCE_MS = 200

const raw = ref('')
const query = ref('')
const panelOpen = ref(true)
let timer: ReturnType<typeof setTimeout> | undefined

watch(raw, (v) => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    query.value = v.trim()
  }, DEBOUNCE_MS)
})

onBeforeUnmount(() => clearTimeout(timer))

const hits = computed(() => {
  const q = query.value.toLowerCase()
  if (!q) return []
  return props.corpus.filter((r) =>
    r.name.toLowerCase().includes(q)
    || r.path.toLowerCase().includes(q)
    || r.description.toLowerCase().includes(q))
})

const shown = computed(() => hits.value.slice(0, LIMIT))

function clear(): void {
  clearTimeout(timer)
  raw.value = ''
  query.value = ''
  panelOpen.value = false
}
</script>

<style scoped>
.fss-search { position: relative; display: inline-block; }
.fss-search-input {
  width: 220px;
  padding: 2px 8px;
  font-size: 12px;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  background: transparent;
  color: inherit;
}
.fss-search-input:focus { outline: none; border-color: var(--el-color-primary, #409eff); }
.fss-search-panel {
  position: absolute;
  z-index: 30;
  top: calc(100% + 4px);
  left: 0;
  max-height: 300px;
  overflow-y: auto;
  min-width: 380px;
  padding: 4px 6px;
  background: var(--el-bg-color-overlay, #fff);
  border: 1px solid var(--el-border-color-light, #e4e7ed);
  border-radius: 4px;
  box-shadow: var(--el-box-shadow-light, 0 0 12px rgba(0, 0, 0, .12));
  font-size: 12px;
}
.fss-search-more { padding: 2px 4px; color: var(--el-text-color-secondary, #909399); }
.fss-search-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 4px;
  border-radius: 3px;
}
.fss-search-row:hover { background: var(--el-fill-color-light, #f5f7fa); }
.fss-search-path { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fss-breadcrumb { color: var(--el-text-color-secondary, #909399); }
.fss-search-type { margin-left: 4px; color: var(--el-text-color-secondary, #909399); }
.fss-search-res { color: var(--el-text-color-secondary, #909399); min-width: 46px; text-align: right; }
.fss-search-res[data-state='carry'] { color: var(--el-color-info, #909399); font-style: italic; }
</style>
