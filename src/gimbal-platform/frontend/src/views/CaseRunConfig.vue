<!-- CaseRunConfig.vue — 运行配置（4 步运行编排）
     ① 绑定场景（已完成） → ② 数据集 × 环境（active）→ ③ 认证 / 重试 / 调度 → ④ 预览组装 · 提交 Plate
     黑色预览块展示即将 POST 给 /api/scenario/action/convert 的 Scenario 草稿摘要
-->
<template>
  <section class="run-config">
    <header class="page-header">
      <div>
        <h2>▶ 运行用例</h2>
        <p>{{ caseName || caseId }} · 选择数据集 × 环境，组装 Scenario 草稿后提交 Plate</p>
      </div>
      <div class="header-actions">
        <el-button @click="router.back()">← 返回</el-button>
        <el-button :loading="validating" plain @click="onValidate">🔍 预校验草稿</el-button>
        <el-button type="primary" :loading="running" @click="onRun">
          ▶ 提交运行（{{ runCount }} 次）
        </el-button>
      </div>
    </header>

    <div class="body">
      <!-- 左侧 4 步 -->
      <aside class="stepper-card">
        <h3>运行前检查</h3>
        <ol class="step-list">
          <li :class="{ done: true }">
            <span class="dot done">✓</span>
            <span class="text">绑定场景</span>
            <span class="hint">{{ scenarioId }}</span>
          </li>
          <li :class="{ active: true }">
            <span class="dot active">2</span>
            <span class="text">选择数据集 × 环境</span>
            <span class="hint">{{ selectedDataSets.length }} × {{ selectedEnv ? '1' : '0' }}</span>
          </li>
          <li :class="{ pending: true }">
            <span class="dot pending">3</span>
            <span class="text">认证 / 重试 / 调度</span>
          </li>
          <li :class="{ pending: true }">
            <span class="dot pending">4</span>
            <span class="text">预览组装 · 提交 Plate</span>
          </li>
        </ol>
      </aside>

      <!-- 右侧配置 -->
      <main class="config-area">
        <!-- 数据集选择 -->
        <section class="card">
          <header class="card-head">
            <h3>② 选择数据集（多选）</h3>
            <span class="muted">已选 {{ selectedDataSets.length }}</span>
          </header>
          <div class="ds-grid">
            <label
              v-for="d in dataSets"
              :key="d.datasetId"
              class="ds-tile"
              :class="{ active: selectedDataSets.includes(d.datasetId) }"
            >
              <input
                type="checkbox"
                :checked="selectedDataSets.includes(d.datasetId)"
                @change="toggleDS(d.datasetId)"
              />
              <div class="ds-info">
                <div class="row1">
                  <strong>{{ d.name }}</strong>
                  <span class="count">{{ d.rowCount }} 条</span>
                </div>
                <div class="row2">{{ previewOf(d) }}</div>
              </div>
              <span v-if="d.lastRunStatus" class="status-cell">
                <StatusBadge :status="d.lastRunStatus" />
              </span>
            </label>
            <el-empty
              v-if="!dataSets.length"
              description="此用例还没有数据集"
              :image-size="60"
            />
          </div>
        </section>

        <!-- 环境选择 -->
        <section class="card">
          <header class="card-head"><h3>② 选择执行环境</h3></header>
          <div class="env-grid">
            <label
              v-for="e in envs"
              :key="e.envId"
              class="env-tile"
              :class="{ active: selectedEnv === e.envId }"
            >
              <input
                type="radio"
                :checked="selectedEnv === e.envId"
                @change="selectedEnv = e.envId"
              />
              <div class="env-info">
                <strong>{{ e.name }}</strong>
                <code>{{ e.baseUrl }}</code>
              </div>
            </label>
          </div>
        </section>

        <!-- 认证 / 重试 / 调度 -->
        <section class="card">
          <header class="card-head"><h3>③ 认证 / 重试 / 调度</h3></header>
          <div class="grid-3">
            <el-form-item label="执行用认证（多选）">
              <el-select
                v-model="authAliases"
                multiple
                filterable
                placeholder="选择 0..n 个凭证"
                style="width:100%"
              >
                <el-option
                  v-for="a in authSessions"
                  :key="a.id"
                  :value="a.alias"
                  :label="`${a.alias} · ${a.username} · ${a.token_type}`"
                />
              </el-select>
              <!-- &lt;alias&gt; 实体:裸尖括号会被 Vue 模板解析器当标签 -->
              <p class="auth-hint">
                场景 headers 里 <code v-pre>${auth.&lt;alias&gt;.*}</code> 引用的 alias 须包含在此，
                运行时由 executor 解密注入 — 明文不落草稿。
              </p>
            </el-form-item>
            <el-form-item label="重试次数">
              <el-input-number v-model="retryMaxAttempts" :min="0" :max="10" />
            </el-form-item>
            <el-form-item label="间隔(ms)">
              <el-input-number v-model="retryIntervalMs" :min="100" :step="100" />
            </el-form-item>
          </div>
        </section>

        <!-- 组装预览 -->
        <section class="card preview-card">
          <header class="card-head">
            <h3>📦 即将提交给 Plate 的 Scenario 草稿</h3>
            <span class="badge">{{ runCount }} 次运行</span>
          </header>
          <pre>{{ JSON.stringify(draft, null, 2) }}</pre>
        </section>

        <div class="actions">
          <el-checkbox v-model="saveAsTemplate">💾 保存为运行模板</el-checkbox>
          <div class="right">
            <el-button @click="router.back()">返回</el-button>
            <el-button :loading="validating" plain @click="onValidate">🔍 预校验</el-button>
            <el-button type="primary" :loading="running" @click="onRun">
              ▶ 提交运行（{{ runCount }} 次）
            </el-button>
          </div>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import StatusBadge from '@/components/StatusBadge.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { list as listAuths } from '@/api/auth_sessions'
