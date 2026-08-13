<!-- ScenarioEditorSteps.vue — 场景编辑 · ② 步骤编排
     三列布局：① StepList 步骤列表 · ② FieldEditor 当前步骤请求字段 ·
                ③ ConfigPanel 时间策略 / 重试 / 变量
-->
<template>
  <section class="editor">
    <header class="page-header">
      <div>
        <h2>📚 场景编辑 · {{ store.scenarioById(scenarioId)?.meta.name || scenarioId }}</h2>
        <p>{{ scenarioId }} · ② 步骤编排</p>
      </div>
      <div class="header-actions">
        <el-button @click="router.push(`/scenarios/${scenarioId}/edit`)">← ① 基本信息</el-button>
        <el-button type="primary" @click="saveAndNext">保存并下一步 →</el-button>
      </div>
    </header>

    <HeadStepper :steps="steps" :active-index="1" />

    <div v-loading="loading" class="body">
      <!-- ① 步骤列表 -->
      <aside class="step-list">
        <div class="head">
          <h3>步骤 <span class="count">{{ draft.steps.length }}</span></h3>
          <el-button size="small" plain @click="addStep">+ 添加步骤</el-button>
        </div>
        <div class="list">
          <div
            v-for="(s, i) in draft.steps"
            :key="s.id"
            class="step-item"
            :class="{ active: s.id === activeId, disabled: !s.enabled }"
            @click="activeId = s.id"
          >
            <span class="index">{{ i + 1 }}</span>
            <div class="info">
              <div class="row1">
                <span class="name">{{ s.name || '(未命名)' }}</span>
                <span class="kind">{{ s.kind }}</span>
              </div>
              <div class="row2">
                <span class="method" :class="`m-${s.method?.toLowerCase()}`">
                  {{ s.method || '—' }}
                </span>
                <span class="path">{{ s.endpoint || '/' }}</span>
              </div>
            </div>
            <el-switch v-model="s.enabled" size="small" @click.stop />
          </div>
          <div v-if="!draft.steps.length" class="empty">还没有步骤 · 点上方 + 添加</div>
        </div>
      </aside>

      <!-- ② 字段编辑器 -->
      <section v-if="activeStep" class="field-editor">
        <div class="fe-head">
          <h3>字段编辑 · {{ activeStep.name || '步骤' }}</h3>
          <el-button size="small" type="danger" plain @click="removeStep(activeStep.id)">删除</el-button>
        </div>

        <el-form label-position="top" class="fe-form">
          <div class="grid-2">
            <el-form-item label="步骤名">
              <el-input v-model="activeStep.name" placeholder="创建订单" />
            </el-form-item>
            <el-form-item label="类型">
              <el-select v-model="activeStep.kind" placeholder="选择类型">
                <el-option v-for="k in KINDS" :key="k" :value="k" :label="k" />
              </el-select>
            </el-form-item>
          </div>
          <div class="grid-3">
            <el-form-item label="服务">
              <el-input v-model="activeStep.service" placeholder="fin-order" />
            </el-form-item>
            <el-form-item label="方法">
              <el-select v-model="activeStep.method" placeholder="GET">
                <el-option v-for="m in METHODS" :key="m" :value="m" :label="m" />
              </el-select>
            </el-form-item>
            <el-form-item label="期望状态码">
              <el-input v-model.number="activeStep.expectStatus" placeholder="200 或 [200,201]" />
            </el-form-item>
          </div>
          <el-form-item label="路径">
            <el-input v-model="activeStep.endpoint" placeholder="/api/v1/orders" />
          </el-form-item>
          <el-form-item label="Headers (JSON)">
            <el-input
              v-model="headersText"
              type="textarea"
              :rows="3"
              placeholder='{"Content-Type": "application/json"}'
            />
          </el-form-item>
          <el-form-item label="Body (JSON)">
            <el-input
              v-model="activeStep.body"
              type="textarea"
              :rows="6"
              placeholder='{ "qty": 1, ... }'
            />
          </el-form-item>
          <el-form-item label="extractBindings">
            <div v-for="(b, i) in activeStep.extractBindings" :key="i" class="bind-row">
              <el-input v-model="b.name" placeholder="变量名" />
              <el-input v-model="b.path" placeholder="$.data.id" />
              <el-button size="small" plain @click="activeStep.extractBindings?.splice(i, 1)">×</el-button>
            </div>
            <el-button size="small" plain @click="addBinding">+ 添加绑定</el-button>
          </el-form-item>
        </el-form>
      </section>
      <section v-else class="field-editor empty">← 请选择左侧步骤</section>

      <!-- ③ Config 面板 -->
      <aside class="config-panel">
        <h3>场景配置</h3>
        <div class="config-row">
          <label>时间策略</label>
          <el-select v-model="timePolicy" size="small">
            <el-option value="cost-collect" label="cost-collect（默认）" />
            <el-option value="timeout-check" label="timeout-check" />
            <el-option value="none" label="none" />
          </el-select>
        </div>
        <div class="config-row">
          <label>重试</label>
          <div class="retry-row">
            <el-input-number v-model="retryAttempts" :min="0" :max="10" size="small" />
            <span>×</span>
            <el-input-number v-model="retryIntervalMs" :min="100" :step="100" size="small" />
            <span>ms</span>
          </div>
        </div>
        <h3 style="margin-top: 24px;">变量声明</h3>
        <div v-for="(v, k) in draft.meta && varsMap" :key="k" class="var-row">
          <code>{{ k }}</code>
          <span>{{ v }}</span>
        </div>
        <el-button size="small" plain @click="addVar">+ 添加变量</el-button>

        <h3 style="margin-top: 24px;">JSON 预览</h3>
        <pre class="preview">{{ previewSnippet }}</pre>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter, type RouteLocationRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import HeadStepper from '@/components/HeadStepper.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { showError } from '@/utils/errorFallback'
