<!--
  CaseComposerCanvas.vue — ④ 步骤编辑 (现代化设计)
  3 栏布局 + 嵌入式接口目录 (子流程)
-->
<template>
  <div class="canvas-shell">
    <!-- 子流程:覆盖右两栏 -->
    <CaseComposerCatalog
      v-if="subView === 'catalog'"
      :next-step-idx="local.length + 1"
      :adding="adding"
      @add="onAddEndpoint"
      @back="subView = null"
    />

    <!-- 主页:3 栏 -->
    <div v-else class="three-col">
      <!-- ① 步骤流 -->
      <aside class="col col-steps">
        <div class="col-head">
          <div>
            <h3>步骤流</h3>
            <p class="muted">{{ local.length }} 个 step · 按顺序执行</p>
          </div>
          <button class="add-step" @click="subView = 'catalog'">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            添加接口
          </button>
        </div>
        <div class="step-list">
          <div v-for="(s, i) in local" :key="s.id" class="step-row"
               :class="{ active: i === activeStepIdx, disabled: !s.enabled }"
               @click="activeStepIdx = i">
            <div class="step-idx">{{ i + 1 }}</div>
            <div class="step-info">
              <div class="step-name">{{ s.name || s.id }}</div>
              <div class="step-meta">
                <span v-if="s.method" class="method-badge" :class="`m-${s.method.toLowerCase()}`">{{ s.method }}</span>
                <span v-if="s.service" class="svc-tag">{{ s.service }}</span>
                <span v-if="s.endpoint" class="ep-path">{{ s.endpoint }}</span>
              </div>
            </div>
            <el-switch v-model="s.enabled" size="small" @click.stop />
            <button class="step-del" @click.stop="removeStep(i)" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/></svg>
            </button>
          </div>
          <div v-if="!local.length" class="step-empty">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>
            </svg>
            <p>还没有 step</p>
            <button class="empty-cta" @click="subView = 'catalog'">+ 从接口目录选</button>
          </div>
        </div>
      </aside>

      <!-- ② 字段编辑器 -->
      <main class="col col-fields">
        <div v-if="currentStep" class="fields-shell">
          <div class="fields-head">
            <div class="fields-title">
              <span class="title-num">{{ activeStepIdx + 1 }}</span>
              <input
                class="title-input"
                :value="currentStep.name"
                @input="(e: any) => currentStep.name = e.target.value"
                placeholder="step 名称"
              />
            </div>
            <span class="step-kind">{{ currentStep.kind }}</span>
          </div>
          <el-form label-position="top" size="small" class="modern-form">
            <div class="grid-2">
              <el-form-item label="id">
                <el-input v-model="currentStep.id" />
              </el-form-item>
              <el-form-item label="kind">
                <el-select v-model="currentStep.kind" class="modern-select">
                  <el-option value="http" label="http" />
                  <el-option value="rpc" label="rpc" />
                  <el-option value="sql" label="sql" />
                  <el-option value="script" label="script" />
                  <el-option value="wait" label="wait" />
                  <el-option value="extract" label="extract" />
                </el-select>
              </el-form-item>
            </div>
            <div class="grid-3">
              <el-form-item label="method">
                <el-select v-model="currentStep.method" class="modern-select" allow-clear>
                  <el-option v-for="m in METHODS" :key="m" :value="m" :label="m" />
                </el-select>
              </el-form-item>
              <el-form-item label="service">
                <el-input v-model="currentStep.service" placeholder="tidb-test-service" />
              </el-form-item>
              <el-form-item label="expectStatus">
                <el-input-number v-model="currentStep.expectStatus as any" :min="100" :max="599" class="modern-number" />
              </el-form-item>
            </div>
            <el-form-item label="endpoint">
              <el-input v-model="currentStep.endpoint" placeholder="/api/v1/orders">
                <template #prefix><span class="input-tag">URL</span></template>
              </el-input>
            </el-form-item>
            <el-form-item label="headers (JSON)">
              <el-input
                :model-value="JSON.stringify(currentStep.headers || {}, null, 2)"
                @update:model-value="v => currentStep.headers = parseJson(v, {})"
                type="textarea"
                :rows="3"
                class="code-input"
              />
            </el-form-item>
            <!-- V3: body 由 IOFieldBinding 驱动 — 表单字段 (Type A) 自动渲染, schema-only (Type C) 隐藏携带 -->
            <el-form-item v-if="currentStep.endpointRef" label="请求体 (由 IOFieldBinding 驱动)">
              <div class="field-form-wrap">
                <FieldForm
                  :bindings="currentStep.endpointRef.bindings"
                  :body="currentStep.body || {}"
                  @update:body="v => currentStep.body = mergeBody(v, currentStep.endpointRef?.hiddenFields)"
                />
                <p class="field-form-hint">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                  来自 <code>Plate /api/endpoint/{{ currentStep.endpointRef.endpointId }}/full</code> 的 IOFieldBinding
                  · {{ currentStep.endpointRef.bindings.length }} 个字段, 全部 schema 字段会随 step 一起序列化 (含隐藏字段)
                </p>
                <!-- 附带字段 (Type C, schema-only) 折叠区 (PRD §5.9) -->
                <div v-if="hiddenFieldCount" class="extra-fields">
                  <div class="extra-head" @click="hiddenOpen = !hiddenOpen">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" :class="{ open: hiddenOpen }"><polyline points="6 9 12 15 18 9"/></svg>
                    <span>附带字段 · {{ hiddenFieldCount }} (从 schema 自动携带)</span>
                    <span class="extra-hint">运行时全量发出, 默认开启</span>
                  </div>
                  <div v-if="hiddenOpen" class="extra-body">
                    <div v-for="(v, k) in currentStep.endpointRef.hiddenFields" :key="k" class="extra-row">
                      <code class="extra-key">{{ k }}</code>
                      <span class="extra-arrow">→</span>
                      <code class="extra-val">{{ JSON.stringify(v) }}</code>
                      <span class="extra-tag t-c">Type C · hidden</span>
                    </div>
                  </div>
                </div>
              </div>
            </el-form-item>
            <el-form-item v-else label="body (JSON)">
              <el-input
                :model-value="JSON.stringify(currentStep.body || {}, null, 2)"
                @update:model-value="v => currentStep.body = parseJson(v, {})"
                type="textarea"
                :rows="5"
                class="code-input"
              />
              <span class="hint">提示: 从接口目录添加 step 后, body 将由 IOFieldBinding 自动渲染</span>
            </el-form-item>
            <el-form-item label="extract bindings (从响应提取变量)">
              <div v-for="(b, j) in currentStep.extractBindings" :key="j" class="extract-row">
                <el-input v-model="b.name" placeholder="变量名" size="small" class="ex-name" />
                <span class="ex-arrow">←</span>
                <el-input v-model="b.path" placeholder="$.data.orderId" size="small" class="ex-path" />
                <button class="ex-del" @click="currentStep.extractBindings.splice(j, 1)">×</button>
              </div>
              <button class="add-extract" @click="currentStep.extractBindings.push({ name: '', path: '' })">
                + 添加 extract
              </button>
            </el-form-item>
          </el-form>
        </div>
        <div v-else class="fields-empty">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <polyline points="14 2 14 8 20 8"/><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          </svg>
          <p>选一个 step 编辑</p>
          <p class="muted">或在左侧添加新 step</p>
        </div>
      </main>

      <!-- ③ 信息面板 -->
      <aside class="col col-info">
        <div class="col-head">
          <h3>step 信息</h3>
        </div>
        <div v-if="currentStep" class="info-body">
          <div class="info-block">
            <div class="info-k">HTTP</div>
            <div class="info-v">
              <span v-if="currentStep.method" class="method-badge" :class="`m-${currentStep.method.toLowerCase()}`">{{ currentStep.method }}</span>
              <code>{{ currentStep.endpoint || '—' }}</code>
            </div>
          </div>
          <div class="info-block">
            <div class="info-k">service</div>
            <div class="info-v"><code>{{ currentStep.service || '—' }}</code></div>
          </div>
          <div class="info-block">
            <div class="info-k">kind</div>
            <div class="info-v"><span class="badge">{{ currentStep.kind }}</span></div>
          </div>
          <div class="info-block">
            <div class="info-k">enabled</div>
            <div class="info-v">
              <span :class="['status-pill', currentStep.enabled ? 'on' : 'off']">
                {{ currentStep.enabled ? '✓ 启用' : '✗ 禁用' }}
              </span>
            </div>
          </div>
          <div v-if="currentStep.extractBindings?.length" class="info-block">
            <div class="info-k">extracts</div>
            <div class="info-v">
              <div v-for="(b, i) in currentStep.extractBindings" :key="i" class="extract-line">
                <code>{{ b.name || '?' }}</code> ← <code>{{ b.path || '?' }}</code>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="info-empty muted">无选中 step</div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import CaseComposerCatalog from './CaseComposerCatalog.vue'
