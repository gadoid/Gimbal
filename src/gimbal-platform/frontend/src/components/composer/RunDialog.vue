<!--
  RunDialog.vue — 运行对话框 (env + data-set 选择)
  V3 composer 1:1 模型: 通过 case 自动选择 data-set, env 来自平台 /api/envs
-->
<template>
  <Teleport to="body">
    <div class="run-overlay" @click.self="$emit('close')">
      <div class="run-dialog" role="dialog" aria-modal="true">
        <header class="run-header">
          <div>
            <h2>运行编排</h2>
            <p class="muted">从 <code>{{ scenario?.meta?.scenarioId || '—' }}</code> 触发执行</p>
          </div>
          <button class="icon-btn" @click="$emit('close')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </header>

        <div class="run-body">
          <!-- 环境选择 -->
          <section class="run-section">
            <label class="run-label">执行环境</label>
            <div class="env-grid">
              <button
                v-for="env in envs"
                :key="env.envId"
                class="env-tile"
                :class="{ active: selectedEnv === env.envId }"
                @click="selectedEnv = env.envId"
                type="button"
              >
                <div class="env-tile-head">
                  <span class="env-radio"></span>
                  <span class="env-name">{{ env.name }}</span>
                </div>
                <div class="env-url">{{ env.baseUrl }}</div>
              </button>
              <div v-if="envs.length === 0" class="muted small">暂无可用环境 (请检查 Plate 服务)</div>
            </div>
          </section>

          <!-- 数据集选择 -->
          <section class="run-section">
            <div class="label-row">
              <label class="run-label">数据集 <span class="muted small">(可多选, 不选则该数据集的行不参与运行)</span></label>
              <button class="link-btn" @click="onCreateDataSet" type="button">+ 新建数据集</button>
            </div>
            <div class="ds-grid ds-grid-baseline">
              <label class="ds-tile baseline" :class="{ active: useBaseline }">
                <input
                  type="checkbox"
                  data-test="baseline"
                  :checked="useBaseline"
                  @change="toggleBaseline"
                />
                <div class="ds-info">
                  <div class="ds-name">默认配置(基线)</div>
                  <div class="ds-meta"><span class="ds-rows">1 次运行</span></div>
                  <div class="ds-preview"><code>不选数据集 — 步骤直填值 + 共享变量默认值</code></div>
                </div>
              </label>
            </div>
            <div v-if="dataSets.length === 0" class="empty-data">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 3v18"/>
              </svg>
              <p>暂无数据集 — 创建一个数据集来参数化运行</p>
              <button class="primary-btn" @click="onCreateDataSet">+ 新建第一个数据集</button>
            </div>
            <div v-else class="ds-grid">
              <label
                v-for="ds in dataSets"
                :key="ds.datasetId"
                class="ds-tile"
                :class="{ active: selectedDatasets.includes(ds.datasetId) }"
              >
                <input
                  type="checkbox"
                  :value="ds.datasetId"
                  v-model="selectedDatasets"
                />
                <div class="ds-info">
                  <div class="ds-name">{{ ds.name }}</div>
                  <div class="ds-meta">
                    <span class="ds-rows">{{ ds.rowCount }} 行</span>
                  </div>
                  <div v-if="ds.preview.length" class="ds-preview">
                    <code>{{ JSON.stringify(ds.preview[0]) }}</code>
                  </div>
                </div>
              </label>
            </div>
          </section>

          <!-- 高级选项 (V1 能力移植) -->
          <section class="run-section">
            <label class="run-label">高级选项 <span class="muted small">(V1 兼容:步进调试 / 凭证策略 / 批量执行)</span></label>
            <div class="adv-grid">
              <div class="adv-field">
                <span class="adv-name">停止于步骤</span>
                <select v-model.number="stepTo" class="adv-select" :disabled="stepCount === 0">
                  <option :value="null" :disabled="stepCount === 0">运行全部步骤</option>
                  <option v-for="i in stepCount" :key="i" :value="i - 1">
                    第 {{ i }} 步后停止{{ stepName(i - 1) }}
                  </option>
                </select>
              </div>
              <div class="adv-field">
                <span class="adv-name">凭证合并策略</span>
                <div class="policy-group">
                  <label
                    v-for="p in POLICIES"
                    :key="p.value"
                    class="policy-opt"
                    :class="{ active: mergePolicy === p.value }"
                  >
                    <input type="radio" :value="p.value" v-model="mergePolicy" />
                    <span>{{ p.label }}</span>
                  </label>
                </div>
                <div class="muted small policy-hint">{{ policyHint }}</div>
              </div>
              <div class="adv-field">
                <span class="adv-name">执行次数 / 并发度</span>
                <div class="num-row">
                  <input type="number" v-model.number="nRuns" class="adv-input" min="1" max="1000" />
                  <span class="num-sep">次 ×</span>
                  <input type="number" v-model.number="parallel" class="adv-input" min="1" max="200" />
                  <span class="num-sep">并发</span>
                </div>
              </div>
              <div class="adv-field">
                <span class="adv-name">提单号前缀</span>
                <input
                  type="text"
                  v-model.trim="prefix"
                  class="adv-input"
                  maxlength="64"
                  placeholder="留空 = 不注入 order_no 变量"
                />
              </div>
            </div>
            <div class="preset-row">
              <span class="muted small">快捷预设:</span>
              <button
                v-for="p in PRESETS"
                :key="p.label"
                type="button"
                class="preset-btn"
                :class="{ active: nRuns === p.nRuns && parallel === p.parallel }"
                @click="applyPreset(p)"
              >{{ p.label }}</button>
            </div>
            <div v-if="stepCount === 0" class="muted small">场景暂无步骤,停止于步骤不可用</div>
          </section>

          <!-- 错误显示 -->
          <div v-if="lastRunError" class="run-error">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <div>
              <div class="err-title">运行失败</div>
              <div class="err-msg">{{ lastRunError }}</div>
            </div>
          </div>

          <!-- 成功显示 -->
          <div v-if="lastRunId && !lastRunError" class="run-success">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
            <div>
              <div class="success-title">运行已发起</div>
              <div class="success-msg">runId: <code>{{ lastRunId }}</code> — 跳转到执行历史…</div>
            </div>
          </div>
        </div>

        <footer class="run-footer">
          <div class="run-summary">
            <span v-if="useBaseline" class="summary-chip">基线 ×1</span>
            <span v-if="selectedDatasets.length" class="summary-chip">
              {{ selectedDatasets.length }} 数据集
            </span>
            <span v-if="selectedEnv" class="summary-chip env">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/>
              </svg>
              {{ selectedEnv }}
            </span>
            <span class="summary-chip total">
              {{ totalRuns }} 次运行
            </span>
            <span v-if="parallel > 1" class="summary-chip">
              并发 {{ parallel }}
            </span>
          </div>
          <div class="run-actions">
            <button class="ghost-btn" @click="$emit('close')">取消</button>
            <button
              class="primary-btn"
              :disabled="!selectedEnv || running"
              @click="onConfirm"
            >
              <svg v-if="!running" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              <svg v-else class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>
              {{ running ? '运行中…' : '发起运行' }}
            </button>
          </div>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { promptAction } from '@/utils/confirmAction'
