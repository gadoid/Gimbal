<!-- ImpactDrawer —— 影响清单抽屉(spec §5.2):按 field 分组,直填/模板 + 数据集列标注。 -->
<template>
  <el-drawer
    :model-value="modelValue"
    :title="drawerTitle"
    size="480px"
    @update:model-value="emit('update:modelValue', $event)"
    @open="load"
  >
    <div v-loading="loading">
      <p v-if="error" class="error">{{ error }}</p>
      <el-empty v-else-if="groups.length === 0" description="该 endpoint 无引用" />
      <div v-for="g in groups" :key="g.field" class="field-group">
        <h4>
          {{ g.field }}
          <el-tag size="small">{{ g.items.length }}</el-tag>
        </h4>
        <ul>
          <li v-for="(it, i) in g.items" :key="i">
            <span class="mono">{{ it.scenarioId }}</span> · 步骤 {{ it.stepIndex }}
            <template v-if="it.source"> · {{ it.source }}</template>
            <el-tag size="small" :type="it.viaVar ? 'warning' : 'info'">
              {{ it.field === null ? '无业务字段' : (it.viaVar ? '模板' : '直填') }}
            </el-tag>
            <span v-if="it.viaVar" class="via">
              {{ it.viaVar }}
              <template v-if="it.datasetId">
                → {{ it.datasetId }}.{{ it.datasetColumn }}
              </template>
            </span>
          </li>
        </ul>
      </div>
    </div>
    <template #footer>
      <el-button
        class="open-batch-btn"
        type="primary"
        :disabled="groups.length === 0"
        @click="emit('openBatch')"
      >开批次</el-button>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import * as api from '@/api/adaptations'
import type { ImpactItem } from '@/api/adaptations'

const props = defineProps<{
  modelValue: boolean
  endpointId: string
  fromVersion?: string
  toVersion?: string
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'openBatch'): void
}>()

const items = ref<ImpactItem[]>([])
const loading = ref(false)
const error = ref('')

const drawerTitle = computed(() =>
  `影响清单 — ${props.endpointId}` +
  (props.toVersion ? ` (${props.fromVersion} → ${props.toVersion})` : ''))

const groups = computed(() => {
  const byField = new Map<string, ImpactItem[]>()
  for (const it of items.value) {
    const key = it.field ?? '(无业务字段)'
    if (!byField.has(key)) byField.set(key, [])
    byField.get(key)!.push(it)
  }
  return [...byField.entries()].map(([field, list]) => ({ field, items: list }))
})

// element-plus 只在 false→true 变化时 emit open;挂载即打开时补拉一次。
onMounted(() => {
  if (props.modelValue) load()
})

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    items.value = await api.impact(props.endpointId)
  } catch (e) {
    error.value = api.errMsg(e, '影响查询失败,稍后重试')
    items.value = []
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.field-group { margin-bottom: 14px; }
.field-group h4 { margin: 0 0 6px; }
.field-group ul { margin: 0; padding-left: 18px; }
.field-group li { line-height: 1.9; }
.via { color: #909399; }
.error { color: #f56c6c; }
.mono { font-family: monospace; }
</style>
