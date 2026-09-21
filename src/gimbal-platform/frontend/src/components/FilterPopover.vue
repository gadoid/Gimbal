<!-- FilterPopover.vue — 高级过滤面板(批次 6 迁移新栈)
     通用筛选 popover:模块 / 系统 / Tags / 作者 / 优先级 / 更新时间
     触发器由父组件传入(高级过滤按钮),通过 v-model:open 控制开关。
     多选 = 原生 checkbox 数组(Vue 对 :value 绑定支持任意类型,与
     el-checkbox-group 语义同构);更新时间 = 分段钮;容器 = shadcn Popover。 -->
<template>
  <Popover v-model:open="open">
    <PopoverTrigger as-child>
      <button
        type="button"
        class="fp-trigger"
        :class="{ active: activeCount > 0 }"
        data-testid="filter-trigger"
        @click.stop
      >
        高级过滤
        <span v-if="activeCount > 0" class="filter-badge">{{ activeCount }}</span>
      </button>
    </PopoverTrigger>
    <PopoverContent align="end" class="w-[min(380px,calc(100vw-2rem))] p-0">
      <div class="filter-panel">
        <header class="filter-panel-head">
          <span class="filter-panel-title">筛选条件</span>
          <button
            type="button"
            class="fp-link"
            :disabled="activeCount === 0"
            data-testid="filter-reset"
            @click="resetFilters"
          >清空</button>
        </header>

        <div class="filter-panel-form">
          <!-- 模块 / 系统 / Tags / 作者:checkbox 芯片组(多选)。
               可选值优先来自 facets 端点(全量聚合,带计数,M3);
               facets 缺失(请求失败/旧后端)回落 pool uniq。 -->
          <div v-if="availableModules.length > 0" class="fp-item">
            <span class="fp-label">模块</span>
            <div class="fp-checks" data-testid="filter-modules">
              <label v-for="m in availableModules" :key="String(m.value)" class="fp-check">
                <input v-model="local.filters.modules" type="checkbox" :value="m.value" /> {{ m.value }}<span v-if="m.count !== undefined" class="fp-count">{{ m.count }}</span>
              </label>
            </div>
          </div>

          <div v-if="availableSystems.length > 0" class="fp-item">
            <span class="fp-label">系统</span>
            <div class="fp-checks" data-testid="filter-systems">
              <label v-for="s in availableSystems" :key="String(s.value)" class="fp-check">
                <input v-model="local.filters.systems" type="checkbox" :value="s.value" /> {{ s.value }}<span v-if="s.count !== undefined" class="fp-count">{{ s.count }}</span>
              </label>
            </div>
          </div>

          <div v-if="availableTags.length > 0" class="fp-item">
            <span class="fp-label">Tags</span>
            <div class="fp-checks" data-testid="filter-tags">
              <label v-for="t in availableTags" :key="String(t.value)" class="fp-check">
                <input v-model="local.filters.tags" type="checkbox" :value="t.value" /> {{ t.value }}<span v-if="t.count !== undefined" class="fp-count">{{ t.count }}</span>
              </label>
            </div>
          </div>

          <div v-if="availableAuthors.length > 0" class="fp-item">
            <span class="fp-label">作者</span>
            <div class="fp-checks" data-testid="filter-authors">
              <label v-for="a in availableAuthors" :key="String(a.value)" class="fp-check">
                <input v-model="local.filters.authors" type="checkbox" :value="a.value" /> {{ a.value }}<span v-if="a.count !== undefined" class="fp-count">{{ a.count }}</span>
              </label>
            </div>
          </div>

          <!-- 优先级:checkbox 芯片(固定 P1-P3 词表,计数取 facets) -->
          <div class="fp-item">
            <span class="fp-label">优先级</span>
            <div class="fp-checks" data-testid="filter-priorities">
              <label v-for="p in priorityOpts" :key="p.value" class="fp-check">
                <input v-model="local.filters.priorities" type="checkbox" :value="p.value" /> P{{ p.value }}<span v-if="p.count !== undefined" class="fp-count">{{ p.count }}</span>
              </label>
            </div>
          </div>

          <!-- 更新时间:分段钮 -->
          <div class="fp-item">
            <span class="fp-label">更新时间</span>
            <div class="seg" data-testid="filter-updated">
              <button
                v-for="opt in TIME_OPTS"
                :key="opt.value"
                type="button"
                class="seg-btn"
                :class="{ active: local.filters.updatedWithin === opt.value }"
                @click="local.filters.updatedWithin = opt.value"
              >{{ opt.label }}</button>
            </div>
          </div>
        </div>

        <footer class="filter-panel-foot">
          <span class="filter-foot-meta">
            <span v-if="filteredPreview !== undefined">
              匹配 <strong>{{ filteredPreview }}</strong> 条 / 共 {{ totalPreview }}
            </span>
            <span v-else>选择条件后即时生效</span>
          </span>
          <button type="button" class="fp-apply" data-testid="filter-apply" @click="commit">应用</button>
        </footer>
      </div>
    </PopoverContent>
  </Popover>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { emptyFilters, applyFiltersToList, type ScenarioFilters, type FilterRow } from '@/utils/filters'
import type { ScenarioFacets } from '@/api/scenario-composer'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

const TIME_OPTS = [
  { value: 'all', label: '全部' },
  { value: '24h', label: '24h' },
  { value: '7d', label: '7 天' },
  { value: '30d', label: '30 天' },
] as const

const props = defineProps<{
  modelValue: ScenarioFilters
  /** ``FilterRow`` = ``Partial<ScenarioFilterRow>`` + optional ``system`` —
   *  the V3 composer rows (Scenarios.vue pool) legitimately
   *  lack the legacy tags/module/author fields; missing fields simply
   *  don't produce filter options. */
  pool: readonly FilterRow[]
  /** M3:facets 聚合(全量可选值+计数)。提供时维度选项以它为准;
   *  缺省(请求失败/旧后端)回落 pool uniq。 */
  facets?: ScenarioFacets | null
}>()