import type { AuthSession as AuthSessionDTO } from '@/api/auth_sessions'
import { authAliasesIn } from '@/utils/tpl-refs'
import type { DataSetSummary } from '@/types/scenario-composer'

const AUTH_HINT_MAX = 3

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()
const caseId = route.params.caseId as string
const presetDataSetId = (route.query.dataSetId as string) || ''
const presetDataSetIds = (route.query.dataSetIds as string) || ''

const selectedDataSets = ref<string[]>(
  presetDataSetId ? [presetDataSetId] :
  presetDataSetIds ? presetDataSetIds.split(',').filter(Boolean) : [],
)
const selectedEnv = ref<string>('')
/** 执行用认证(多选)。替换旧 AUTH_LIST 硬编码 — 数据源 /api/auths(owner 级) */
const authAliases = ref<string[]>([])
const authSessions = ref<AuthSessionDTO[]>([])
const retryMaxAttempts = ref(0)
const retryIntervalMs = ref(500)
const saveAsTemplate = ref(false)
const validating = ref(false)
const running = ref(false)

const dataSets = computed(() => store.dataSetsOfCase(caseId))
const envs = computed(() => store.envs)

const currentCase = computed(() => store.caseById(caseId))
const scenarioId = computed(() => currentCase.value?.scenarioId ?? '')
const caseName = computed(() => currentCase.value?.name ?? '')

const runCount = computed(() => {
  if (!selectedDataSets.value.length || !selectedEnv.value) return 0
  const ds = dataSets.value.filter((d) => selectedDataSets.value.includes(d.datasetId))
  return ds.reduce((s, d) => s + d.rowCount, 0)
})

// 容器形 {definition, orchestration} — 满足后端 ScenarioDraft 契约(必填 definition)。
// definition 取自读侧 scenario(其 config/resource 已是 plate 形,由 composer 持久化);
// 不再注入 case 级 run-config(cost-collect / {intervalMs} —— plate 拒绝这些 scenario 级字段)。
// 读侧 Scenario 把 config/resource/orchestration 类型化为 Record<string,unknown> / Orchestration?,
// 而 ScenarioView 需要 ConfigView,故在此局部 `as` 转换(运行时确为 plate 形,见 scenario-composer.ts 注释)。
const draft = computed(() => {
  const s = store.scenarioById(scenarioId.value)
  const definition = {
    kind: 'scenario' as const,
    scenarioId: scenarioId.value,
    meta: s?.meta ?? {},
    config: (s?.config ?? {
      setup: [], teardown: [], services: {}, users: {},
      timePolicy: { kind: 'record' }, retry: null, vars: {},
    }) as any,
    resource: s?.resource ?? {},
    steps: s?.steps ?? [],
  }
  const orchestration = s?.orchestration ?? {
    steps: (s?.steps ?? []).map(() => ({ enabled: true, name: '' })),
    resourceMeta: {},
  }
  return { definition, orchestration }
})

onMounted(async () => {
  try {
    if (!store.scenarios.length) await store.fetchScenarios()
    if (!store.cases.length)      await store.fetchCases()
    if (!store.dataSets.length)   await store.fetchDataSets()
    if (!store.envs.length)       await store.fetchEnvs()
    if (envs.value[0])            selectedEnv.value = envs.value[0].envId
    authSessions.value = await listAuths()
  } catch (e) {
    showError('加载运行配置', undefined, (e as Error).message)
  }
})

function toggleDS(id: string) {
  const idx = selectedDataSets.value.indexOf(id)
  if (idx >= 0) selectedDataSets.value.splice(idx, 1)
  else selectedDataSets.value.push(id)
}

function previewOf(d: DataSetSummary) {
  const cols = Object.keys(d.preview[0] ?? {})
  return cols.slice(0, 3).join(' · ')
}

async function onValidate() {
  validating.value = true
  try {
    const res = await store.previewPlate(draft.value)
    if (res.ok) ElMessage.success('预校验通过')
    else        ElMessage.warning(`未通过：${res.errors?.length ?? 0} 个错误`)
  } catch (e) {
    showError('预校验', undefined, (e as Error).message)
  } finally {
    validating.value = false
  }
}