import * as api from '@/api/scenario-composer'
import type { MergePolicy } from '@/api/executions'
import type { Scenario, DataSetSummary, RunEnv } from '@/types/scenario-composer'

const props = defineProps<{
  scenario: Scenario | null
  dataSets: DataSetSummary[]
  envs: RunEnv[]
  running: boolean
  lastRunId: string | null
  lastRunError: string | null
}>()
const emit = defineEmits<{
  close: []
  confirm: [
    envId: string,
    dataSetIds: string[],
    opts?: {
      stepTo?: number | null
      injectCredentials: boolean
      nRuns?: number
      parallel?: number
      prefix?: string
      mergePolicy?: MergePolicy
    },
  ]
}>()

const selectedEnv = ref<string>(props.envs[0]?.envId || '')
const selectedDatasets = ref<string[]>([])
// D12 基线执行:不选数据集 = 直填值 + 共享变量默认值跑一次(一个隐式空覆盖行)
const useBaseline = ref(false)
// V1 能力移植:stepTo = 0-based 含端点(引擎 halt_at);null = 全量运行
const stepTo = ref<number | null>(null)
// M1 执行能力(V1 ExecutionDrawer 语义):origin 在此表达"不注入"
// (上送 injectCredentials=false),其余三选一映射后端 merge_policy。
const POLICIES = [
  { value: 'origin', label: 'origin · 不注入' },
  { value: 'override', label: 'override · 替换' },
  { value: 'merge', label: 'merge · 合并' },
  { value: 'append', label: 'append · 追加' },
] as const
const mergePolicy = ref<'origin' | MergePolicy>('merge')
const nRuns = ref(1)
const parallel = ref(1)
const prefix = ref('')
const PRESETS = [
  { label: '烟囱 1/1', nRuns: 1, parallel: 1 },
  { label: '小批量 5/3', nRuns: 5, parallel: 3 },
  { label: '压测 50/10', nRuns: 50, parallel: 10 },
] as const