const emit = defineEmits<{
  'update:modelValue': [v: ScenarioFilters]
}>()

const open = defineModel<boolean>('open', { default: false })

// Local copy for editing — commit on "应用"
const local = reactive<{ filters: ScenarioFilters }>({
  filters: { ...emptyFilters(), ...props.modelValue },
})

watch(
  () => props.modelValue,
  (v) => {
    Object.assign(local.filters, emptyFilters(), v)
  },
  { deep: true },
)

/** 选项 = {value, count?}:facets 有计数,池兜底只有值。 */
type Opt = { value: string | number; count?: number }

function _facetOpts(dim: keyof ScenarioFacets): Opt[] | null {
  if (!props.facets) return null
  // 空值(如旧数据缺 author)不产芯片,与池兜底的 filter(Boolean) 同口径
  return props.facets[dim].filter((o) => o.value !== '' && o.value != null)
}

function _poolOpts(values: (string | undefined | null)[]): Opt[] {
  return Array.from(new Set(values.filter((v): v is string => !!v)))
    .map((value) => ({ value }))
}

const availableModules = computed<Opt[]>(() =>
  _facetOpts('modules')
  ?? _poolOpts(props.pool.map((c) => c.module)),
)
const availableSystems = computed<Opt[]>(() =>
  _facetOpts('systems')
  ?? _poolOpts(props.pool.flatMap((c) => c.system ?? [])),
)
const availableTags = computed<Opt[]>(() =>
  _facetOpts('tags')
  ?? _poolOpts(props.pool.flatMap((c) => c.tags ?? [])),
)
const availableAuthors = computed<Opt[]>(() =>
  _facetOpts('authors')
  ?? _poolOpts(props.pool.map((c) => c.author)),
)
/** P1-P3 固定词表(与后端 priority 枚举一致),计数从 facets 取。 */
const priorityOpts = computed<Opt[]>(() =>
  [1, 2, 3].map((value) => ({
    value,
    count: props.facets?.priorities.find((p) => Number(p.value) === value)?.count,
  })),
)

const activeCount = computed(() => {
  let n = 0
  const f = local.filters
  if (f.modules.length) n++
  if (f.systems.length) n++
  if (f.tags.length) n++
  if (f.authors.length) n++
  if (f.priorities.length) n++
  if (f.updatedWithin !== 'all') n++
  return n
})

const totalPreview = computed(() => props.pool.length)
const filteredPreview = computed(() => {
  const list = applyFiltersToList(props.pool, local.filters)
  return list.length
})

function commit() {
  emit('update:modelValue', { ...local.filters })
  open.value = false
}

function resetFilters() {
  Object.assign(local.filters, emptyFilters())
}
</script>

<style scoped>
/* 触发器:按钮形制,激活态描边高亮(原 el-button primary/plain 语义) */
.fp-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  font-size: 12px;
  color: #374151;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  cursor: pointer;
}
.fp-trigger:hover { color: #111827; border-color: #9ca3af; }
.fp-trigger.active {
  color: #2f6fed;
  border-color: #2f6fed;
  background: #e7efff;
}

.filter-panel {
  font-size: 12px;
}

.filter-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--color-border-tertiary, #e1e5eb);
}

.filter-panel-title {
  color: var(--color-text-secondary, #64748b);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.fp-link {
  padding: 0;
  border: none;
  background: none;
  color: #2f6fed;
  font-size: 12px;
  cursor: pointer;
}
.fp-link:disabled { color: #c4c9d2; cursor: not-allowed; }

.filter-panel-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px 12px 4px;
  max-height: 50vh;
  overflow-y: auto;
}

.fp-item { display: flex; flex-direction: column; gap: 4px; }
.fp-label {
  color: var(--color-text-secondary, #64748b);
  font-size: 11px;
  font-weight: 600;
}

/* checkbox 芯片组:换行流式,上限滚动(选项可能很多) */
.fp-checks {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 6px;
  max-height: 96px;
  overflow-y: auto;
}
.fp-check {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: 11.5px;
  color: #374151;
  border: 1px solid #e1e5eb;
  border-radius: 10px;
  cursor: pointer;
  user-select: none;
}
.fp-check:has(input:checked) {
  color: #2f6fed;
  border-color: #2f6fed;
  background: #e7efff;
}
.fp-check input { accent-color: #2f6fed; margin: 0; }

/* facets 计数徽标:弱化的次级信息(池兜底时不渲染) */
.fp-count {
  margin-left: 2px;
  color: #9ca3af;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}
.fp-check:has(input:checked) .fp-count { color: #6f9bff; }

/* 分段钮(更新时间) */
.seg { display: inline-flex; border: 1px solid #e1e5eb; border-radius: 6px; overflow: hidden; }
.seg-btn {
  padding: 4px 10px;
  font-size: 11.5px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #5a6273;
}
.seg-btn.active { background: #2f6fed; color: #fff; font-weight: 600; }

.filter-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 5px;
  color: white;
  font-size: 10px;
  font-weight: 700;
  background: #2f6fed;
  border-radius: 999px;
}

.filter-panel-foot {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-top: 1px dashed var(--color-border-tertiary, #e1e5eb);
}

.filter-foot-meta {
  color: var(--color-text-secondary, #64748b);
  font-size: 11.5px;
}

.filter-foot-meta strong {
  color: #2f6fed;
  font-weight: 700;
}

.fp-apply {
  padding: 5px 14px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  background: #2f6fed;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.fp-apply:hover { background: #265fd4; }
</style>
