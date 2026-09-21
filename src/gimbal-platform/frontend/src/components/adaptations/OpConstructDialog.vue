<!-- OpConstructDialog —— 11 类人工构造 op(§6.3 全量 + T16 三个 carry 值表
     op;mergeSeed 预填)。CARRY_OPS 免场景落点(后端 D1):值表层,
     service 缺省 = 全局默认表。 -->
<template>
  <Dialog :open="modelValue" @update:open="emit('update:modelValue', $event)">
    <DialogContent class="max-w-[560px]" @interact-outside="!modelValue || undefined">
    <DialogHeader>
      <DialogTitle>{{ mergeSeed ? '合并为 renameField' : '构造 op' }}</DialogTitle>
    </DialogHeader>
    <div class="ocd-form">
      <div class="ocd-row"><span class="ocd-label">类型</span>
        <select v-model="form.opType" class="ocd-select" :disabled="Boolean(mergeSeed)">
          <option v-for="t in OP_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
        </select>
      </div>
      <!-- carry 值表 op 无场景落点:不渲染场景选择,提交也不校验 -->
      <div class="ocd-row"><span class="ocd-label">场景</span>
        <select v-model="form.scenarioId" class="ocd-select">
          <option value="" disabled>选择场景</option>
          <option v-for="sc in scenarios" :key="sc.scenarioId" :value="sc.scenarioId">{{ sc.scenarioId }}</option>
        </select>
      </div>

      <!-- 数据集 op:数据集 + 列 -->
      <template v-if="opTypeIn(['renameDatasetColumn', 'mapDatasetValues'])">
        <div class="ocd-row"><span class="ocd-label">数据集</span>
          <select v-model="form.datasetId" class="ocd-select">
            <option value="" disabled>选择数据集</option>
            <option v-for="d in datasets" :key="d.datasetId" :value="d.datasetId">{{ d.datasetId }}</option>
          </select>
        </div>
        <div v-if="form.opType === 'mapDatasetValues'"><span class="ocd-label">列名(column)</span>
          <Input v-model="form.column" class="h-8" />
        </div>
        <div class="ocd-row"><span class="ocd-label">列 from → to</span>
          <Input v-model="form.from" placeholder="from" />
          <Input v-model="form.to" placeholder="to" class="pair" />
        </div>
      </template>

      <!-- renameVar:调色板下拉 -->
      <template v-else-if="form.opType === 'renameVar'">
        <div class="ocd-row"><span class="ocd-label">var from → to</span>
          <select v-model="form.from" class="ocd-select">
            <option value="" disabled>from</option>
            <option v-for="v in varNames" :key="v" :value="v">{{ v }}</option>
          </select>
          <select v-model="form.to" class="ocd-select pair">
            <option value="" disabled>to</option>
            <option v-for="v in varNames" :key="v" :value="v">{{ v }}</option>
          </select>
        </div>
      </template>

      <!-- CARRY_OPS(T16):值表三层字段 —— service 缺省 = 全局默认表;
           from/to 输入对模式同 renameField。 -->
      <template v-else-if="isCarryOp">
        <div class="ocd-row"><span class="ocd-label">服务(service)</span>
          <Input v-model="form.service"
            placeholder="缺省 = 全局默认表"
          />
        </div>
        <div class="ocd-row"><span class="ocd-label">路径 from → to</span>
          <Input v-model="form.from" placeholder="from" />
          <Input v-model="form.to" placeholder="to" class="pair" />
        </div>
        <div class="ocd-row"><span class="ocd-label">路径(path)</span>
          <Input v-model="form.field" placeholder="$.carry.path" />
        </div>
        <div class="ocd-row"><span class="ocd-label">值(value)</span>
          <Input v-model="form.value" placeholder="空串合法;显式 null 用批详情编辑 JSON" />
        </div>
      </template>

      <!-- STEP_OPS -->
      <template v-else>
        <div class="ocd-row"><span class="ocd-label">步骤(step)</span>
          <Input v-model="form.step" type="number" min="0" class="h-8 w-[100px]" />
        </div>
        <div class="ocd-row"><span class="ocd-label">字段</span>
          <Input v-model="fieldModel"
            :placeholder="form.opType === 'renameField' ? 'from' : 'field'"
          />
          <Input
            v-if="form.opType === 'renameField'"
            v-model="form.to"
            placeholder="to"
            class="pair h-8"
          />
        </div>
        <div class="ocd-row"><span class="ocd-label">值(value)</span>
          <Input v-model="form.value" class="h-8" />
        </div>
        <div class="ocd-row"><span class="ocd-label">目标 var</span>
          <select v-model="form.varName" class="ocd-select">
            <option value="" disabled>调色板</option>
            <option v-for="v in varNames" :key="v" :value="v">{{ v }}</option>
          </select>
        </div>
      </template>

      <!-- map 编辑器(mapValue / mapDatasetValues) -->
      <div v-if="opTypeIn(['mapValue', 'mapDatasetValues'])"><span class="ocd-label">值映射(map)</span>
        <div class="map-rows">
          <div v-for="(row, i) in form.mapRows" :key="i" class="map-row">
            <Input v-model="row.key" placeholder="原值(键手输)" />
            <span>→</span>
            <Input v-model="row.value" placeholder="新值" />
            <Button variant="link" size="sm" class="h-7 px-2 text-signal-failed" @click="form.mapRows.splice(i, 1)">删</Button>
          </div>
          <Button variant="link" size="sm" class="h-7 px-2" @click="form.mapRows.push({ key: '', value: '' })">+ 加一行</Button>
          <p class="hint">草案 payload 不含值域;候选可从预览的当前值抄录</p>
        </div>
      </div>
    </div>

    <DialogFooter>
      <Button variant="outline" @click="emit('update:modelValue', false)">取消</Button>
      <Button :disabled="submitting" @click="submit">
        {{ submitting ? '创建中…' : '创建' }}
      </Button>
    </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { toast } from '@/utils/toast'
