<!-- OpPreview —— 单条 op 预览(§6.2):零后端改动,场景 step 片段前端取。 -->
<template>
  <div v-loading="loading" class="op-preview">
    <p v-if="error" class="error">{{ error }}</p>

    <template v-else-if="op.opType === 'renameVar'">
      <span class="mono">{{ '${var.' + String(op.payload.from) + '}' }}</span>
      →
      <span class="mono">{{ '${var.' + String(op.payload.to) + '}' }}</span>
      <span class="hint">{{ refCount }} 处引用</span>
    </template>

    <template v-else-if="isDatasetOp">
      <span>
        数据集 <b class="mono">{{ op.datasetId }}</b> · 列
        <code>{{ columnLabel }}</code>
        <template v-if="'to' in op.payload"> → <code>{{ op.payload.to }}</code></template>
      </span>
      <table v-if="mapEntries.length" class="map-table">
        <tr v-for="(row, i) in mapEntries" :key="i">
          <td class="mono">{{ row[0] }} → {{ row[1] }}</td>
        </tr>
      </table>
    </template>

    <!-- CARRY_OPS(T16):值表层,无场景落点 —— 不拉场景,直渲 payload。 -->
    <template v-else-if="isCarryOp">
      <span class="mono">
        carry 值表({{ carryScopeLabel }})
        <template v-if="op.opType === 'renameCarryPath'">
          :<code>{{ op.payload.from }}</code> → <code>{{ op.payload.to }}</code>
        </template>
        <template v-else-if="op.opType === 'addCarryBinding'">
          + <code>{{ op.payload.path }}</code>
          <template v-if="'value' in op.payload">
            = {{ JSON.stringify(op.payload.value) }}
          </template>
        </template>
        <template v-else>
          − <code>{{ op.payload.path }}</code>
        </template>
      </span>
    </template>

    <template v-else-if="step">
      <span class="mono">
        步骤 {{ op.payload.step }} · {{ fieldLabel }}
        <template v-if="'to' in op.payload">
          → {{ op.payload.to }}
        </template>
        <template v-if="op.opType === 'rebindField'">
          → {{ '${var.' + String(op.payload.var) + '}' }}
        </template>
        <template v-if="op.opType === 'addField'">
          = {{ JSON.stringify(op.payload.value) }}
        </template>
      </span>
      <pre class="fragment">{{ fragmentText }}</pre>
      <table v-if="mapEntries.length" class="map-table">
        <tr v-for="(row, i) in mapEntries" :key="i">
          <td class="mono">{{ row[0] }} → {{ row[1] }}</td>
        </tr>
      </table>
    </template>

    <el-empty v-else description="步骤不存在(场景可能已变更)" :image-size="40" />
  </div>
</template>

<script lang="ts">
import type { Scenario } from '@/types/scenario-composer'

// 场景按 id 模块级缓存:一个批次的 ops 常集中同几个场景,只拉一次
// (放在 <script>(非 setup)块:script setup 每实例执行一次,Map 会退化为实例级)
const scenarioCache = new Map<string, Scenario>()
</script>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { OpOut } from '@/api/adaptations'
import { getScenario } from '@/api/scenario-composer'

const props = defineProps<{ op: OpOut }>()

const loading = ref(false)
const error = ref('')
const scenario = ref<Awaited<ReturnType<typeof getScenario>> | null>(null)

const isDatasetOp = computed(() => ['renameDatasetColumn', 'mapDatasetValues']
  .includes(props.op.opType))

/** CARRY_OPS:值表 op,scenarioId=null(D1 免场景),不进场景拉取分支。 */
const isCarryOp = computed(() => ['renameCarryPath', 'addCarryBinding',
  'removeCarryBinding'].includes(props.op.opType))

const carryScopeLabel = computed(() =>
  String(props.op.payload.service ?? '全局默认'))

const columnLabel = computed(() =>
  String(props.op.payload.column ?? props.op.payload.from ?? ''))

const fieldLabel = computed(() =>
  String(props.op.payload.field ?? props.op.payload.from ?? ''))

const step = computed<Record<string, unknown> | null>(() => {
  if (!scenario.value) return null
  const idx = Number(props.op.payload.step)
  const steps = (scenario.value as { steps?: unknown[] }).steps ?? []
  const s = steps[idx]
  return (s ?? null) as Record<string, unknown> | null
})

const mapEntries = computed<[string, string][]>(() => {
  const m = props.op.payload.map
  if (!m || typeof m !== 'object') return []
  return Object.entries(m as Record<string, string>)
})

// 命中字段的容器(body/headers);addField 目标默认 body
const fragmentText = computed(() => {
  if (!step.value) return ''
  const st = step.value as {
    request?: { body?: Record<string, unknown> }
    api?: Record<string, Record<string, unknown>>
  }
  const containers: Record<string, Record<string, unknown>> = {
    body: st.request?.body ?? {},
    headers: st.api?.headers ?? {},
  }
  const field = fieldLabel.value
  const hit = Object.values(containers).find((c) => field in c)
  return JSON.stringify(hit ?? containers.body, null, 2)
})

const refCount = computed(() => {
  if (!scenario.value) return 0
  const needle = `\${var.${String(props.op.payload.from)}}`
  return JSON.stringify(scenario.value).split(needle).length - 1
})

onMounted(async () => {
  // carry op(值表层)与数据集 op 不拉场景;scenarioId=null 直接守卫
  if (isCarryOp.value || props.op.scenarioId === null) return
  if (props.op.opType === 'renameVar' || isDatasetOp.value) {
    // renameVar 引用计数需要场景;数据集 op 只用 datasetId,不拉场景
    if (props.op.opType !== 'renameVar') return
  }
  if (scenarioCache.has(props.op.scenarioId)) {
    scenario.value = scenarioCache.get(props.op.scenarioId) ?? null
    return
  }
  loading.value = true
  try {
    scenario.value = await getScenario(props.op.scenarioId)
    scenarioCache.set(props.op.scenarioId, scenario.value)
  } catch {
    error.value = '场景加载失败(可能已删除)'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.op-preview { font-size: 13px; }
.fragment {
  margin: 6px 0 0;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  max-height: 180px;
  overflow: auto;
  font-size: 12px;
}
.map-table { margin-top: 6px; border-collapse: collapse; }
.map-table td { padding: 2px 8px; border: 1px solid #ebeef5; }
.hint { margin-left: 8px; color: #909399; }
.error { color: #f56c6c; }
.mono { font-family: monospace; }
</style>
