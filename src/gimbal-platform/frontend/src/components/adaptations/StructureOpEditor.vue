<!--
  StructureOpEditor.vue — RS4b 步骤结构级改造编辑器（Release §5.4）

  5 种 op:replaceEndpoint / splitStep / mergeSteps / insertStep / removeStep
  每个结构级变化步骤选一种 op 并配置参数;配置结果追加到 drafted_ops。
  接口从目标修订的目录里选(datalist,也可手填);跨系统接口必须填
  目标系统的修订(否则提交时会被 version_undeclared 拦下)。步骤编号
  展示与输入一致(1 起)。编辑经 update:items 上抛(断链即静默丢结果)。
-->
<template>
  <div class="soe" data-testid="structure-op-editor">
    <datalist id="soe-eps">
      <option v-for="ep in endpoints" :key="ep.id"
              :value="ep.id">{{ ep.name }}（{{ ep.service }}）</option>
    </datalist>
    <p v-if="!endpoints.length" class="soe-catalog-hint">
      目标修订目录拉取失败或为空 —— 接口 ID 可手填,提交检查会校验
    </p>

    <div v-for="(item, idx) in items" :key="idx" class="soe-item">
      <div class="soe-head">
        <span class="mono soe-ep">{{ item.endpoint }}</span>
        <span class="soe-step">步骤 {{ item.step + 1 }}</span>
      </div>

      <!-- op 类型选择 -->
      <select v-model="item.opType" class="soe-sel" data-testid="soe-type"
              @change="onTypeChange(item)">
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
          <label>目标接口（从目标修订目录选择，或输入 ID）</label>
          <input v-model="item.config.endpoint" list="soe-eps"
                 placeholder="如 fin.order.v2"
                 class="soe-input" data-testid="soe-replace-endpoint"
                 @change="resolveEndpoint(item)" />
        </div>
        <div class="soe-field">
          <label>字段映射（旧字段 → 新字段，每行一条，格式: old=new）</label>
          <textarea v-model="item.config.fieldMapping" rows="3"
                    placeholder="order_id=orderId&#10;user_id=userId"
                    class="soe-input soe-textarea" />
        </div>
        <div v-if="isCrossSystem(item)" class="soe-field soe-cross">
          <label>目标系统（{{ item.config._system }}）的修订 — 必填</label>
          <input v-model="item.config.revision" placeholder="如 1.0#1"
                 class="soe-input" data-testid="soe-cross-revision" />
        </div>
      </template>

      <!-- splitStep -->
      <template v-if="item.opType === 'splitStep'">
        <div v-for="(ns, ni) in (item.config.newSteps as any[])" :key="ni" class="soe-substep">
          <div class="soe-sub-head">新步骤 {{ ni + 1 }}</div>
          <div class="soe-field">
            <label>接口（从目标修订目录选择，或输入 ID）</label>
            <input v-model="ns.endpoint" list="soe-eps"
                   placeholder="如 fin.order.create"
                   class="soe-input" @change="resolveNsEndpoint(item, ns)" />
          </div>
          <div class="soe-field">
            <label>请求体（JSON，支持 ${var} 模板）</label>
            <textarea v-model="ns.body" rows="2"
                      placeholder='{"orderId": "${var.orderId}"}'
                      class="soe-input soe-textarea" :class="{ 'soe-json-bad': !bodyOk(ns.body) }" />
            <span v-if="ns.body && !bodyOk(ns.body)" class="soe-json-err">
              请求体不是合法 JSON —— 修复后再提交（当前会被当作空对象丢弃）
            </span>
          </div>
        </div>
        <button type="button" class="soe-add"
                @click="(item.config.newSteps as any[]).push({endpoint:'',body:'',service:''})">
          + 添加步骤
        </button>
        <div v-if="isCrossSystem(item)" class="soe-field soe-cross">
          <label>目标系统（{{ item.config._system }}）的修订 — 必填</label>
          <input v-model="item.config.revision" placeholder="如 1.0#1"
                 class="soe-input" data-testid="soe-cross-revision" />
        </div>
      </template>

      <!-- mergeSteps -->
      <template v-if="item.opType === 'mergeSteps'">
        <div class="soe-field">
          <label>要合并的步骤编号（1 起，逗号分隔，含本步骤，可不连续）</label>
          <input v-model="item.config.steps" placeholder="如 1,3"
                 class="soe-input" data-testid="soe-merge-steps" />
        </div>
        <div class="soe-field">
          <label>合并后的接口（从目标修订目录选择，或输入 ID）</label>
          <input v-model="item.config.endpoint" list="soe-eps"
                 placeholder="如 fin.order.combined"
                 class="soe-input" @change="resolveEndpoint(item)" />
        </div>
        <div v-if="isCrossSystem(item)" class="soe-field soe-cross">
          <label>目标系统（{{ item.config._system }}）的修订 — 必填</label>
          <input v-model="item.config.revision" placeholder="如 1.0#1"
                 class="soe-input" data-testid="soe-cross-revision" />
        </div>
      </template>

      <!-- insertStep -->
      <template v-if="item.opType === 'insertStep'">
        <div class="soe-field">
          <label>插入到第几步之前（1 起；填 3 = 插在步骤 3 前面）</label>
          <input v-model.number="item.config.at" type="number" min="1"
                 class="soe-input" />
        </div>
        <div class="soe-field">
          <label>新步骤的接口（从目标修订目录选择，或输入 ID）</label>
          <input v-model="item.config.endpoint" list="soe-eps"
                 placeholder="如 fin.auth.login"
                 class="soe-input" @change="resolveEndpoint(item)" />
        </div>
        <div v-if="isCrossSystem(item)" class="soe-field soe-cross">
          <label>目标系统（{{ item.config._system }}）的修订 — 必填</label>
          <input v-model="item.config.revision" placeholder="如 1.0#1"
                 class="soe-input" data-testid="soe-cross-revision" />
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
/** 结构级改造条目（编辑面形态;提交前经 toOps 转为 op） */
export interface StructureItem {
  step: number
  endpoint: string
  reason: string
  opType: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any
}