import FieldForm from './FieldForm.vue'
import { getFullEndpoint } from '@/api/scenario-composer'
import { deepDefaults } from '@/utils/jsonpath'
import type { ScenarioStep } from '@/types/scenario-composer'

const METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']

const props = defineProps<{ modelValue: ScenarioStep[] }>()
const emit = defineEmits<{ 'update:modelValue': [ScenarioStep[]] }>()

const local = reactive<ScenarioStep[]>([...(props.modelValue || [])])
const activeStepIdx = ref(0)
const subView = ref<null | 'catalog'>(null)
const hiddenOpen = ref(false)
const adding = ref(false)

const hiddenFieldCount = computed(() =>
  currentStep.value?.endpointRef?.hiddenFields
    ? Object.keys(currentStep.value.endpointRef.hiddenFields).length
    : 0
)

watch(() => props.modelValue, (v) => {
  local.splice(0, local.length, ...(v || []))
}, { deep: true })

watch(local, (v) => {
  emit('update:modelValue', [...v])
}, { deep: true })

const currentStep = computed(() => local[activeStepIdx.value])

async function onAddEndpoint(ep: any) {
  if (!ep) return
  adding.value = true
  try {
    // Fetch the FULL endpoint definition from Plate so the form editor
    // has the IOFieldBinding list. Without this, the step has no
    // schema — just raw JSON, which is what the user complained about.
    let endpointRef: any = undefined
    try {
      const full = await getFullEndpoint(ep.id)
      endpointRef = {
        endpointId: full.id,
        bindings: full.request?.fields || [],
        hiddenFields: {},
      }
    } catch (e) {
      ElMessage.warning('拉取完整接口定义失败, 仍以原始信息加入: ' + (e as Error).message)
    }
    // Pre-populate body from defaults/examples so the form has values.
    const initialBody = endpointRef
      ? deepDefaults(endpointRef.bindings)
      : null
    const newStep: ScenarioStep = {
      id: ep.id?.split('.').pop() || `step-${local.length + 1}`,
      name: ep.name,
      kind: 'http',
      service: ep.service,
      endpoint: ep.api?.path,
      method: ep.api?.method as any,
      headers: ep.api?.headers || {},
      body: initialBody,
      expectStatus: 200,
      extractBindings: [],
      dependsOn: [],
      enabled: true,
      endpointRef,
    }
    local.push(newStep)
    activeStepIdx.value = local.length - 1
    subView.value = null  // 直接落盘, 关闭目录回到画布
    ElMessage.success(`已加入 step: ${newStep.name} (${endpointRef?.bindings?.length || 0} 字段)`)
  } finally {
    adding.value = false
  }
}

