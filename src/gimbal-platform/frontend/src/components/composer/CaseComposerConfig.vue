<!--
  CaseComposerConfig.vue — ③ 配置 (现代化设计)
  4 个子区块: 时间策略 / 重试 / 变量 / 服务
-->
<template>
  <div class="config-grid">
    <!-- 时间策略 -->
    <div class="config-card">
      <div class="card-head">
        <div class="head-icon time"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></div>
        <div>
          <h3>时间策略</h3>
          <p class="muted">控制步骤执行的耗时采集与超时检测</p>
        </div>
      </div>
      <div class="time-grid">
        <button
          v-for="opt in TIME_OPTS"
          :key="opt.value"
          class="time-tile"
          :class="{ active: local.timePolicy.kind === opt.value }"
          @click="selectTimePolicy(opt.value)"
        >
          <div class="time-name">{{ opt.name }}</div>
          <div class="time-desc">{{ opt.desc }}</div>
        </button>
      </div>
      <div v-if="local.timePolicy.kind === 'timeout'" class="time-seconds">
        <label class="seconds-label">超时秒数 (seconds)</label>
        <el-input-number
          :model-value="(local.timePolicy as any).seconds"
          @update:model-value="(v: any) => (local.timePolicy as any).seconds = v"
          :min="1"
          :max="3600"
          class="modern-number"
        />
      </div>
    </div>

    <!-- 重试 -->
    <div class="config-card">
      <div class="card-head">
        <div class="head-icon retry"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><polyline points="21 3 21 8 16 8"/></svg></div>
        <div>
          <h3>重试策略</h3>
          <p class="muted">失败步骤的重试 — 默认 0 次</p>
        </div>
      </div>
      <div class="retry-row">
        <div class="retry-field retry-toggle">
          <label>启用重试</label>
          <el-switch
            :model-value="local.retry !== null"
            @update:model-value="(v: any) => onRetryToggle(!!v)"
          />
        </div>
        <template v-if="local.retry">
          <div class="retry-field">
            <label>最大尝试次数 (maxAttempts)</label>
            <el-input-number
              v-model="local.retry.maxAttempts"
              :min="1"
              :max="10"
              :step="1"
              class="modern-number"
            />
          </div>
          <div class="retry-field">
            <label>退避秒数 (backoffSeconds)</label>
            <el-input-number
              v-model="local.retry.backoffSeconds"
              :min="0"
              :max="600"
              :step="1"
              class="modern-number"
            />
          </div>
        </template>
      </div>
      <p v-if="local.retry" class="muted hint-line">retryOn: {{ local.retry.retryOn.length ? local.retry.retryOn.join(', ') : '(空 — 默认不限定)' }}</p>
    </div>

    <!-- PRD §6.4 setup: 用例前置 (phase=before_request) -->
    <div class="config-card">
      <div class="card-head">
        <div class="head-icon setup"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg></div>
        <div>
          <h3>用例前置 (setup)</h3>
          <p class="muted">用例开始前执行 — 准备数据 / 启动 mock / 清理状态</p>
        </div>
      </div>
      <div v-if="!setupList.length" class="empty-small">
        <p class="muted">还没有前置动作</p>
      </div>
      <div v-else class="action-list">
        <div v-for="(s, i) in setupList" :key="i" class="action-row">
          <span class="phase-tag setup">before_request</span>
          <el-input v-model="s.name" placeholder="动作名 (例: clear-cache)" size="small" class="action-name" />
          <el-input v-model="s.kind" placeholder="类型 (mock_seed / db_seed / ...)" size="small" class="action-kind" />
          <textarea
            :value="JSON.stringify(s.payload || {}, null, 2)"
            @input="e => s.payload = parseJson((e.target as HTMLTextAreaElement).value, {})"
            class="json-input"
            rows="2"
            placeholder="动作参数 (JSON)"
          />
          <button class="action-del" @click="setupList.splice(i, 1)">×</button>
        </div>
      </div>
      <button class="add-var more" @click="addSetup">+ 添加前置</button>
    </div>

    <!-- PRD §6.4 teardown: 用例后置 (phase=teardown) -->
    <div class="config-card">
      <div class="card-head">
        <div class="head-icon teardown"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/></svg></div>
        <div>
          <h3>用例后置 (teardown)</h3>
          <p class="muted">用例结束后执行 — 清理数据 / 关闭 mock</p>
        </div>
      </div>
      <div v-if="!teardownList.length" class="empty-small">
        <p class="muted">还没有后置动作</p>
      </div>
      <div v-else class="action-list">
        <div v-for="(s, i) in teardownList" :key="i" class="action-row">
          <span class="phase-tag teardown">teardown</span>
          <el-input v-model="s.name" placeholder="动作名 (例: cleanup-mock)" size="small" class="action-name" />
          <el-input v-model="s.kind" placeholder="类型" size="small" class="action-kind" />
          <textarea
            :value="JSON.stringify(s.payload || {}, null, 2)"
            @input="e => s.payload = parseJson((e.target as HTMLTextAreaElement).value, {})"
            class="json-input"
            rows="2"
            placeholder="动作参数 (JSON)"
          />
          <button class="action-del" @click="teardownList.splice(i, 1)">×</button>
        </div>
      </div>
      <button class="add-var more" @click="addTeardown">+ 添加后置</button>
    </div>

    <!-- 共享变量 -->
    <div class="config-card vars-card">
      <div class="card-head">
        <div class="head-icon vars"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div>
        <div>
          <h3>共享变量 (vars) — 按 <code>&lt;system&gt;.key</code> 命名空间分组</h3>
          <p class="muted">用例级共享 — 在 ④ 步骤编辑 中可用 <code>${var.x}</code> 引用</p>
        </div>
      </div>
      <div v-if="!varsRows.length" class="empty-small">
        <p class="muted">还没有变量</p>
      </div>
      <div v-else class="ns-grid">
        <div v-for="(group, sys) in varsBySystem" :key="sys" class="ns-group">
          <div class="ns-head">
            <span class="ns-sys" :class="`s-${sys}`">{{ systemLabel(sys) }}</span>
            <span class="ns-count">{{ group.length }} keys</span>
          </div>
          <div v-for="(v, j) in group" :key="j" class="var-row">
            <el-input
              :model-value="v.key"
              @update:model-value="val => v.key = val"
              placeholder="变量名"
              size="small"
              class="var-key"
            />
            <span class="var-eq">=</span>
            <el-input
              :model-value="formatVarValue(v.value)"
              @update:model-value="val => v.value = parseVarValue(val)"
              placeholder="值 / 引用"
              size="small"
              class="var-value"
            />
            <button class="var-del" @click="removeVar(v)">×</button>
          </div>
        </div>
      </div>
      <button class="add-var more" @click="addVar">+ 添加变量</button>
    </div>

    <!-- 服务 -->
    <div class="config-card">
      <div class="card-head">
        <div class="head-icon svc"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2"/><path d="M2 8h20M8 2v20"/></svg></div>
        <div>
          <h3>服务映射 (services) — 按系统分组</h3>
          <p class="muted">步骤的 <code>service</code> 字段会从这里查找 baseUrl (例: <code>fin.tidb-test</code>)</p>
        </div>
      </div>
      <div v-if="!serviceRows.length" class="empty-small">
        <p class="muted">还没有服务映射</p>
      </div>
      <div v-else class="ns-grid">
        <div v-for="(group, sys) in servicesBySystem" :key="sys" class="ns-group">
          <div class="ns-head">
            <span class="ns-sys" :class="`s-${sys}`">{{ systemLabel(sys) }}</span>
            <span class="ns-count">{{ group.length }} services</span>
          </div>
          <div v-for="(s, i) in group" :key="i" class="svc-row">
            <el-input
              :model-value="s.alias"
              @update:model-value="val => s.alias = val"
              placeholder="alias (例: tidb-test-service)"
              size="small"
              class="svc-alias"
            />
            <span class="svc-arrow">→</span>
            <el-input
              :model-value="s.baseUrl"
              @update:model-value="val => s.baseUrl = val"
              placeholder="baseUrl"
              size="small"
              class="svc-url"
            />
            <button class="var-del" @click="removeService(sys, i)">×</button>
          </div>
        </div>
      </div>
      <button class="add-var more" @click="addService">+ 添加服务</button>
    </div>

    <!--
      导出入口已统一上移到:
        - CaseComposer 顶栏 (任意 step 都可见)
        - Scenarios.vue 工具栏 (场景库级)
      通过 ScenarioExportMenu + scenario-draft store 实现,平台侧始终持有
      进行中的 meta/steps/config/resource,无须再在本页重复一份。
    -->
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { ConfigView, RetryPolicyView } from '@/types/plate'