/** 字段映射文本(old=new 每行一条)→ dict;空行/无 = 行忽略 */
function parseFieldMapping(text: string): Record<string, string> {
  const map: Record<string, string> = {}
  for (const line of String(text || '').split('\n')) {
    const [old, ...rest] = line.split('=')
    if (old?.trim() && rest.length) map[old.trim()] = rest.join('=').trim()
  }
  return map
}

/** JSON 容错解析(模板串 ${var} 在 JSON 里合法,普通 JSON.parse 即可) */
function parseBody(text: string): unknown {
  try { return JSON.parse(text || '{}') } catch { return {} }
}

function bodyTextOk(text: string): boolean {
  if (!text) return true
  try { JSON.parse(text); return true } catch { return false }
}

/**
 * 将用户配置转为提交用的 op 列表。编号约定:展示与输入一律 1 起,
 * 转换时 -1 为引擎的 0 起索引。call 不在前端拼(6.2:派生字段由投影
 * 提供,场景自有字段由后端从旧步骤继承/由目录选择带出 service)。
 */
export function toOps(items: StructureItem[]): Array<Record<string, unknown>> {
  const ops: Array<Record<string, unknown>> = []
  for (const item of items) {
    if (!item.opType || item.opType === '__skip') continue
    const base = { op: item.opType, step: item.step, endpoint: item.endpoint }
    const tr = item.config?.revision
      ? { targetRevision: String(item.config.revision).trim() } : {}
    switch (item.opType) {
      case 'replaceEndpoint':
        ops.push({ ...base, endpoint: String(item.config.endpoint || '').trim(),
                   fieldMapping: parseFieldMapping(item.config.fieldMapping), ...tr })
        break
      case 'splitStep':
        ops.push({ ...base, newSteps: (item.config.newSteps || []).map(
          (ns: { endpoint: string; body: string; service?: string }) => ({
            endpoint: String(ns.endpoint || '').trim(),
            service: ns.service || '',
            body: parseBody(ns.body),
          })), ...tr })
        break
      case 'mergeSteps': {
        const indices = String(item.config.steps || '')
          .split(',').map((s: string) => parseInt(s.trim(), 10))
          .filter((n: number) => !isNaN(n) && n >= 1)
          .map((n: number) => n - 1)          // 1 起 → 0 起
        ops.push({ ...base, steps: indices,
                   endpoint: String(item.config.endpoint || '').trim(),
                   mergedStep: { service: item.config.service || '' }, ...tr })
        break
      }
      case 'insertStep':
        ops.push({ ...base, at: Math.max(0, (Number(item.config.at) || 1) - 1),
                   newStep: {
                     endpoint: String(item.config.endpoint || '').trim(),
                     service: item.config.service || '',
                   }, ...tr })
        break
      case 'removeStep':
        ops.push(base)
        break
    }
  }
  return ops
}

/**
 * 提交前完整性校验:返回阻塞原因(null = 可提交)。
 * 跨系统接口缺修订 / 必填接口为空 / 合并编号无有效项 / 拆分 JSON
 * 非法,都会在这里拦下 —— 与其让后端静默降级,不如在提交口报清楚。
 */
