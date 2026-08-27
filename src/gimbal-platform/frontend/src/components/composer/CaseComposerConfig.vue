<!--
  CaseComposerConfig.vue — ③ 配置 (平面风统一)
  样式走 composer.css 共享层; 7 个子区块:
  时间策略 / 重试 / 前置 / 后置 / 变量 / 服务 / 用户认证
-->
<template>
  <div class="c-page c-form">
    <!-- 时间策略 -->
    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        <div>
          <h3>时间策略</h3>
          <p class="c-head-desc">控制步骤执行的耗时采集与超时检测</p>
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
      <div v-if="local.timePolicy.kind === 'timeout'" class="c-inline-row" style="margin-top: 8px;">
        <span class="c-inline-label">超时秒数 (seconds)</span>
        <span class="c-inline-ctrl">
          <el-input-number
            :model-value="(local.timePolicy as any).seconds"
            @update:model-value="(v: any) => (local.timePolicy as any).seconds = v"
            :min="1"
            :max="3600"
            size="small"
          />
        </span>
      </div>
    </div>

    <!-- 重试 -->
    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><polyline points="21 3 21 8 16 8"/></svg>
        <div>
          <h3>重试策略</h3>
          <p class="c-head-desc">失败步骤的重试 — 默认 0 次</p>
        </div>
      </div>
      <div class="c-inline-stack">
        <div class="c-inline-row">
          <span class="c-inline-label">启用重试</span>
          <span class="c-inline-ctrl">
            <el-switch
              :model-value="local.retry !== null"
              @update:model-value="(v: any) => onRetryToggle(!!v)"
            />
          </span>
        </div>
        <template v-if="local.retry">
          <div class="c-inline-row">
            <span class="c-inline-label">最大尝试次数 (maxAttempts)</span>
            <span class="c-inline-ctrl">
              <el-input-number
                v-model="local.retry.maxAttempts"
                :min="1"
                :max="10"
                :step="1"
                size="small"
              />
            </span>
          </div>
          <div class="c-inline-row">
            <span class="c-inline-label">退避秒数 (backoffSeconds)</span>
            <span class="c-inline-ctrl">
              <el-input-number
                v-model="local.retry.backoffSeconds"
                :min="0"
                :max="600"
                :step="1"
                size="small"
              />
            </span>
          </div>
          <p class="c-inline-hint">retryOn: {{ local.retry.retryOn.length ? local.retry.retryOn.join(', ') : '(空 — 默认不限定)' }}</p>
        </template>
      </div>
    </div>

    <!-- PRD §6.4 setup: 用例前置 (phase=before_request) -->
    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
        <div>
          <h3>用例前置 (setup)</h3>
          <p class="c-head-desc">用例开始前执行 — 准备数据 / 启动 mock / 清理状态</p>
        </div>
      </div>
      <div v-if="!setupList.length" class="c-empty">
        <p>还没有前置动作</p>
      </div>
      <div v-else class="action-list">
        <div v-for="(s, i) in setupList" :key="i" class="action-row">
          <div class="action-row-head">
            <span class="phase-tag setup">before_request</span>
            <button class="action-del" @click="setupList.splice(i, 1)">×</button>
          </div>
          <div class="action-row-grid">
            <el-input v-model="s.name" placeholder="动作名 (例: clear-cache)" size="small" />
            <el-input v-model="s.kind" placeholder="类型 (mock_seed / db_seed / ...)" size="small" />
          </div>
          <textarea
            :value="JSON.stringify(s.payload || {}, null, 2)"
            @input="e => s.payload = parseJson((e.target as HTMLTextAreaElement).value, {})"
            class="c-json"
            rows="2"
            placeholder="动作参数 (JSON)"
          />
        </div>
      </div>
      <button class="c-add" @click="addSetup">+ 添加前置</button>
    </div>

    <!-- PRD §6.4 teardown: 用例后置 (phase=teardown) -->
    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/></svg>
        <div>
          <h3>用例后置 (teardown)</h3>
          <p class="c-head-desc">用例结束后执行 — 清理数据 / 关闭 mock</p>
        </div>
      </div>
      <div v-if="!teardownList.length" class="c-empty">
        <p>还没有后置动作</p>
      </div>
      <div v-else class="action-list">
        <div v-for="(s, i) in teardownList" :key="i" class="action-row">
          <div class="action-row-head">
            <span class="phase-tag teardown">teardown</span>
            <button class="action-del" @click="teardownList.splice(i, 1)">×</button>
          </div>
          <div class="action-row-grid">
            <el-input v-model="s.name" placeholder="动作名 (例: cleanup-mock)" size="small" />
            <el-input v-model="s.kind" placeholder="类型" size="small" />
          </div>
          <textarea
            :value="JSON.stringify(s.payload || {}, null, 2)"
            @input="e => s.payload = parseJson((e.target as HTMLTextAreaElement).value, {})"
            class="c-json"
            rows="2"
            placeholder="动作参数 (JSON)"
          />
        </div>
      </div>
      <button class="c-add" @click="addTeardown">+ 添加后置</button>
    </div>

    <!-- 共享变量 -->
    <div class="c-card vars-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
        <div>
          <h3>共享变量 (vars) — 按 <code class="c-code">&lt;system&gt;.key</code> 命名空间分组</h3>
          <p class="c-head-desc">用例级共享 — 在 ④ 步骤编辑 中可用 <code class="c-code">${var.x}</code> 引用</p>
        </div>
      </div>
      <div v-if="!varsRows.length" class="c-empty">
        <p>还没有变量</p>
      </div>
      <div v-else class="c-ns-grid">
        <div v-for="(group, sys) in varsBySystem" :key="sys" class="c-ns-group">
          <div class="c-ns-head">
            <span class="c-ns-sys" :class="`s-${sys}`">{{ systemLabel(sys) }}</span>
            <span class="c-ns-count">{{ group.length }} keys</span>
          </div>
          <div v-for="(v, j) in group" :key="j" class="c-kv-row">
            <el-input
              :model-value="v.key"
              @update:model-value="(val: string) => v.key = val"
              placeholder="变量名"
              size="small"
            />
            <span class="c-kv-sep">=</span>
            <el-input
              :model-value="formatVarValue(v.value)"
              @update:model-value="(val: string) => v.value = parseVarValue(val)"
              placeholder="值 / 引用"
              size="small"
            />
            <button class="c-kv-del" @click="removeVar(v)">×</button>
          </div>
        </div>
      </div>
      <button class="c-add" @click="addVar">+ 添加变量</button>
    </div>

    <!-- 服务 -->
    <div class="c-card svc-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2"/><path d="M2 8h20M8 2v20"/></svg>
        <div>
          <h3>服务映射 (services) — 按系统分组</h3>
          <p class="c-head-desc">步骤的 <code class="c-code">service</code> 字段会从这里查找 baseUrl (例: <code class="c-code">fin.tidb-test</code>)</p>
        </div>
      </div>
      <div v-if="!serviceRows.length" class="c-empty">
        <p>还没有服务映射</p>
      </div>
      <div v-else class="c-ns-grid">
        <div v-for="(group, sys) in servicesBySystem" :key="sys" class="c-ns-group">
          <div class="c-ns-head">
            <span class="c-ns-sys" :class="`s-${sys}`">{{ systemLabel(sys) }}</span>
            <span class="c-ns-count">{{ group.length }} services</span>
          </div>
          <div v-for="(s, i) in group" :key="i" class="c-kv-row svc-row">
            <el-input
              :model-value="s.alias"
              @update:model-value="(val: string) => s.alias = val"
              placeholder="alias (例: tidb-test-service)"
              size="small"
            />
            <span class="svc-owner" :title="ownerLabel(s.alias)">{{ ownerLabel(s.alias) }}</span>
            <span class="c-kv-sep">→</span>
            <el-input
              :model-value="s.baseUrl"
              @update:model-value="(val: string) => s.baseUrl = val"
              placeholder="baseUrl"
              size="small"
              class="svc-url"
            />
            <button class="c-kv-del" @click="removeService(sys, i)">×</button>
          </div>
        </div>
      </div>
      <button class="c-add" @click="addService">+ 添加服务</button>
    </div>

    <!-- 用户认证(2026-08-25):场景级 users 快照 — 手动配置或凭证池导入 -->
    <UsersCard v-model="local.users" />

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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { ConfigView, RetryPolicyView } from '@/types/plate'
import { parseJson } from '../../utils/json'
import { deriveBase } from '@/utils/service-alias'
import { loadCatalogServiceNames } from '@/utils/catalog-services'
import UsersCard from './UsersCard.vue'

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