function applyPreset(p: { nRuns: number; parallel: number }) {
  nRuns.value = p.nRuns
  parallel.value = p.parallel
}

const policyHint = computed(() => {
  switch (mergePolicy.value) {
    case 'origin':
      return '跳过凭证注入,以场景 yaml 自带的 Config.users 原样运行'
    case 'override':
      return 'Config.users 整块替换为所选执行认证'
    case 'append':
      return '合并注入;与场景内置 users 别名冲突时整单拒绝(409)'
    default:
      return '同名覆盖、场景内置其余认证保留(默认)'
  }
})

const stepCount = computed(() => props.scenario?.stepCount ?? 0)

/** 下拉里附上步骤名(有 name/id 时),便于定位 */
function stepName(i: number): string {
  const s = props.scenario?.steps?.[i] as { name?: string; id?: string } | undefined
  const n = s?.name || s?.id
  return n ? ` · ${n}` : ''
}

watch(() => props.envs, (envs) => {
  if (!selectedEnv.value && envs.length > 0) {
    selectedEnv.value = envs[0].envId
  }
}, { immediate: true })

watch(() => props.dataSets, (ds) => {
  if (ds.length) {
    selectedDatasets.value = ds.map(d => d.datasetId)  // 默认全选(基线关)
  } else {
    useBaseline.value = true   // 无数据集:唯一可跑的就是基线
    selectedDatasets.value = []
  }
}, { immediate: true })

// 勾回任一数据集 → 退出基线(基线与数据集互斥:基线 = 空覆盖行)
watch(selectedDatasets, (v) => { if (v.length) useBaseline.value = false })

function toggleBaseline() {
  useBaseline.value = !useBaseline.value
  if (useBaseline.value) selectedDatasets.value = []
}

const totalRuns = computed(() => {
  if (useBaseline.value) return 1 * (nRuns.value || 1)   // 基线 = 一个隐式空行
  return props.dataSets
    .filter(d => selectedDatasets.value.includes(d.datasetId))
    .reduce((sum, d) => sum + (d.rowCount || 0), 0) * (nRuns.value || 1)
})

function onConfirm() {
  if (!selectedEnv.value) {
    ElMessage.warning('请选择执行环境')
    return
  }
  // 输入钳位(与后端 schema 上限一致,防 422)
  nRuns.value = Math.min(1000, Math.max(1, Math.floor(nRuns.value || 1)))
  parallel.value = Math.min(200, Math.max(1, Math.floor(parallel.value || 1)))
  const origin = mergePolicy.value === 'origin'
  emit('confirm', selectedEnv.value, selectedDatasets.value, {
    stepTo: stepTo.value,
    injectCredentials: !origin,
    // 'origin'(保持 plate 原文)只在本地用于翻转 injectCredentials,
    // 不是后端 RunRequest 的合法 merge_policy,不随 confirm 下发。
    ...(origin ? {} : { mergePolicy: mergePolicy.value as Exclude<(typeof mergePolicy)['value'], 'origin'> }),
    ...(nRuns.value > 1 ? { nRuns: nRuns.value } : {}),
    ...(parallel.value > 1 ? { parallel: parallel.value } : {}),
    ...(prefix.value ? { prefix: prefix.value } : {}),
  })
}