// plate TimePolicy 只有两态:record / timeout(带 seconds)。
// 砍掉原 cost-collect / intervalMs — 不在 plate 契约内。
const TIME_OPTS = [
  { value: 'record',  name: 'record',  desc: '记录每个 step 的耗时和响应' },
  { value: 'timeout', name: 'timeout', desc: '强制检测每个 step 是否超时(需秒数)' },
] as const

const SYS_LABELS: Record<string, string> = {
  fin: 'fin (财务)', logi: 'logi (物流)', wms: 'wms (仓储)', mall: 'mall (商城)', common: 'common (通用)',
}
function systemLabel(s: string) { return SYS_LABELS[s] || s }

// 单一 props: modelValue 绑 plate ConfigView
const props = defineProps<{ modelValue: ConfigView }>()
const emit = defineEmits<{ 'update:modelValue': [ConfigView] }>()

const local = reactive<ConfigView>({
  setup: [...(props.modelValue?.setup || [])],
  teardown: [...(props.modelValue?.teardown || [])],
  services: { ...(props.modelValue?.services || {}) },
  users: { ...(props.modelValue?.users || {}) },
  timePolicy: props.modelValue?.timePolicy?.kind === 'timeout'
    ? { kind: 'timeout', seconds: (props.modelValue.timePolicy as any).seconds ?? 30 }
    : { kind: 'record' },
  retry: props.modelValue?.retry ?? null,
  vars: { ...(props.modelValue?.vars || {}) },
})