import type { ScenarioDraft, ScenarioStep, StepKind } from '@/types/scenario-composer'

const KINDS: StepKind[] = ['http', 'rpc', 'sql', 'script', 'wait', 'extract']
const METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'] as const

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()
const scenarioId = route.params.scenarioId as string

const steps = [
  { key: 'meta',  label: '① 基本信息', to: `/scenarios/${scenarioId}/edit` as RouteLocationRaw },
  { key: 'steps', label: '② 步骤编排', to: '' as RouteLocationRaw },
  { key: 'cases', label: '③ 用例管理', to: `/scenarios/${scenarioId}/cases` as RouteLocationRaw },
  { key: 'data',  label: '④ 数据集',   to: `/scenarios/${scenarioId}/data-sets` as RouteLocationRaw },
]

const loading = ref(false)
const draft = reactive<ScenarioDraft>({
  meta: { scenarioId, name: '', description: '', module: '', priority: 2, author: '', owner: '', tags: [], system: [] },
  steps: [],
})

const activeId = ref<string>('')
const headersText = ref('{}')

const timePolicy = ref<'cost-collect' | 'timeout-check' | 'none'>('cost-collect')
const retryAttempts = ref(0)
const retryIntervalMs = ref(500)
const varsMap = reactive<Record<string, string>>({})

const activeStep = computed<ScenarioStep | undefined>(() =>
  draft.steps.find((s) => s.id === activeId.value),
)

const previewSnippet = computed(() =>
  JSON.stringify(
    {
      scenarioId: draft.meta.scenarioId,
      steps: draft.steps,
      config: {
        timePolicy: timePolicy.value,
        retry: { maxAttempts: retryAttempts.value, intervalMs: retryIntervalMs.value },
        vars: { ...varsMap },
      },
    },
    null,
    2,
  ),
)

onMounted(async () => {
  loading.value = true
  try {
    if (!store.scenarioById(scenarioId)) {
      await store.fetchScenarios()
    }
    const sc = store.scenarioById(scenarioId)
    if (sc) {
      Object.assign(draft.meta, sc.meta)
      draft.steps = sc.steps.map((s) => ({ ...s }))
      if (draft.steps[0]) {
        activeId.value = draft.steps[0].id
      }
    } else {
      ElMessage.warning('场景不存在，请先到 ① 基本信息创建')
    }
  } catch (e) {
    showError('加载步骤', undefined, (e as Error).message)
  } finally {
    loading.value = false
  }
})

watch(activeStep, (s) => {
  if (s) headersText.value = JSON.stringify(s.headers ?? {}, null, 2)
}, { immediate: true })

watch(headersText, (v) => {
  if (!activeStep.value) return
  try { activeStep.value.headers = JSON.parse(v) } catch { /* keep raw */ }
})