// ── 别名归属列(spec §1.4/§1.3):前缀派生只读标签,无手填 ──────────
const catalogNames = ref<Set<string>>(new Set())
onMounted(() => {
  loadCatalogServiceNames()
    .then((ns) => { catalogNames.value = new Set(ns) })
    .catch(() => { /* 目录不可达 → 全部显示未挂目录,不阻塞编辑 */ })
})
function ownerLabel(alias: string): string {
  return deriveBase(alias, catalogNames.value) ?? '未挂目录'
}

/**
 * 当前编辑态折叠成的 ConfigView(emit watch 发出的同一形状)。
 * 提取成单一函数供两处共用:emit 直接发;入向 watch 用它做
 * deep-equal 跳过 — 父级 v-model 回写的是我们刚 emit 的内容
 * (对象身份不同、内容相同),无条件重建 rows 会把用户刚 push 的
 * 空 row 引用吞掉并与 emit watch 互触成递归回灌
 * (Maximum recursive updates)。与 Canvas 的 sameSteps 同一模式。
 */
function emitShape(): ConfigView {
  const varsDict: Record<string, unknown> = {}
  for (const r of varsRows.value) {
    if (r.key) varsDict[r.key] = r.value
  }
  return {
    setup: [...setupList.value],
    teardown: [...teardownList.value],
    services: Object.fromEntries(
      serviceRows.value.filter(r => r.alias).map(r => [r.alias, r.baseUrl])
    ),
    users: local.users || {},
    timePolicy: local.timePolicy,
    retry: local.retry,
    vars: varsDict,
  }
}