function mergeBody(formValues: any, hiddenFields: any): any {
  // Form values come from IOFieldBinding-driven controls; hidden
  // fields come from the schema (Type C) and are carried through
  // untouched. The merged body is what the dispatch serialises to
  // Plate — so it matches the contract schema field-for-field.
  return { ...(hiddenFields || {}), ...(formValues || {}) }
}

function removeStep(i: number) {
  local.splice(i, 1)
  if (activeStepIdx.value >= local.length) activeStepIdx.value = Math.max(0, local.length - 1)
}

function parseJson(s: string, fallback: unknown) {
  try { return JSON.parse(s) } catch { return fallback }
}
</script>

<style scoped>
.canvas-shell { width: 100%; }
.three-col {
  display: grid;
  grid-template-columns: 360px 1fr 320px;
  gap: 12px;
  min-height: 600px;
}
.col {
  background: #fff;
  border: 1px solid #e6e8ec;
  border-radius: 16px;
  padding: 16px 18px;
  display: flex; flex-direction: column;
}

.col-head { margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid #f1f5f9; }
.col-head h3 { margin: 0 0 2px; font-size: 14px; font-weight: 700; }
.col-head .muted { margin: 0; font-size: 11px; color: #94a3b8; }
.col-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }

.add-step {
  display: inline-flex; align-items: center; gap: 4px;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
  color: #fff; border: none; border-radius: 8px;
  padding: 6px 12px; font-size: 12px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
  white-space: nowrap;
}
.add-step:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3); }