function addStep() {
  const id = `step-${Date.now()}`
  draft.steps.push({
    id,
    name: '新步骤',
    kind: 'http',
    service: '',
    method: 'POST',
    endpoint: '/',
    headers: {},
    body: '',
    expectStatus: 200,
    extractBindings: [],
    dependsOn: [],
    enabled: true,
  })
  activeId.value = id
}

function removeStep(id: string) {
  draft.steps = draft.steps.filter((s) => s.id !== id)
  if (activeId.value === id) activeId.value = draft.steps[0]?.id ?? ''
}

function addBinding() {
  if (!activeStep.value) return
  activeStep.value.extractBindings = activeStep.value.extractBindings ?? []
  activeStep.value.extractBindings.push({ name: '', path: '' })
}

function addVar() {
  const k = window.prompt('变量名（不含 $）')
  if (k && !(k in varsMap)) varsMap[k] = ''
}

async function saveAndNext() {
  try {
    await store.saveScenario(scenarioId, draft)
    ElMessage.success('已保存步骤')
    router.push(`/scenarios/${scenarioId}/cases`)
  } catch (e) {
    showError('保存', undefined, (e as Error).message)
  }
}
</script>

<style scoped>
.editor {
  max-width: 1480px;
  min-height: calc(100vh - 48px);
  padding: 28px 32px 48px;
  margin: 0 auto;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.page-header h2 { margin: 0; font-size: 22px; color: var(--color-text-primary); }
.page-header p  { margin: 5px 0 0; font-size: 12px; color: var(--color-text-secondary); }
.header-actions { display: flex; gap: 8px; }

.body {
  display: grid;
  grid-template-columns: 280px 1fr 320px;
  gap: 12px;
  margin-top: 16px;
  min-height: 600px;
}

.step-list, .field-editor, .config-panel {
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
}
.step-list   { display: flex; flex-direction: column; }
.field-editor { padding: 16px 20px; overflow: auto; }
.config-panel { padding: 16px 20px; }

.step-list .head {
  display: flex;
  gap: 6px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-tertiary);
}
.step-list h3 { margin: 0; font-size: 13px; font-weight: 700; }
.count {
  display: inline-block;
  margin-left: 4px;
  padding: 1px 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 10px;
}

.list { padding: 8px; overflow: auto; }
.step-item {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 8px 10px;
  background: #fff;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
}
.step-item:hover { background: #fafbff; }
.step-item.active {
  background: var(--accent-soft);
  border-color: var(--accent-soft-border);
}
.step-item.disabled { opacity: 0.55; }
.step-item .index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-secondary);
  background: #f1f5f9;
  border-radius: 50%;
  flex-shrink: 0;
}
.step-item.active .index { color: #fff; background: var(--accent); }
.step-item .info { flex: 1; min-width: 0; }
.step-item .name {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary);
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}
.step-item .row2 { display: flex; gap: 6px; align-items: center; margin-top: 2px; }
.step-item .kind {
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: #64748b;
  background: #f1f5f9;
  padding: 1px 5px;
  border-radius: 3px;
}
.step-item .method {
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
}
.m-get { color: #15803d; background: #dcfce7; }
.m-post { color: #b45309; background: #fef3c7; }
.m-put, .m-patch { color: #1d4ed8; background: #dbeafe; }
.m-delete { color: #b91c1c; background: #fee2e2; }
.step-item .path {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}
.empty {
  padding: 32px 12px;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.fe-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.fe-head h3 { margin: 0; font-size: 13px; font-weight: 700; }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }

.bind-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 6px;
  margin-bottom: 6px;
}

.config-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}
.config-row label {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
}
.retry-row {
  display: flex;
  gap: 6px;
  align-items: center;
}
.retry-row span { font-size: 11px; color: var(--color-text-secondary); }

.var-row {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 4px 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  background: #f8fafc;
  border-radius: 4px;
  margin-bottom: 4px;
}
.var-row code { color: var(--accent); }

.preview {
  padding: 12px;
  margin: 0;
  max-height: 280px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.5;
  color: #cbd5e1;
  background: #0f172a;
  border-radius: 6px;
}

@media (max-width: 1200px) {
  .body { grid-template-columns: 240px 1fr; }
  .config-panel { grid-column: 1 / -1; }
}
</style>
