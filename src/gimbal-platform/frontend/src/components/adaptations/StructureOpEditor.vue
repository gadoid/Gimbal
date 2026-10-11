<!--
  StructureOpEditor.vue — RS4b 步骤结构级改造编辑器（Release §5.4）

  5 种 op:replaceEndpoint / splitStep / mergeSteps / insertStep / removeStep
  每个结构级变化步骤选一种 op 并配置参数;配置结果追加到 drafted_ops。
-->
<template>
  <div class="soe" data-testid="structure-op-editor">
    <div v-for="(item, idx) in items" :key="idx" class="soe-item">
      <div class="soe-head">
        <span class="mono soe-ep">{{ item.endpoint }}</span>
        <span class="soe-step">步骤 {{ item.step + 1 }}</span>
      </div>

      <!-- op 类型选择 -->
      <select v-model="item.opType" class="soe-sel" data-testid="soe-type"
              @change="item.config = defaultConfig(item.opType)">
        <option value="">— 选择改造方式 —</option>
        <option value="replaceEndpoint">接口替换（改指向另一个接口）</option>
        <option value="splitStep">一拆多（拆成有序多步）</option>
        <option value="mergeSteps">多合一（合并为一个步骤）</option>
        <option value="insertStep">插入新步骤</option>
        <option value="removeStep">删除此步骤</option>
        <option value="__skip">放弃适配此场景</option>
      </select>

      <!-- removeStep:无参数 -->
      <div v-if="item.opType === 'removeStep'" class="soe-note">
        删除后其他步骤引用它提取的变量时列为评审项
      </div>

      <!-- replaceEndpoint -->
      <template v-if="item.opType === 'replaceEndpoint'">
        <div class="soe-field">
          <label>目标接口 ID</label>
          <input v-model="item.config.endpoint" placeholder="如 fin.order.v2"
                 class="soe-input" data-testid="soe-replace-endpoint" />
        </div>
        <div class="soe-field">
          <label>字段映射（旧字段 → 新字段，每行一条，格式: old=new）</label>
          <textarea v-model="item.config.fieldMapping" rows="3"
                    placeholder="order_id=orderId&#10;user_id=userId"
                    class="soe-input soe-textarea" />
        </div>
      </template>

      <!-- splitStep -->
      <template v-if="item.opType === 'splitStep'">
        <div v-for="(ns, ni) in (item.config.newSteps as any[])" :key="ni" class="soe-substep">
          <div class="soe-sub-head">新步骤 {{ ni + 1 }}</div>
          <div class="soe-field">
            <label>接口 ID</label>
            <input v-model="ns.endpoint" placeholder="如 fin.order.create"
                   class="soe-input" />
          </div>
          <div class="soe-field">
            <label>请求体（JSON，支持 ${var} 模板）</label>
            <textarea v-model="ns.body" rows="2"
                      placeholder='{"orderId": "${var.orderId}"}'
                      class="soe-input soe-textarea" />
          </div>
        </div>
        <button type="button" class="soe-add"
                @click="(item.config.newSteps as any[]).push({endpoint:'',body:''})">
          + 添加步骤
        </button>
      </template>

      <!-- mergeSteps -->
      <template v-if="item.opType === 'mergeSteps'">
        <div class="soe-field">
          <label>要合并的步骤索引（逗号分隔，含本步骤）</label>
          <input v-model="item.config.steps" placeholder="如 0,1,2"
                 class="soe-input" />
        </div>
        <div class="soe-field">
          <label>合并后的接口 ID</label>
          <input v-model="item.config.endpoint" placeholder="如 fin.order.combined"
                 class="soe-input" />
        </div>
      </template>

      <!-- insertStep -->
      <template v-if="item.opType === 'insertStep'">
        <div class="soe-field">
          <label>插入位置（步骤索引）</label>
          <input v-model="item.config.at" type="number" min="0"
                 class="soe-input" />
        </div>
        <div class="soe-field">
          <label>新步骤的接口 ID</label>
          <input v-model="item.config.endpoint" placeholder="如 fin.auth.login"
                 class="soe-input" />
        </div>
      </template>

      <!-- 放弃提示 -->
      <div v-if="item.opType === '__skip'" class="soe-skip">
        此场景将在提交中跳过（不做适配）
      </div>
    </div>
  </div>
</template>

<script lang="ts">
export interface StructureItem {
  step: number
  endpoint: string
  reason: string
  opType: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any
}