// setup / teardown 列表 (PRD §6.4)
const setupList = ref<Array<{ name: string; kind: string; payload: any }>>(
  ((props.modelValue as any)?.setup as any[]) || []
)
const teardownList = ref<Array<{ name: string; kind: string; payload: any }>>(
  ((props.modelValue as any)?.teardown as any[]) || []
)

const serviceRows = ref<Array<{ alias: string; baseUrl: string }>>(
  Object.entries(props.modelValue?.services ?? {}).map(([alias, baseUrl]) => ({ alias, baseUrl: baseUrl as string }))
)

// ── vars list<->dict 边界 (pre-flight ruling #1) ──
// plate vars 是 Record<string, unknown>;UI 维护按命名空间分组的 rows 编辑,
// 在 load/emit 时与 dict 互转。
interface VarRow { key: string; value: unknown }
const varsRows = ref<VarRow[]>(
  Object.entries(props.modelValue?.vars ?? {}).map(([key, value]) => ({ key, value }))
)

// 按 <system>.key 命名空间分组 (PRD §5.3)
function namespaceOf(key: string): string {
  const dot = key.indexOf('.')
  return dot > 0 ? key.substring(0, dot) : 'common'
}
const varsBySystem = computed(() => {
  const out: Record<string, VarRow[]> = {}
  for (const v of varsRows.value) {
    const sys = namespaceOf(v.key || '')
    if (!out[sys]) out[sys] = []
    out[sys].push(v)
  }
  return out
})
const servicesBySystem = computed(() => {
  const out: Record<string, Array<{ alias: string; baseUrl: string }>> = {}
  for (const s of serviceRows.value) {
    const sys = namespaceOf(s.alias || 'common')
    if (!out[sys]) out[sys] = []
    out[sys].push(s)
  }
  return out
})

watch(() => props.modelValue, (v) => {
  if (!v) return
  local.setup = [...(v.setup || [])]
  local.teardown = [...(v.teardown || [])]
  local.services = { ...(v.services || {}) }
  local.users = { ...(v.users || {}) }
  local.timePolicy = v.timePolicy?.kind === 'timeout'
    ? { kind: 'timeout', seconds: (v.timePolicy as any).seconds ?? 30 }
    : { kind: 'record' }
  local.retry = v.retry ?? null
  local.vars = { ...(v.vars || {}) }
  serviceRows.value = Object.entries(v.services || {}).map(([alias, baseUrl]) => ({ alias, baseUrl: baseUrl as string }))
  setupList.value = ((v as any).setup as any[]) || []
  teardownList.value = ((v as any).teardown as any[]) || []
  varsRows.value = Object.entries(v.vars || {}).map(([key, value]) => ({ key, value }))
}, { deep: true })