watch(() => props.modelValue, (v) => {
  if (!v) return
  // 回声(自己 emit 的内容回写)→ 跳过;真外部变更(loadScenario)才重建
  if (JSON.stringify(emitShape()) === JSON.stringify(v)) return
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
  emit('update:modelValue', emitShape())
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
</script>

<style scoped>
/* 大部分样式来自 composer.css 共享层 (.c-page/.c-card/.c-kv-row/.c-ns-group/.c-empty/.c-add/.c-json/.c-inline-row) */
/* 确定性 2 列栅格: 时间|重试 / 前置|后置 / 变量+服务通栏。
 * auto-fit 在 1280px 内容宽下会排 3 列 → 6 卡出现 3+1+1+1 的行空洞,
 * 改为显式 2 列 (窄屏 1 列), 每行卡片成对对齐。 */
.c-page {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.vars-card, .svc-card, .users-card { grid-column: 1 / -1; }
@media (max-width: 960px) {
  .c-page { grid-template-columns: 1fr; }
}

/* time policy */
.time-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.time-tile {
  background: var(--c-bg-secondary);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s;
}
.time-tile:hover { border-color: var(--c-accent-soft-border); }
.time-tile.active {
  border-color: var(--c-accent);
  background: var(--c-accent-soft);
}
.time-name { font-weight: 600; font-size: 13px; font-family: var(--font-mono); color: var(--c-accent); }
.time-desc { font-size: 11px; color: var(--c-text-secondary); margin-top: 4px; line-height: 1.4; }

/* setup / teardown actions — 纵向堆叠: tag 头行 + 双字段栅格 + JSON 通栏,
 * 卡片窄至 320px 也不溢出 (原 5 列 grid 最小轨道 658px 在 2 列布局下必溢出) */
.action-list { display: flex; flex-direction: column; gap: 8px; }
.action-row {
  display: flex; flex-direction: column; gap: 8px;
  padding: 10px; background: var(--c-bg-secondary); border-radius: 6px;
}
.action-row-head {
  display: flex; align-items: center; justify-content: space-between;
}
.action-row-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px;
}
.action-row :deep(.el-input__wrapper) { background: var(--c-surface); }
.phase-tag {
  padding: 2px 6px; border-radius: 4px;
  font-family: var(--font-mono); font-size: 9px; font-weight: 700;
}
.phase-tag.setup { background: #d1fae5; color: #065f46; }
.phase-tag.teardown { background: #fce7f3; color: #9d174d; }
.action-del {
  width: 24px; height: 24px; background: transparent; border: none; border-radius: 4px;
  color: var(--c-text-tertiary); cursor: pointer; font-size: 16px;
  display: inline-flex; align-items: center; justify-content: center;
}
.action-del:hover { background: #fef2f2; color: #ef4444; }

/* vars / services 行 (c-kv-row 共享栅格) */
.c-kv-row { margin-bottom: 4px; }
.c-kv-row :deep(.el-input__wrapper) { background: var(--c-surface); }
/* svc-row 在共享 4 列栅格上扩一列归属标签: alias | 归属 | → | url | × */
.svc-row { grid-template-columns: minmax(140px, 220px) minmax(96px, 150px) 24px minmax(0, 1fr) 28px; }
.svc-owner {
  font-family: var(--font-mono); font-size: 11px; color: var(--c-text-tertiary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.svc-row .svc-url :deep(.el-input__wrapper) { font-family: var(--font-mono); }
@media (max-width: 720px) {
  /* 与共享层 .c-kv-sep 同款降级:窄屏收起归属列,退回 2 列行为 */
  .svc-row .svc-owner { display: none; }
}
.c-ns-grid { display: flex; flex-direction: column; gap: 12px; }
.c-ns-group .c-kv-row:last-child { margin-bottom: 0; }
</style>