export function incompleteReason(items: StructureItem[]): string | null {
  for (const item of items) {
    if (!item.opType || item.opType === '__skip') continue
    const where = `步骤 ${item.step + 1}（${item.endpoint}）`
    if (item.opType === 'replaceEndpoint' && !String(item.config.endpoint || '').trim())
      return `${where}:接口替换未选择目标接口`
    if (item.opType === 'insertStep' && !String(item.config.endpoint || '').trim())
      return `${where}:插入步骤未选择接口`
    if (item.opType === 'mergeSteps') {
      if (!String(item.config.endpoint || '').trim())
        return `${where}:合并未选择合并后的接口`
      const n = String(item.config.steps || '').split(',')
        .map((s: string) => parseInt(s.trim(), 10))
        .filter((v: number) => !isNaN(v) && v >= 1).length
      if (n < 2) return `${where}:合并至少要 2 个有效步骤编号(1 起)`
    }
    if (item.opType === 'splitStep') {
      const nsList: Array<{ endpoint?: string; body?: string }> =
        item.config.newSteps || []
      if (!nsList.length || nsList.some(ns => !String(ns.endpoint || '').trim()))
        return `${where}:拆分的每个新步骤都要填接口`
      const bad = nsList.find(ns => ns.body && !bodyTextOk(ns.body))
      if (bad) return `${where}:新步骤请求体不是合法 JSON`
    }
    if (isCross(item) && !String(item.config.revision || '').trim())
      return `${where}:接口属于其他系统(${item.config._system}),必须填该系统的修订`
  }
  return null
}

function isCross(item: StructureItem): boolean {
  const sys = item.config?._system
  const own = item.endpoint.split('.')[0]
  return !!sys && sys !== own
}
</script>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { listRevisionEndpoints, type RevisionEndpoint } from '@/api/adaptationFlow'

const props = defineProps<{
  structure: Array<{ step: number; endpoint: string; reason: string }>
  /** 目标修订(拉目录用;空 = 不拉,手填接口) */
  revision?: string
}>()
const emit = defineEmits<{ 'update:items': [StructureItem[]] }>()

const items = ref<StructureItem[]>([])

// 编辑面上抛(先注册:props 初次铸入同样上报;opType 选择/config 字段/
// newSteps 增删都经深 watch 触发)。父组件(@update:items)持有提交用
// 的 items —— 断链即静默丢编辑结果
watch(items, v => {
  emit('update:items',
       v.map(i => ({ ...i, config: JSON.parse(JSON.stringify(i.config ?? {})) })))
}, { deep: true })

// 本地可编辑副本:props.structure 变化(重新比对)时重铸
watch(() => props.structure, s => {
  items.value = s.map(x => ({
    step: x.step, endpoint: x.endpoint, reason: x.reason,
    opType: '', config: {},
  }))
}, { immediate: true })

// ── 目标修订目录(接口选择面)────────────────────────────────────
const endpoints = ref<RevisionEndpoint[]>([])

function defaultConfig(opType: string): Record<string, unknown> {
  switch (opType) {
    case 'replaceEndpoint':
      return { endpoint: '', fieldMapping: '', revision: '' }
    case 'splitStep':
      return { newSteps: [{ endpoint: '', body: '', service: '' }] }
    case 'mergeSteps':
      return { steps: '', endpoint: '', revision: '' }
    case 'insertStep':
      return { at: 1, endpoint: '', revision: '' }
    case 'removeStep':
    case '__skip':
    default:
      return {}
  }
}

function onTypeChange(item: StructureItem): void {
  item.config = defaultConfig(item.opType)
}

/** 选中目录条目 → 带出 service 与所属系统(跨系统判定/提交用) */
function resolveEndpoint(item: StructureItem): void {
  const ep = endpoints.value.find(e => e.id === String(item.config.endpoint || '').trim())
  item.config.service = ep?.service || ''
  item.config._system = ep?.system || ''
}

function resolveNsEndpoint(item: StructureItem, ns: Record<string, unknown>): void {
  const ep = endpoints.value.find(e => e.id === String(ns.endpoint || '').trim())
  ns.service = ep?.service || ''
  item.config._system = item.config._system || ep?.system || ''
}

function isCrossSystem(item: StructureItem): boolean {
  const sys = item.config?._system
  return !!sys && sys !== item.endpoint.split('.')[0]
}

function bodyOk(text: string | undefined): boolean {
  return bodyTextOk(String(text || ''))
}

onMounted(async () => {
  const system = props.structure[0]?.endpoint?.split('.')[0]
  if (!system || !props.revision) return
  try {
    endpoints.value = await listRevisionEndpoints(system, props.revision)
  } catch {
    endpoints.value = []          // 手填兜底;提示见模板
  }
})
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
.soe-cross label { color: #b45309; font-weight: 600; }
.soe-catalog-hint { font-size: 11px; color: #94a3b8; margin: 0; }
.soe-json-bad { border-color: #ef4444; }
.soe-json-err { font-size: 11px; color: #ef4444; }
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
