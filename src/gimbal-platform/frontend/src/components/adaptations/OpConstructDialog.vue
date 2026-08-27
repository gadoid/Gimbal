<!-- OpConstructDialog —— 8 类人工构造 op(§6.3,全量类型 + mergeSeed 预填)。 -->
<template>
  <el-dialog
    :model-value="modelValue"
    :title="mergeSeed ? '合并为 renameField' : '构造 op'"
    width="560px"
    @update:model-value="emit('update:modelValue', $event)"
    @open="onOpen"
  >
    <el-form label-width="110px">
      <el-form-item label="类型">
        <el-select v-model="form.opType" :disabled="Boolean(mergeSeed)">
          <el-option
            v-for="t in OP_TYPES"
            :key="t.value"
            :label="t.label"
            :value="t.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="场景">
        <el-select v-model="form.scenarioId" placeholder="选择场景">
          <el-option
            v-for="s in scenarios"
            :key="s.scenarioId"
            :label="s.scenarioId"
            :value="s.scenarioId"
          />
        </el-select>
      </el-form-item>

      <!-- 数据集 op:数据集 + 列 -->
      <template v-if="opTypeIn(['renameDatasetColumn', 'mapDatasetValues'])">
        <el-form-item label="数据集">
          <el-select v-model="form.datasetId" placeholder="选择数据集">
            <el-option
              v-for="d in datasets"
              :key="d.datasetId"
              :label="d.datasetId"
              :value="d.datasetId"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="form.opType === 'mapDatasetValues'"
          label="列名(column)"
        >
          <el-input v-model="form.column" />
        </el-form-item>
        <el-form-item v-else label="列 from → to">
          <el-input v-model="form.from" placeholder="from" />
          <el-input v-model="form.to" placeholder="to" class="pair" />
        </el-form-item>
      </template>

      <!-- renameVar:调色板下拉 -->
      <template v-else-if="form.opType === 'renameVar'">
        <el-form-item label="var from → to">
          <el-select v-model="form.from" placeholder="from">
            <el-option v-for="v in varNames" :key="v" :label="v" :value="v" />
          </el-select>
          <el-select v-model="form.to" placeholder="to" class="pair">
            <el-option v-for="v in varNames" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
      </template>

      <!-- STEP_OPS -->
      <template v-else>
        <el-form-item label="步骤(step)">
          <el-input-number v-model="form.step" :min="0" />
        </el-form-item>
        <el-form-item label="字段">
          <el-input
            v-model="fieldModel"
            :placeholder="form.opType === 'renameField' ? 'from' : 'field'"
          />
          <el-input
            v-if="form.opType === 'renameField'"
            v-model="form.to"
            placeholder="to"
            class="pair"
          />
        </el-form-item>
        <el-form-item v-if="form.opType === 'addField'" label="值(value)">
          <el-input v-model="form.value" />
        </el-form-item>
        <el-form-item v-if="form.opType === 'rebindField'" label="目标 var">
          <el-select v-model="form.varName" placeholder="调色板">
            <el-option v-for="v in varNames" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
      </template>

      <!-- map 编辑器(mapValue / mapDatasetValues) -->
      <el-form-item
        v-if="opTypeIn(['mapValue', 'mapDatasetValues'])"
        label="值映射(map)"
      >
        <div class="map-rows">
          <div v-for="(row, i) in form.mapRows" :key="i" class="map-row">
            <el-input v-model="row.key" placeholder="原值(键手输)" />
            <span>→</span>
            <el-input v-model="row.value" placeholder="新值" />
            <el-button link type="danger" @click="form.mapRows.splice(i, 1)">
              删
            </el-button>
          </div>
          <el-button link type="primary" @click="form.mapRows.push({ key: '', value: '' })">
            + 加一行
          </el-button>
          <p class="hint">草案 payload 不含值域;候选可从预览的当前值抄录</p>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">
        创建
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as api from '@/api/adaptations'
import type { MergeSeed, OpOut } from '@/api/adaptations'
import { getScenario, listDataSets, listScenarios } from '@/api/scenario-composer'

const props = defineProps<{
  modelValue: boolean
  batchId: string
  mergeSeed?: MergeSeed | null
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'created', op: OpOut): void
}>()

const OP_TYPES = [
  { value: 'renameVar', label: 'renameVar(变量重命名)' },
  { value: 'renameField', label: 'renameField(字段重命名)' },
  { value: 'addField', label: 'addField(新增字段)' },
  { value: 'removeField', label: 'removeField(删除字段)' },
  { value: 'rebindField', label: 'rebindField(改绑变量)' },
  { value: 'mapValue', label: 'mapValue(值映射,补值)' },
  { value: 'renameDatasetColumn', label: 'renameDatasetColumn(数据集列重命名)' },
  { value: 'mapDatasetValues', label: 'mapDatasetValues(数据集值映射)' },
] as const