watch([local, serviceRows, setupList, teardownList, varsRows], () => {
  // 把 vars rows 折叠回 dict (同名 last-wins)
  const varsDict: Record<string, unknown> = {}
  for (const r of varsRows.value) {
    if (r.key) varsDict[r.key] = r.value
  }
  emit('update:modelValue', {
    setup: [...setupList.value],
    teardown: [...teardownList.value],
    services: Object.fromEntries(
      serviceRows.value.filter(r => r.alias).map(r => [r.alias, r.baseUrl])
    ),
    users: local.users || {},
    timePolicy: local.timePolicy,
    retry: local.retry,
    vars: varsDict,
  })
}, { deep: true })

// ── timePolicy 切换 ──
function selectTimePolicy(kind: 'record' | 'timeout') {
  local.timePolicy = kind === 'timeout'
    ? { kind: 'timeout', seconds: 30 }
    : { kind: 'record' }
}

// ── retry 开关 ──
function onRetryToggle(on: boolean) {
  local.retry = on
    ? { kind: 'retry_policy', maxAttempts: 1, backoffSeconds: 20, retryOn: [] } as RetryPolicyView
    : null
}

// ── vars 编辑 (操作 varsRows,emit 时折叠回 dict) ──
function addVar() { varsRows.value.push({ key: '', value: '' }) }
function removeVar(row: VarRow) {
  varsRows.value = varsRows.value.filter(r => r !== row)
}
function formatVarValue(v: unknown) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  return JSON.stringify(v)
}
function parseVarValue(s: string): unknown {
  if (!s) return ''
  if (/^-?\d+(\.\d+)?$/.test(s)) return Number(s)
  if (s === 'true' || s === 'false') return s === 'true'
  if (s.startsWith('{') || s.startsWith('[') || s.startsWith('"')) {
    try { return JSON.parse(s) } catch { return s }
  }
  return s
}
function addService() { serviceRows.value.push({ alias: '', baseUrl: '' }) }
function removeService(sys: string, i: number) {
  const list = (servicesBySystem.value as any)[sys]
  if (!list) return
  const target = list[i]
  serviceRows.value = serviceRows.value.filter(s => s !== target)
}
function addSetup() { setupList.value.push({ name: '', kind: '', payload: {} }) }
function addTeardown() { teardownList.value.push({ name: '', kind: '', payload: {} }) }
function parseJson(s: string, fallback: unknown) {
  try { return JSON.parse(s) } catch { return fallback }
}
</script>

<style scoped>
.config-grid {
  display: grid;
  /* 自适应: 屏宽够时 3 列 (1920+), 默认 2 列 (1366+), 窄屏 1 列 */
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
  max-width: min(100%, 1800px);
  margin: 0 auto;
}
.config-card {
  background: #fff;
  border: 1px solid #e6e8ec;
  border-radius: 16px;
  padding: 22px 24px;
  transition: box-shadow 0.15s;
}
.config-card:hover { box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04); }
.vars-card { grid-column: 1 / -1; }