async function onCreateDataSet() {
  if (!props.scenario) {
    ElMessage.warning('请先保存草稿')
    return
  }
  try {
    const name = await promptAction('数据集名称', '新建数据集', {
      inputValue: '默认数据集',
      confirmButtonText: '创建',
    })
    if (name === null || !name) return
    const rowsStr = await promptAction(
      'JSON 数组格式, 如 [{"qty": 1}, {"qty": 2}]',
      '数据集内容',
      {
        inputType: 'textarea',
        inputValue: '[]',
        confirmButtonText: '创建',
      }
    )
    if (rowsStr === null) return
    let rows: any[]
    try {
      rows = JSON.parse(rowsStr || '[]')
    } catch {
      // 解析失败必须中止：静默按 [] 创建会把用户输入整组丢掉。
      ElMessage.error('JSON 解析失败，未创建数据集 — 请检查格式后重试')
      return
    }
    if (!Array.isArray(rows)) {
      ElMessage.error('数据集内容必须是 JSON 数组（如 [{"qty": 1}]），未创建')
      return
    }
    await api.createDataSet(props.scenario.meta.scenarioId, { name, rows })
    ElMessage.success('已创建, 请重新打开运行对话框')
  } catch (e) {
    ElMessage.error('创建失败: ' + (e as Error).message)
  }
}
</script>