const scenarios = ref<{ scenarioId: string }[]>([])
const datasets = ref<{ datasetId: string }[]>([])
const varNames = ref<string[]>([])
const submitting = ref(false)

const form = reactive({
  opType: 'renameVar' as string,
  scenarioId: '',
  datasetId: '',
  step: 0,
  field: '',
  from: '',
  to: '',
  column: '',
  value: '',
  varName: '',
  mapRows: [] as { key: string; value: string }[],
})

// removeField/addField/rebindField/mapValue 用 field;renameField 用 from
const fieldModel = computed({
  get: () => (form.opType === 'renameField' ? form.from : form.field),
  set: (v: string) => {
    if (form.opType === 'renameField') form.from = v
    else form.field = v
  },
})

function opTypeIn(list: string[]): boolean {
  return list.includes(form.opType)
}

function resetForm(): void {
  form.opType = 'renameVar'
  form.scenarioId = ''
  form.datasetId = ''
  form.step = 0
  form.field = ''
  form.from = ''
  form.to = ''
  form.column = ''
  form.value = ''
  form.varName = ''
  form.mapRows = [{ key: '', value: '' }]
  if (props.mergeSeed) {           // 合并交互:锁 renameField + 预填
    form.opType = 'renameField'
    form.step = props.mergeSeed.step
    form.from = props.mergeSeed.from
    form.to = props.mergeSeed.to
  }
}

async function onOpen(): Promise<void> {
  resetForm()
  if (scenarios.value.length === 0) {
    try {
      const list = await listScenarios({})
      scenarios.value = list.map((s) => ({ scenarioId: s.meta.scenarioId }))
    } catch {
      scenarios.value = []
    }
  }
}

// 初次挂载即打开(modelValue 出生为 true)时,el-dialog 不保证 emit open —— 兜底
watch(() => props.modelValue, (v) => { if (v) void onOpen() }, { immediate: true })

// 选场景 → 拉调色板 vars + 数据集清单
watch(() => form.scenarioId, async (sid) => {
  varNames.value = []
  datasets.value = []
  if (!sid) return
  try {
    const sc = await getScenario(sid)
    const cfg = (sc as { config?: { vars?: Record<string, unknown> } }).config
    varNames.value = Object.keys(cfg?.vars ?? {})
  } catch { /* 调色板空着,手输兜底 */ }
  try {
    datasets.value = (await listDataSets({ scenarioId: sid })).map((d) => ({
      datasetId: (d as { datasetId: string }).datasetId,
    }))
  } catch { /* 数据集空着 */ }
})

function buildMap(): Record<string, string> {
  const map: Record<string, string> = {}
  for (const r of form.mapRows) {
    if (r.key !== '') map[r.key] = r.value
  }
  return map
}

function buildPayload(): Record<string, unknown> {
  switch (form.opType) {
    case 'renameVar': return { from: form.from, to: form.to }
    case 'renameField': return { step: form.step, from: form.from, to: form.to }
    case 'addField': return { step: form.step, field: form.field, value: form.value }
    case 'removeField': return { step: form.step, field: form.field }
    case 'rebindField': return { step: form.step, field: form.field, var: form.varName }
    case 'renameDatasetColumn': return { from: form.from, to: form.to }
    case 'mapDatasetValues': return { column: form.column, map: buildMap() }
    case 'mapValue': return { step: form.step, field: form.field, map: buildMap() }
    default: return {}
  }
}

async function submit(): Promise<void> {
  if (!form.scenarioId) {
    ElMessage.warning('请选择场景')
    return
  }
  const datasetOp = opTypeIn(['renameDatasetColumn', 'mapDatasetValues'])
  if (datasetOp && !form.datasetId) {
    ElMessage.warning('请选择数据集')
    return
  }
  submitting.value = true
  try {
    const op = await api.createOp(props.batchId, {
      opType: form.opType,
      scenarioId: form.scenarioId,
      datasetId: datasetOp ? form.datasetId : null,
      payload: buildPayload(),
    })
    emit('created', op)
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(api.errMsg(e, '创建失败(批次可能已不在 open 状态)'))
  } finally {
    submitting.value = false
  }
}

defineExpose({ form, submit })
</script>

<style scoped>
.pair { margin-left: 8px; }
.map-rows { width: 100%; }
.map-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.map-row .el-input { flex: 1; }
.hint { color: #909399; font-size: 12px; margin: 6px 0 0; }
</style>