.card-head {
  display: flex; align-items: flex-start; gap: 12px;
  margin-bottom: 16px;
}
.head-icon {
  width: 36px; height: 36px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.head-icon.time { background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); color: #1e40af; }
.head-icon.retry { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); color: #92400e; }
.head-icon.setup { background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%); color: #065f46; }
.head-icon.teardown { background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%); color: #9d174d; }
.head-icon.vars { background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%); color: #6b21a8; }
.head-icon.svc { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); color: #92400e; }

.card-head h3 { margin: 0 0 2px; font-size: 15px; font-weight: 700; }
.card-head .muted { margin: 0; font-size: 12px; color: #5a6273; }
.card-head .muted code {
  font-family: var(--font-mono); background: #f1f5f9;
  padding: 1px 4px; border-radius: 3px; color: #4f46e5; font-size: 11px;
}

/* time policy */
.time-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.time-tile {
  background: #fafbfc;
  border: 1.5px solid #e6e8ec;
  border-radius: 10px;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s;
}
.time-tile:hover { border-color: #c7d2fe; }
.time-tile.active {
  border-color: #4f46e5;
  background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
}
.time-name { font-weight: 700; font-size: 13px; font-family: var(--font-mono); color: #4f46e5; }
.time-desc { font-size: 11px; color: #5a6273; margin-top: 4px; line-height: 1.4; }
.time-seconds {
  display: flex; align-items: center; gap: 12px;
  margin-top: 10px; padding: 8px 10px;
  background: #fafbfc; border-radius: 8px; border: 1px solid #e6e8ec;
}
.seconds-label { font-size: 12px; color: #5a6273; font-weight: 500; }
.time-seconds .modern-number { width: 140px; }

/* retry */
.retry-row { display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-end; }
.retry-field { flex: 1; min-width: 140px; }
.retry-toggle { flex: 0 0 auto; }
.retry-field label { display: block; font-size: 12px; color: #5a6273; margin-bottom: 6px; }
.hint-line { margin: 8px 0 0; font-size: 11px; }
.modern-number { width: 100%; }
.modern-number :deep(.el-input-number__decrease),
.modern-number :deep(.el-input-number__increase) { background: #f5f6fa; }
.modern-number :deep(.el-input__wrapper) { background: #fafbfc; box-shadow: 0 0 0 1px #e6e8ec; border-radius: 8px; }

/* empty state */
.empty-small {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 20px;
  border: 1.5px dashed #cbd5e1; border-radius: 10px;
  text-align: center;
}
.empty-small p { margin: 0; font-size: 13px; }
.empty-small .muted { color: #94a3b8; font-size: 12px; }

.add-var {
  background: #fafbfc; border: 1.5px dashed #cbd5e1; border-radius: 8px;
  color: #5a6273; font-size: 12px; padding: 8px 16px;
  cursor: pointer; transition: all 0.15s;
  width: 100%;
}
.add-var:hover { background: #eef2ff; border-color: #c7d2fe; color: #4f46e5; }
.add-var.more { margin-top: 4px; }

.var-list, .svc-list { display: flex; flex-direction: column; gap: 6px; }
.var-row, .svc-row {
  display: flex; align-items: center; gap: 8px;
  padding: 6px; background: #fafbfc; border-radius: 8px;
}
.var-key { width: 200px; }
.var-value { flex: 1; }
.var-eq, .svc-arrow { color: #94a3b8; font-weight: 700; padding: 0 4px; }
.svc-alias { width: 200px; }
.svc-url { flex: 1; font-family: var(--font-mono); }
.var-row :deep(.el-input__wrapper),
.svc-row :deep(.el-input__wrapper) { background: #fff; box-shadow: 0 0 0 1px #e6e8ec; border-radius: 6px; }

.var-del {
  width: 28px; height: 28px; background: transparent; border: none;
  border-radius: 4px; color: #94a3b8; font-size: 18px; cursor: pointer;
}
.var-del:hover { background: #fef2f2; color: #ef4444; }

/* namespace grouping (PRD §5.3) */
.ns-grid { display: flex; flex-direction: column; gap: 12px; }
.ns-group {
  border: 1px solid #e6e8ec; border-radius: 10px; padding: 10px 12px;
  background: #fafbfc;
}
.ns-head {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 8px; padding-bottom: 6px;
  border-bottom: 1px solid #e6e8ec;
}
.ns-sys {
  padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 700;
  background: #f1f5f9; color: #475569;
}
.ns-sys.s-fin { background: #eef2ff; color: #4338ca; }
.ns-sys.s-logi { background: #cffafe; color: #0e7490; }
.ns-sys.s-wms { background: #f3e8ff; color: #6b21a8; }
.ns-sys.s-mall { background: #fce7f3; color: #9d174d; }
.ns-sys.s-common { background: #f1f5f9; color: #475569; }
.ns-count { font-size: 11px; color: #94a3b8; }

/* setup / teardown actions */
.action-list { display: flex; flex-direction: column; gap: 8px; }
.action-row {
  display: grid; grid-template-columns: auto 140px 140px 1fr auto; gap: 6px;
  padding: 6px; background: #fafbfc; border-radius: 8px;
  align-items: start;
}
.phase-tag {
  padding: 4px 6px; border-radius: 4px;
  font-family: var(--font-mono); font-size: 9px; font-weight: 700;
  align-self: center;
}
.phase-tag.setup { background: #d1fae5; color: #065f46; }
.phase-tag.teardown { background: #fce7f3; color: #9d174d; }
.action-row .json-input { min-height: 36px; }
.action-del {
  width: 24px; height: 24px; background: transparent; border: none;
  color: #94a3b8; cursor: pointer; align-self: center;
}
.action-del:hover { color: #ef4444; }
.action-row :deep(.el-input__wrapper) { background: #fff; box-shadow: 0 0 0 1px #e6e8ec; border-radius: 6px; }
</style>