import * as api from '@/api/adaptations'
import type { MergeSeed, OpOut } from '@/api/adaptations'
import { getScenario, listDataSets, listScenarioOptions } from '@/api/scenario-composer'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

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
  { value: 'renameCarryPath', label: 'renameCarryPath(carry 路径重命名)' },
  { value: 'addCarryBinding', label: 'addCarryBinding(补 carry 绑定)' },
  { value: 'removeCarryBinding', label: 'removeCarryBinding(移除 carry 绑定)' },
] as const

/** CARRY_OPS(T16):值表 op 免场景落点,payload 带 service?/路径字段。 */
const CARRY_OP_TYPES = [
  'renameCarryPath', 'addCarryBinding', 'removeCarryBinding',
]

const scenarios = ref<{ scenarioId: string }[]>([])
const datasets = ref<{ datasetId: string }[]>([])
const varNames = ref<string[]>([])
const submitting = ref(false)

const form = reactive({
  opType: 'renameVar' as string,
  scenarioId: '',
  datasetId: '',
  service: '',
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

const isCarryOp = computed(() => opTypeIn(CARRY_OP_TYPES))

function resetForm(): void {
  form.opType = 'renameVar'
  form.scenarioId = ''
  form.datasetId = ''
  form.service = ''
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
      const env = await listScenarioOptions({ page_size: 100 })
      scenarios.value = env.items.map((s) => ({ scenarioId: s.scenarioId }))
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

/** carry op payload:service 为空不带键(缺省 = 全局默认表,后端契约)。 */
function carryPayload(base: Record<string, unknown>): Record<string, unknown> {
  return form.service ? { service: form.service, ...base } : base
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
    case 'renameCarryPath': return carryPayload({ from: form.from, to: form.to })
    case 'addCarryBinding': return carryPayload({ path: form.field, value: form.value })
    case 'removeCarryBinding': return carryPayload({ path: form.field })
    default: return {}
  }
}

async function submit(): Promise<void> {
  // CARRY_OPS 免场景(值表 op);场景 op 仍必选
  if (!isCarryOp.value && !form.scenarioId) {
    toast.warning('请选择场景')
    return
  }
  const datasetOp = opTypeIn(['renameDatasetColumn', 'mapDatasetValues'])
  if (datasetOp && !form.datasetId) {
    toast.warning('请选择数据集')
    return
  }
  submitting.value = true
  try {
    // carry op 请求体不带 scenarioId/datasetId 键(后端 D1 免场景)
    const op = await api.createOp(props.batchId, isCarryOp.value ? {
      opType: form.opType,
      payload: buildPayload(),
    } : {
      opType: form.opType,
      scenarioId: form.scenarioId,
      datasetId: datasetOp ? form.datasetId : null,
      payload: buildPayload(),
    })
    emit('created', op)
    emit('update:modelValue', false)
  } catch (e) {
    toast.error(api.errMsg(e, '创建失败(批次可能已不在 open 状态)'))
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
.hint { color: var(--sl-ink-3); font-size: 12px; margin: 6px 0 0; }
.ocd-form { display: flex; flex-direction: column; gap: 10px; }
.ocd-row { display: grid; grid-template-columns: 110px 1fr; gap: 8px; align-items: center; }
.ocd-label { font-size: 12px; font-weight: 500; color: var(--sl-ink-2); text-align: right; }
.ocd-select {
  height: 32px; padding: 0 8px; font-size: 13px;
  color: var(--sl-ink); background: #fff;
  border: 1px solid var(--sl-line); border-radius: 6px;
  min-width: 0;
}
.pair { margin-left: 6px; }
</style>
