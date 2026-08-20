<!-- FilterPopover.vue — 高级过滤面板
     通用筛选 popover：模块 / 系统 / Tags / 作者 / 优先级 / 更新时间
     触发器由父组件传入（高级过滤按钮），通过 v-model:open 控制开关
-->
<template>
  <el-popover
    :width="380"
    placement="bottom-end"
    trigger="click"
    :show-arrow="false"
    popper-class="filter-popover"
    v-model:visible="open"
  >
    <template #reference>
      <el-button
        :type="activeCount > 0 ? 'primary' : ''"
        :plain="activeCount === 0"
        :icon="Operation"
        @click.stop
      >
        高级过滤
        <span v-if="activeCount > 0" class="filter-badge">{{ activeCount }}</span>
      </el-button>
    </template>

    <div class="filter-panel">
      <header class="filter-panel-head">
        <span class="filter-panel-title">筛选条件</span>
        <el-button
          link
          type="primary"
          :disabled="activeCount === 0"
          @click="resetFilters"
        >清空</el-button>
      </header>

      <el-form label-position="top" class="filter-panel-form">
        <!-- 模块 -->
        <el-form-item v-if="availableModules.length > 0" label="模块">
          <el-select
            v-model="local.filters.modules"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="全选"
            class="filter-full"
          >
            <el-option
              v-for="m in availableModules"
              :key="m"
              :value="m"
              :label="m"
            />
          </el-select>
        </el-form-item>

        <!-- 系统 (scenario library rows carry meta.system flattened) -->
        <el-form-item v-if="availableSystems.length > 0" label="系统">
          <el-select
            v-model="local.filters.systems"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="全选"
            class="filter-full"
          >
            <el-option
              v-for="s in availableSystems"
              :key="s"
              :value="s"
              :label="s"
            />
          </el-select>
        </el-form-item>

        <!-- Tags -->
        <el-form-item v-if="availableTags.length > 0" label="Tags">
          <el-select
            v-model="local.filters.tags"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="全选"
            class="filter-full"
          >
            <el-option
              v-for="t in availableTags"
              :key="t"
              :value="t"
              :label="t"
            />
          </el-select>
        </el-form-item>

        <!-- 作者 -->
        <el-form-item v-if="availableAuthors.length > 0" label="作者">
          <el-select
            v-model="local.filters.authors"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="全选"
            class="filter-full"
          >
            <el-option
              v-for="a in availableAuthors"
              :key="a"
              :value="a"
              :label="a"
            />
          </el-select>
        </el-form-item>

        <!-- 优先级 -->
        <el-form-item label="优先级">
          <el-checkbox-group v-model="local.filters.priorities" class="filter-prio">
            <el-checkbox :value="1" label="P1" />
            <el-checkbox :value="2" label="P2" />
            <el-checkbox :value="3" label="P3" />
          </el-checkbox-group>
        </el-form-item>

        <!-- 更新时间 -->
        <el-form-item label="更新时间">
          <el-radio-group v-model="local.filters.updatedWithin" class="filter-time">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="24h">24h</el-radio-button>
            <el-radio-button value="7d">7 天</el-radio-button>
            <el-radio-button value="30d">30 天</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <footer class="filter-panel-foot">
        <span class="filter-foot-meta">
          <span v-if="filteredPreview !== undefined">
            匹配 <strong>{{ filteredPreview }}</strong> 条 / 共 {{ totalPreview }}
          </span>
          <span v-else>选择条件后即时生效</span>
        </span>
        <el-button type="primary" @click="commit">应用</el-button>
      </footer>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Operation } from '@element-plus/icons-vue'
import { emptyFilters, applyFiltersToList, type ScenarioFilters, type FilterRow } from '@/utils/filters'

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

const isActive = (f: ScenarioFilters) =>
  f.modules.length > 0 ||
  f.systems.length > 0 ||
  f.tags.length > 0 ||
  f.authors.length > 0 ||
  f.priorities.length > 0 ||
  f.updatedWithin !== 'all'

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
.filter-panel {
  font-size: 12px;
}

.filter-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--color-border-tertiary);
}

.filter-panel-title {
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.filter-panel-form :deep(.el-form-item) {
  margin-bottom: 12px;
}

.filter-panel-form :deep(.el-form-item__label) {
  padding-bottom: 4px;
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 600;
}

.filter-full {
  width: 100%;
}

.filter-prio {
  display: flex;
  gap: 6px;
}
.filter-prio :deep(.el-checkbox) {
  margin-right: 0;
}

.filter-time {
  width: 100%;
}
.filter-time :deep(.el-radio-button__inner) {
  padding: 4px 10px;
  font-size: 11.5px;
}

.filter-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  margin-left: 4px;
  padding: 0 5px;
  color: white;
  font-size: 10px;
  font-weight: 700;
  background: var(--accent);
  border-radius: 999px;
}

.filter-panel-foot {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding-top: 10px;
  margin-top: 6px;
  border-top: 1px dashed var(--color-border-tertiary);
}

.filter-foot-meta {
  color: var(--color-text-secondary);
  font-size: 11.5px;
}

.filter-foot-meta strong {
  color: var(--accent);
  font-weight: 700;
}
</style>
