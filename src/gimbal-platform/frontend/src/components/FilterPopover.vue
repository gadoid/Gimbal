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
          <!-- 模块 / 系统 / Tags / 作者:checkbox 芯片组(多选) -->
          <div v-if="availableModules.length > 0" class="fp-item">
            <span class="fp-label">模块</span>
            <div class="fp-checks" data-testid="filter-modules">
              <label v-for="m in availableModules" :key="m" class="fp-check">
                <input v-model="local.filters.modules" type="checkbox" :value="m" /> {{ m }}
              </label>
            </div>
          </div>

          <div v-if="availableSystems.length > 0" class="fp-item">
            <span class="fp-label">系统</span>
            <div class="fp-checks" data-testid="filter-systems">
              <label v-for="s in availableSystems" :key="s" class="fp-check">
                <input v-model="local.filters.systems" type="checkbox" :value="s" /> {{ s }}
              </label>
            </div>
          </div>

          <div v-if="availableTags.length > 0" class="fp-item">
            <span class="fp-label">Tags</span>
            <div class="fp-checks" data-testid="filter-tags">
              <label v-for="t in availableTags" :key="t" class="fp-check">
                <input v-model="local.filters.tags" type="checkbox" :value="t" /> {{ t }}
              </label>
            </div>
          </div>

          <div v-if="availableAuthors.length > 0" class="fp-item">
            <span class="fp-label">作者</span>
            <div class="fp-checks" data-testid="filter-authors">
              <label v-for="a in availableAuthors" :key="a" class="fp-check">
                <input v-model="local.filters.authors" type="checkbox" :value="a" /> {{ a }}
              </label>
            </div>
          </div>

          <!-- 优先级:checkbox 芯片(数值 value) -->
          <div class="fp-item">
            <span class="fp-label">优先级</span>
            <div class="fp-checks" data-testid="filter-priorities">
              <label class="fp-check"><input v-model="local.filters.priorities" type="checkbox" :value="1" /> P1</label>
              <label class="fp-check"><input v-model="local.filters.priorities" type="checkbox" :value="2" /> P2</label>
              <label class="fp-check"><input v-model="local.filters.priorities" type="checkbox" :value="3" /> P3</label>
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

const availableModules = computed(() =>
  unique(props.pool.map((c) => c.module).filter(Boolean)),
)
const availableSystems = computed(() =>
  unique(props.pool.flatMap((c) => c.system ?? []).filter(Boolean)),
)
const availableTags = computed(() =>
  unique(props.pool.flatMap((c) => c.tags ?? []).filter(Boolean)),
)
const availableAuthors = computed(() =>
  unique(props.pool.map((c) => c.author).filter(Boolean)),
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

function unique<T>(arr: T[]): T[] {
  return Array.from(new Set(arr))
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