/* step list */
.step-list { display: flex; flex-direction: column; gap: 6px; flex: 1; overflow-y: auto; }
.step-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px;
  background: #fafbfc;
  border: 1.5px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
}
.step-row:hover { background: #fff; border-color: #e6e8ec; }
.step-row.active {
  background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
  border-color: #c7d2fe;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.08);
}
.step-row.disabled { opacity: 0.55; }
.step-idx {
  width: 26px; height: 26px; border-radius: 50%;
  background: #fff; color: #5a6273; font-size: 12px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  border: 1.5px solid #e6e8ec;
  flex-shrink: 0;
}
.step-row.active .step-idx {
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
  color: #fff; border-color: transparent;
}
.step-info { flex: 1; min-width: 0; }
.step-name { font-size: 13px; font-weight: 600; color: #1a1d24; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.step-row.active .step-name { color: #4f46e5; }
.step-meta { display: flex; gap: 4px; align-items: center; margin-top: 3px; font-size: 10px; color: #5a6273; flex-wrap: wrap; }
.method-badge {
  font-family: var(--font-mono); font-weight: 700;
  padding: 1px 5px; border-radius: 3px;
  background: #f1f5f9; color: #475569; font-size: 9px;
}
.method-badge.m-get { background: #dbeafe; color: #1e40af; }
.method-badge.m-post { background: #d1fae5; color: #065f46; }
.method-badge.m-put { background: #fef3c7; color: #92400e; }
.method-badge.m-delete { background: #fee2e2; color: #991b1b; }
.method-badge.m-patch { background: #f3e8ff; color: #6b21a8; }
.svc-tag { background: #f1f5f9; color: #475569; padding: 1px 5px; border-radius: 3px; font-size: 9px; }
.ep-path { font-family: var(--font-mono); font-size: 10px; color: #94a3b8; }
.step-row :deep(.el-switch) { transform: scale(0.8); }
.step-del {
  width: 24px; height: 24px; background: transparent; border: none;
  border-radius: 4px; color: #94a3b8; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s; opacity: 0;
}
.step-row:hover .step-del { opacity: 1; }
.step-del:hover { background: #fef2f2; color: #ef4444; }

.step-empty {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 40px 16px; text-align: center; color: #94a3b8;
}
.step-empty svg { color: #cbd5e1; }
.step-empty p { margin: 0; font-size: 13px; }
.empty-cta {
  display: inline-flex; align-items: center; gap: 4px;
  background: #4f46e5; color: #fff; border: none; border-radius: 8px;
  padding: 8px 16px; font-size: 12px; font-weight: 600;
  cursor: pointer;
}
.empty-cta:hover { background: #6366f1; }

/* fields editor */
.fields-shell { flex: 1; }
.fields-head {
  display: flex; align-items: center; gap: 10px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 16px;
}
.fields-title { display: flex; align-items: center; gap: 8px; flex: 1; }
.title-num {
  width: 28px; height: 28px; border-radius: 8px;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
  color: #fff; font-size: 13px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.title-input {
  border: none; background: transparent;
  font-size: 18px; font-weight: 700; color: #1a1d24;
  flex: 1; outline: none;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
}
.title-input:focus { border-bottom-color: #4f46e5; }
.step-kind {
  padding: 4px 10px; border-radius: 999px;
  background: #f3e8ff; color: #6b21a8;
  font-size: 11px; font-weight: 600;
}

.modern-form :deep(.el-form-item__label) { font-weight: 500; color: #1a1d24; font-size: 12px; }
.modern-form :deep(.el-input__wrapper) {
  border-radius: 8px; background: #fafbfc; box-shadow: 0 0 0 1px #e6e8ec;
  transition: all 0.15s;
}
.modern-form :deep(.el-input__wrapper:hover) { box-shadow: 0 0 0 1px #c7d2fe; }
.modern-form :deep(.el-input__wrapper.is-focus) { background: #fff; box-shadow: 0 0 0 2px #4f46e5; }
.modern-form :deep(.el-select__wrapper) { background: #fafbfc; box-shadow: 0 0 0 1px #e6e8ec; border-radius: 8px; }
.modern-number { width: 100%; }
.modern-number :deep(.el-input__wrapper) { background: #fafbfc; box-shadow: 0 0 0 1px #e6e8ec; border-radius: 8px; }

.input-tag {
  display: inline-block; background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
  color: #fff; font-size: 10px; font-weight: 700;
  padding: 2px 6px; border-radius: 4px; margin-right: 4px;
}

.code-input :deep(.el-textarea__inner) {
  font-family: var(--font-mono); font-size: 12px; line-height: 1.5;
  background: #1e1e2e; color: #a6e3a1;
  border-radius: 8px; box-shadow: 0 0 0 1px #313244;
  padding: 10px 12px;
}

/* 附带字段 (Type C) 折叠区 */
.extra-fields {
  margin-top: 10px;
  border: 1px solid #fde68a; border-radius: 8px;
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
}
.extra-head {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; cursor: pointer;
  font-size: 12px; font-weight: 600; color: #92400e;
}
.extra-head svg { transition: transform 0.15s; }
.extra-head svg.open { transform: rotate(180deg); }
.extra-hint { margin-left: auto; font-size: 11px; font-weight: 400; color: #b45309; }
.extra-body { padding: 0 12px 10px; display: flex; flex-direction: column; gap: 4px; }
.extra-row {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 6px; background: #fff; border-radius: 4px;
  font-size: 11px;
}
.extra-key { color: #4338ca; font-weight: 600; }
.extra-arrow { color: #94a3b8; }
.extra-val { color: #15803d; }
.extra-tag {
  margin-left: auto; padding: 1px 6px; border-radius: 3px;
  font-size: 9px; font-weight: 700; text-transform: uppercase;
}
.t-c { background: #fde68a; color: #92400e; }
.code-input :deep(.el-textarea__inner::placeholder) { color: #6c7086; }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0 14px; }

.extract-row {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 4px; padding: 4px 6px;
  background: #fafbfc; border-radius: 6px;
}
.ex-name { width: 140px; }
.ex-path { flex: 1; font-family: var(--font-mono); }
.ex-arrow { color: #94a3b8; }
.ex-del { width: 24px; height: 24px; background: transparent; border: none; color: #94a3b8; cursor: pointer; }
.ex-del:hover { color: #ef4444; }
.extract-row :deep(.el-input__wrapper) { background: #fff; box-shadow: 0 0 0 1px #e6e8ec; border-radius: 4px; }
.add-extract {
  margin-top: 6px;
  background: #fafbfc; border: 1.5px dashed #cbd5e1; border-radius: 6px;
  color: #5a6273; font-size: 12px; padding: 6px;
  cursor: pointer; width: 100%;
}
.add-extract:hover { background: #eef2ff; border-color: #c7d2fe; color: #4f46e5; }

/* fields empty */
.fields-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; color: #94a3b8;
}
.fields-empty svg { color: #cbd5e1; }
.fields-empty p { margin: 0; font-size: 13px; }
.fields-empty .muted { font-size: 12px; }

/* info panel */
.info-body { display: flex; flex-direction: column; gap: 12px; }
.info-block {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 10px 12px; background: #fafbfc; border-radius: 8px;
}
.info-k {
  width: 50px; flex-shrink: 0;
  font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;
}
.info-v { flex: 1; font-size: 12px; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.info-v code { font-family: var(--font-mono); font-size: 11px; color: #4f46e5; background: #fff; padding: 1px 4px; border-radius: 3px; word-break: break-all; }
.badge { background: #f3e8ff; color: #6b21a8; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.status-pill { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.status-pill.on { background: #d1fae5; color: #065f46; }
.status-pill.off { background: #fee2e2; color: #991b1b; }
.extract-line { font-size: 10px; width: 100%; }
.info-empty { padding: 40px 0; text-align: center; font-size: 12px; }
</style>