export function toOps(items: StructureItem[]): Array<Record<string, unknown>> {
  const ops: Array<Record<string, unknown>> = []
  for (const item of items) {
    if (!item.opType || item.opType === '__skip') continue
    const base = { op: item.opType, step: item.step, endpoint: item.endpoint }
    switch (item.opType) {
      case 'replaceEndpoint': {
        const map: Record<string, string> = {}
        for (const line of String(item.config.fieldMapping || '').split('\n')) {
          const [old, ...rest] = line.split('=')
          if (old?.trim() && rest.length) map[old.trim()] = rest.join('=').trim()
        }
        ops.push({ ...base, endpoint: item.config.endpoint, newStep: {
          kind: 'step', call: { protocol: 'http', service: '', headers: {} },
          request: { kind: 'request', body: {} }, strategy: [],
        }, fieldMapping: map })
        break
      }
      case 'splitStep':
        ops.push({ ...base, newSteps: (item.config.newSteps || []).map(
          (ns: { endpoint: string; body: string }) => ({
            kind: 'step', endpoint: ns.endpoint,
            call: { protocol: 'http', service: '', headers: {} },
            request: { kind: 'request',
                       body: (() => { try { return JSON.parse(ns.body || '{}') } catch { return {} } })() },
            strategy: [],
          })) })
        break
      case 'mergeSteps': {
        const indices = String(item.config.steps || '')
          .split(',').map((s: string) => parseInt(s.trim())).filter((n: number) => !isNaN(n))
        ops.push({ ...base, steps: indices, mergedStep: {
          kind: 'step', endpoint: item.config.endpoint,
          call: { protocol: 'http', service: '', headers: {} },
          request: { kind: 'request', body: {} }, strategy: [],
        } })
        break
      }
      case 'insertStep':
        ops.push({ ...base, at: Number(item.config.at) || 0, newStep: {
          kind: 'step', endpoint: item.config.endpoint,
          call: { protocol: 'http', service: '', headers: {} },
          request: { kind: 'request', body: {} }, strategy: [],
        } })
        break
      case 'removeStep':
        ops.push(base)
        break
    }
  }
  return ops
}
</script>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ structure: Array<{ step: number; endpoint: string; reason: string }> }>()
const emit = defineEmits<{ 'update:items': [StructureItem[]] }>()

const items = computed<StructureItem[]>(() =>
  props.structure.map(s => ({
    step: s.step,
    endpoint: s.endpoint,
    reason: s.reason,
    opType: '',
    config: {},
  })))

function defaultConfig(opType: string): Record<string, unknown> {
  switch (opType) {
    case 'replaceEndpoint':
      return { endpoint: '', fieldMapping: '' }
    case 'splitStep':
      return { newSteps: [{ endpoint: '', body: '' }] }
    case 'mergeSteps':
      return { steps: '', endpoint: '' }
    case 'insertStep':
      return { at: 0, endpoint: '' }
    case 'removeStep':
    case '__skip':
    default:
      return {}
  }
}
</script>

<style scoped>
.soe { display: flex; flex-direction: column; gap: 12px; }
.soe-item {
  border: 1px solid #fecaca; border-radius: 8px; padding: 10px 12px;
  background: #fff;
}
.soe-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.soe-ep { font-size: 12px; font-weight: 600; color: #b91c1c; }
.soe-step { font-size: 11px; color: #94a3b8; }
.soe-sel {
  width: 100%; padding: 6px 8px; border: 1px solid #e1e5eb;
  border-radius: 4px; font-size: 13px; margin-bottom: 8px;
}
.soe-field { display: flex; flex-direction: column; gap: 4px; margin: 6px 0; }
.soe-field label { font-size: 11px; color: #64748b; }
.soe-input {
  padding: 6px 8px; border: 1px solid #e1e5eb; border-radius: 4px;
  font-size: 12px; font-family: ui-monospace, monospace;
}
.soe-textarea { resize: vertical; }
.soe-note { font-size: 11px; color: #94a3b8; padding: 4px 0; }
.soe-skip { font-size: 11px; color: #f59e0b; padding: 4px 0; }
.soe-substep { border-left: 2px solid #e1e5eb; padding-left: 10px; margin: 8px 0; }
.soe-sub-head { font-size: 11px; font-weight: 600; color: #64748b; margin-bottom: 4px; }
.soe-add {
  background: none; border: 1px dashed #94a3b8; border-radius: 4px;
  padding: 4px 12px; font-size: 12px; color: #64748b; cursor: pointer;
}
.soe-add:hover { border-color: #2f6fed; color: #2f6fed; }
</style>