/**
 * 悬空认证扫描:场景全部 step headers 里的 ${auth.X} 引用 vs 已选 aliases。
 * 仅警告放行 — Gimbal 解析失败会在步骤级报错,与运行语义一致(定案)。
 */
function danglingAuthRefs(): string[] {
  const referenced = new Set<string>()
  for (const s of draft.value.definition.steps ?? []) {
    const headers = (s as { api?: { headers?: Record<string, string> } })?.api?.headers
    if (!headers) continue
    for (const v of Object.values(headers)) {
      for (const a of authAliasesIn(String(v))) referenced.add(a)
    }
  }
  return [...referenced].filter((a) => !authAliases.value.includes(a))
}

async function onRun() {
  if (!runCount.value) {
    ElMessage.warning('请先选择数据集和环境')
    return
  }
  const dangling = danglingAuthRefs()
  if (dangling.length) {
    const shown = dangling.slice(0, AUTH_HINT_MAX).join('、')
    const more = dangling.length > AUTH_HINT_MAX ? ` 等 ${dangling.length} 个` : ''
    ElMessage.warning(
      `headers 引用了未勾选的认证: ${shown}${more} — 运行时将解析失败,建议勾选或移除引用(本次仍会提交)`,
    )
  }
  running.value = true
  try {
    const env = envs.value.find((e) => e.envId === selectedEnv.value)
    if (!env) throw new Error('环境不存在')
    const { runId } = await store.runCase({
      caseId,
      dataSetIds: selectedDataSets.value,
      env,
      auths: authAliases.value,
      retry: { maxAttempts: retryMaxAttempts.value, intervalMs: retryIntervalMs.value },
    })
    ElMessage.success(`已启动运行 · ${runId}`)
    router.push(`/executions/${runId}`)
  } catch (e) {
    showError('提交运行', undefined, (e as Error).message)
  } finally {
    running.value = false
  }
}
</script>

<style scoped>
.run-config {
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
.auth-hint {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}
.auth-hint code {
  font-family: var(--font-mono);
  background: var(--color-bg-secondary, #f1f5f9);
  padding: 0 3px;
  border-radius: 3px;
}

.body {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
}

.stepper-card {
  padding: 16px 18px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
  align-self: flex-start;
}
.stepper-card h3 {
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 700;
}
.step-list {
  padding: 0;
  margin: 0;
  list-style: none;
}
.step-list li {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 8px 10px;
  margin-bottom: 4px;
  border: 1px solid transparent;
  border-radius: 6px;
}
.step-list li.active {
  background: var(--accent-soft);
  border-color: var(--accent-soft-border);
}
.step-list li.active .text { font-weight: 600; color: var(--accent); }
.step-list li.done .text  { color: #15803d; }
.step-list li.pending { opacity: 0.7; }

.step-list .dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  border-radius: 50%;
}
.step-list .dot.active   { color: #fff; background: var(--accent); }
.step-list .dot.done     { color: #fff; background: #15803d; }
.step-list .dot.pending  { color: var(--color-text-tertiary); background: #f8fafc; border: 1px solid var(--color-border-tertiary); }

.step-list .text { flex: 1; font-size: 12px; }
.step-list .hint {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--color-text-secondary);
}

.config-area { display: flex; flex-direction: column; gap: 12px; }
.card {
  padding: 16px 18px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 8px;
}
.card-head {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.card-head h3 { margin: 0; font-size: 13px; font-weight: 700; }

.muted { color: var(--color-text-secondary); font-size: 11px; }
.badge {
  padding: 2px 8px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: #c7d2fe;
  background: #312e81;
  border-radius: 10px;
}

.ds-grid, .env-grid {
  display: grid;
  gap: 8px;
}
.ds-grid { grid-template-columns: 1fr; }
.env-grid { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }

.ds-tile, .env-tile {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
  cursor: pointer;
}
.ds-tile:hover, .env-tile:hover { border-color: var(--accent); }
.ds-tile.active, .env-tile.active {
  background: var(--accent-soft);
  border-color: var(--accent);
}
.ds-tile input, .env-tile input { accent-color: var(--accent); }

.ds-info, .env-info { flex: 1; min-width: 0; }
.ds-info .row1 {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 12px;
}
.ds-info .count {
  padding: 1px 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: #f1f5f9;
  border-radius: 3px;
}
.ds-info .row2 {
  margin-top: 2px;
  overflow: hidden;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  text-overflow: ellipsis;
}
.status-cell { margin-left: auto; }

.env-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}
.env-info code {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--color-text-secondary);
}

.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

.preview-card {
  background: #0f172a;
  border-color: #1f2933;
}
.preview-card h3, .preview-card .badge { color: #f5f3ff; }
.preview-card pre {
  margin: 0;
  max-height: 240px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.55;
  color: #cbd5e1;
}

.actions {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}
.actions .right { display: flex; gap: 8px; }

@media (max-width: 1100px) {
  .body { grid-template-columns: 1fr; }
  .grid-3 { grid-template-columns: 1fr; }
}
</style>