<style scoped>
.run-overlay {
  position: fixed; inset: 0;
  background: rgba(15, 18, 25, 0.5);
  backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
  animation: fadeIn 0.2s;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.run-dialog {
  width: 720px; max-width: 92vw; max-height: 88vh;
  background: #fff; border-radius: 16px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.25);
  display: flex; flex-direction: column;
  animation: slideUp 0.25s ease-out;
}
@keyframes slideUp { from { transform: translateY(16px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

.run-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 24px 28px 20px;
  border-bottom: 1px solid #e6e8ec;
}
.run-header h2 { margin: 0 0 4px; font-size: 20px; }
.run-header .muted { font-size: 13px; color: #5a6273; }
.run-header .muted code { font-family: var(--font-mono); background: #f1f5f9; padding: 1px 4px; border-radius: 3px; }

.icon-btn {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: transparent; border: none; border-radius: 6px;
  color: #5a6273; cursor: pointer; transition: all 0.15s;
}
.icon-btn:hover { background: #f5f6fa; color: #1a1d24; }

.run-body { padding: 20px 28px; flex: 1; overflow-y: auto; }
.run-section { margin-bottom: 24px; }
.run-label {
  display: block; font-size: 13px; font-weight: 600; color: #1a1d24;
  margin-bottom: 12px;
}
.run-label .muted { font-weight: 400; color: #94a3b8; }
.label-row { display: flex; justify-content: space-between; align-items: center; }
.link-btn {
  background: transparent; border: none; color: #4f46e5;
  font-size: 12px; cursor: pointer; padding: 0;
}
.link-btn:hover { text-decoration: underline; }

/* env grid */
.env-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;
}
.env-tile {
  text-align: left;
  background: #fff; border: 1.5px solid #e6e8ec; border-radius: 10px;
  padding: 12px 14px; cursor: pointer; transition: all 0.15s;
}
.env-tile:hover { border-color: #c7d2fe; }
.env-tile.active { border-color: #4f46e5; background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%); }
.env-tile-head { display: flex; align-items: center; gap: 8px; }
.env-radio {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid #cbd5e1; transition: all 0.15s;
}
.env-tile.active .env-radio { border-color: #4f46e5; background: radial-gradient(circle, #4f46e5 0%, #4f46e5 35%, transparent 40%); }
.env-name { font-weight: 600; font-size: 13px; }
.env-url { font-family: var(--font-mono); font-size: 11px; color: #5a6273; margin-top: 4px; padding-left: 22px; }

/* data-set grid */
.ds-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.ds-tile {
  display: flex; gap: 10px;
  background: #fff; border: 1.5px solid #e6e8ec; border-radius: 10px;
  padding: 10px 12px; cursor: pointer; transition: all 0.15s;
}
.ds-tile input { margin-top: 2px; }
.ds-tile:hover { border-color: #c7d2fe; }
.ds-tile.active { border-color: #4f46e5; background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%); }
.ds-info { flex: 1; min-width: 0; }
.ds-name { font-weight: 600; font-size: 13px; }
.ds-meta { display: flex; gap: 8px; margin-top: 2px; font-size: 11px; color: #5a6273; }
.ds-preview { margin-top: 4px; font-size: 10px; }
.ds-preview code { background: #f1f5f9; padding: 1px 4px; border-radius: 2px; }

.ds-grid-baseline { margin-bottom: 8px; }
.ds-tile.baseline { border-style: dashed; }

.empty-data {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 32px 20px; border: 1.5px dashed #cbd5e1; border-radius: 12px;
  color: #5a6273; text-align: center;
}
.empty-data p { margin: 0; font-size: 13px; }

/* advanced options */
.adv-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
}
.adv-field {
  padding: 10px 12px;
  border: 1.5px solid #e6e8ec; border-radius: 10px;
}
.adv-name {
  display: block; font-size: 12px; font-weight: 600; margin-bottom: 6px;
}
.adv-select {
  width: 100%; padding: 6px 8px;
  border: 1px solid #e6e8ec; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.adv-check {
  display: flex; gap: 6px; align-items: flex-start;
  font-size: 12px; color: #5a6273; cursor: pointer;
}
.adv-check input { margin-top: 2px; }

/* M1: merge-policy radio group + nRuns/parallel/prefix inputs + presets */
.policy-group {
  display: flex; flex-wrap: wrap; gap: 6px;
}
.policy-opt {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 8px; border: 1px solid #e6e8ec; border-radius: 999px;
  font-size: 11px; color: #5a6273; cursor: pointer; transition: all 0.15s;
}
.policy-opt.active {
  border-color: #4f46e5; background: #eef2ff; color: #4f46e5;
}
.policy-opt input { margin: 0; accent-color: #4f46e5; }
.policy-hint { margin-top: 6px; }
.num-row {
  display: flex; align-items: center; gap: 6px;
}
.adv-input {
  width: 100%; padding: 6px 8px;
  border: 1px solid #e6e8ec; border-radius: 6px;
  font-size: 12px; background: #fff;
}
.num-row .adv-input { width: 72px; }
.num-sep { font-size: 11px; color: #94a3b8; }
.preset-row {
  display: flex; align-items: center; gap: 6px; margin-top: 10px;
}
.preset-btn {
  padding: 4px 10px; border: 1px solid #e6e8ec; border-radius: 6px;
  background: #fff; font-size: 11px; color: #5a6273;
  cursor: pointer; transition: all 0.15s;
}
.preset-btn:hover { border-color: #c7d2fe; }
.preset-btn.active {
  border-color: #4f46e5; background: #eef2ff; color: #4f46e5;
}

.run-error, .run-success {
  display: flex; gap: 10px; align-items: flex-start;
  padding: 12px 14px; border-radius: 8px; margin-bottom: 16px;
}
.run-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
.run-error svg { flex-shrink: 0; color: #ef4444; margin-top: 2px; }
.err-title { font-weight: 600; font-size: 13px; }
.err-msg { font-size: 12px; margin-top: 2px; font-family: var(--font-mono); }
.run-success { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
.run-success svg { flex-shrink: 0; color: #10b981; margin-top: 2px; }
.success-title { font-weight: 600; font-size: 13px; }
.success-msg { font-size: 12px; margin-top: 2px; }
.success-msg code { font-family: var(--font-mono); background: #dcfce7; padding: 1px 4px; border-radius: 3px; }

/* footer */
.run-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 28px; border-top: 1px solid #e6e8ec;
  background: #fafbfc; border-radius: 0 0 16px 16px;
}
.run-summary { display: flex; gap: 6px; }
.summary-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 500;
  background: #eef2ff; color: #4f46e5;
}
.summary-chip.env { background: #fef3c7; color: #92400e; }
.summary-chip.total { background: #d1fae5; color: #065f46; }
.run-actions { display: flex; gap: 8px; }

.ghost-btn {
  background: transparent; border: 1px solid #e6e8ec; border-radius: 8px;
  padding: 8px 14px; font-size: 13px; color: #5a6273;
  cursor: pointer; transition: all 0.15s;
}
.ghost-btn:hover { background: #f5f6fa; }

.primary-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
  color: #fff; border: none; border-radius: 8px;
  padding: 8px 18px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
  box-shadow: 0 1px 2px rgba(79, 70, 229, 0.2);
}
.primary-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3); }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.small { font-size: 11px; }

</style>
