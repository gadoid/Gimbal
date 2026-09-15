<script setup lang="ts">
/** 方案工作台 · 运行配置区(spec §6):① 服务绑定(声明∪引用行 × 显式
 *  绑定口径)② 运行参数(钳位 + 总量预览)③ 预埋区(插件/日志订阅,
 *  待引擎支持)。纯展示组件:数据进 props、变更出事件;serviceRows/
 *  authOptions 派生与持久化归壳。绑定口径镜像 RunDialog.explicitBindingOf(D3)。 */
import { computed } from 'vue'
import type { ServiceBinding } from '@/api/scenario-composer'

const props = defineProps<{
  serviceBindings: Record<string, ServiceBinding>
  /** 声明 ∪ 引用并集行(spec D3,RunDialog ServiceRow 同款);壳从 draft 派生 */
  serviceRows: { service: string; declaredUrl: string | null }[]
  /** owner 凭证池 ∪ 场景内置 users 别名(壳调 listAuthSessions 映射) */
  authOptions: string[]
  /** 0-based 含端点;null = 全量 */
  stepTo: number | null
  nRuns: number
  parallel: number
  /** stepTo 钳位上限(0..stepCount) */
  stepCount: number
  /** 平台编排态步骤名(orchestration.steps[].name;缺名时选项不带名) */
  stepNames?: string[]
  /** 预埋自由文本(字符串/JSON;非字符串按空展示,不回写不丢库值) */
  plugins?: unknown
  logSub?: unknown
}>()

const emit = defineEmits<{
  'update:serviceBindings': [v: Record<string, ServiceBinding>]
  'update:stepTo': [v: number | null]
  'update:nRuns': [v: number]
  'update:parallel': [v: number]
  'update:plugins': [v: string]
  'update:logSub': [v: string]
}>()

// ── ① 服务绑定 ─────────────────────────────────────────────────────
function declaredUrlOf(svc: string): string | null {
  return props.serviceRows.find((r) => r.service === svc)?.declaredUrl ?? null
}

/** 行级显式绑定(D3,镜像 RunDialog.explicitBindingOf):与声明相同的 URL
 *  不算显式绑定(否则方案快照会钉死旧声明地址);未声明行任何非空 URL
 *  都是救燃绑定。非显式行返回 undefined(键整个移除)。 */
function explicitBindingOf(
  b: ServiceBinding | undefined,
  declared: string | null,
): ServiceBinding | undefined {
  const url = b?.url?.trim()
  const effectiveUrl = url && url !== declared ? url : undefined
  const authAlias = b?.authAlias || undefined
  if (!authAlias && !effectiveUrl) return undefined
  return {
    ...(authAlias ? { authAlias } : {}),
    ...(effectiveUrl ? { url: effectiveUrl } : {}),
  }
}

/** 行内变更 → 重装配整个绑定对象(受控口径:只显式条目落键,清空即移除)。 */
function setRowBinding(svc: string, patch: ServiceBinding) {
  const next: Record<string, ServiceBinding> = { ...props.serviceBindings }
  const eb = explicitBindingOf({ ...props.serviceBindings[svc], ...patch }, declaredUrlOf(svc))
  if (eb) next[svc] = eb
  else delete next[svc]
  emit('update:serviceBindings', next)
}

/** 降级(spec §9,口径镜像 RunDialog.degraded):存量 authAlias 非空且
 *  不在 authOptions(凭证被删)→ 行标红警示;select 为该 alias 渲染
 *  disabled option,保住值可见可存,用户重选即恢复。 */
function degraded(svc: string): boolean {
  const a = props.serviceBindings[svc]?.authAlias
  return !!a && !props.authOptions.includes(a)
}

// ── ② 运行参数(钳位与后端 schema 上限一致,防 422)─────────────────
/** 总量闸口径同 RunDialog.MAX_TOTAL_RUNS(后端 app/core/config.py
 *  MAX_RUNS_PER_EXECUTION);此处是预览告警,真正拦截在发起运行侧。 */
const MAX_TOTAL_RUNS = 200

function clampInt(v: number | null | undefined, min: number, max: number): number {
  const n = Math.floor(Number(v ?? min))
  return Math.min(max, Math.max(min, Number.isFinite(n) ? n : min))
}

const stepToModel = computed<number | null | undefined>({
  get: () => props.stepTo,
  set: (v) => emit('update:stepTo',
    v == null ? null : clampInt(v, 0, Math.max(0, props.stepCount))),
})
/** select 原生 option 值是字符串:空串哨兵 = null(全量),数字串 → 钳位索引 */
function onStepToChange(raw: string) {
  stepToModel.value = raw === '' ? null : Number(raw)
}
const nRunsModel = computed<number | undefined>({
  get: () => props.nRuns,
  set: (v) => emit('update:nRuns', clampInt(v, 1, 1000)),
})
const parallelModel = computed<number | undefined>({
  get: () => props.parallel,
  set: (v) => emit('update:parallel', clampInt(v, 1, 200)),
})

const totalRuns = computed(() =>
  clampInt(props.nRuns, 1, 1000) * clampInt(props.parallel, 1, 200))
const overLimit = computed(() => totalRuns.value > MAX_TOTAL_RUNS)

// ── ③ 预埋区(draft.plugins/logSub 字符串/JSON 自由文本)────────────
const pluginsText = computed({
  get: () => (typeof props.plugins === 'string' ? props.plugins : ''),
  set: (v: string) => emit('update:plugins', v),
})
const logSubText = computed({
  get: () => (typeof props.logSub === 'string' ? props.logSub : ''),
  set: (v: string) => emit('update:logSub', v),
})
</script>

<template>
  <div class="run-config">
    <!-- ① 用户与服务 -->
    <section class="wb-section">
      <header class="zone-head">
        <span class="zone-name">用户与服务</span>
        <span class="zone-spacer"></span>
        <span class="zone-hint">仅显式绑定入库;与声明相同的 URL 不记录</span>
      </header>
      <div v-if="serviceRows.length" class="bind-list">
        <div v-for="r in serviceRows" :key="r.service" class="bind-row"
          :class="{ 'is-degraded': degraded(r.service) }">
          <div class="bind-svc">
            <span class="svc-name">{{ r.service }}</span>
            <span v-if="r.declaredUrl" class="svc-declared" :title="r.declaredUrl">{{ r.declaredUrl }}</span>
            <span v-else class="svc-nodeclared">未声明引用</span>
            <span v-if="degraded(r.service)" class="svc-degraded" data-testid="binding-degraded-warn">凭证已删,请重选</span>
          </div>
          <!-- 原生 select/input(与数据区/注入区原生控件约定一致,测试直驱) -->
          <select class="bind-alias" data-testid="binding-alias"
            :value="serviceBindings[r.service]?.authAlias ?? ''"
            @change="setRowBinding(r.service, { authAlias: ($event.target as HTMLSelectElement).value })">
            <option value="">— 不绑定 —</option>
            <option v-for="a in authOptions" :key="a" :value="a">{{ a }}</option>
            <!-- 已删别名:disabled option 显示原别名 — 值不丢(可见可存),不可再选 -->
            <option v-if="degraded(r.service)" :value="serviceBindings[r.service]!.authAlias" disabled>
              {{ serviceBindings[r.service]!.authAlias }}(已删)
            </option>
          </select>
          <input class="bind-url" type="text" data-testid="binding-url"
            :value="serviceBindings[r.service]?.url ?? ''"
            :placeholder="r.declaredUrl ? `覆盖 URL(留空用声明)` : '覆盖 URL(救燃未声明引用)'"
            @input="setRowBinding(r.service, { url: ($event.target as HTMLInputElement).value })" />
        </div>
      </div>
      <p v-else class="hint">场景内暂无声明/引用的服务。</p>
    </section>

    <!-- ② 运行参数 -->
    <section class="wb-section">
      <header class="zone-head">
        <span class="zone-name">运行参数</span>
        <span class="zone-spacer"></span>
        <span class="zone-hint">总量预览:<span data-testid="total-preview" class="total-chip"
          :class="{ 'total-over': overLimit }">{{ nRuns }} × {{ parallel }} = {{ totalRuns }}</span></span>
      </header>
      <div class="param-row">
        <label>截断步骤(stepTo)</label>
        <!-- 原生 select(非 el-input-number):空值(null=全量)不能被
             spinner 误写 0 — element-plus 空 displayValue 点 ▼/▲ 会发射
             min(0),把「全量」静默改成「第1步后停止」;下拉里 0 只能显式选 -->
        <select class="bind-alias stepto-select" data-testid="param-stepto"
          :value="stepTo === null ? '' : String(stepTo)"
          @change="onStepToChange(($event.target as HTMLSelectElement).value)">
          <option value="">运行全部步骤</option>
          <option v-for="i in stepCount" :key="i" :value="String(i - 1)">
            第 {{ i }} 步后停止{{ stepNames?.[i - 1] ? ` · ${stepNames[i - 1]}` : '' }}
          </option>
        </select>
        <span class="param-hint">0-based 含端点(0..{{ stepCount }})</span>
      </div>
      <div class="param-row">
        <label>每行重复(nRuns)</label>
        <el-input-number v-model="nRunsModel" :min="1" :max="1000"
          size="small" data-testid="param-nruns" />
      </div>
      <div class="param-row">
        <label>并发度(parallel)</label>
        <el-input-number v-model="parallelModel" :min="1" :max="200"
          size="small" data-testid="param-parallel" />
      </div>
      <p v-if="overLimit" class="total-warn">超出单次执行总量上限 200</p>
    </section>

    <!-- ③ 预埋区(引擎接入前 no-op,可先配置) -->
    <section class="wb-section">
      <header class="zone-head">
        <span class="zone-name">预埋区</span>
      </header>
      <div class="reserve-row">
        <div class="reserve-head">
          <span>插件列表</span>
          <span class="tag-reserve">待引擎支持</span>
        </div>
        <el-input v-model="pluginsText" type="textarea" :rows="2"
          data-testid="reserve-plugins" placeholder="插件配置(字符串/JSON 自由文本,引擎接入后生效)" />
      </div>
      <div class="reserve-row">
        <div class="reserve-head">
          <span>日志订阅</span>
          <span class="tag-reserve">待引擎支持</span>
        </div>
        <el-input v-model="logSubText" type="textarea" :rows="2"
          data-testid="reserve-logsub" placeholder="日志订阅(字符串/JSON 自由文本,引擎接入后生效)" />
      </div>
    </section>
  </div>
</template>

<style scoped>
/* 分区卡片:对齐平台卡片体系(CaseDataSetsList .card / 编辑器 .meta) */
.wb-section {
  background: #fff; border: 1px solid var(--color-border-tertiary);
  border-radius: 8px; padding: 12px 16px;
  display: flex; flex-direction: column; gap: 10px;
}
/* zone-head 体系(CaseDataSetsList 同款):左竖线标题 + 弹性空位 + note */
.zone-head { display: flex; align-items: center; gap: 10px; }
.zone-name {
  font-size: 14px; font-weight: 700; color: var(--color-text-primary);
  padding-left: 10px; border-left: 3px solid var(--accent);
}
.zone-spacer { flex: 1; }
.zone-hint { font-size: 11px; color: var(--color-text-secondary); }
.run-config { display: flex; flex-direction: column; gap: 16px; }

/* ① 绑定行:列表行语言(分隔线 + 行距,atbl td 同款) */
.bind-list { display: flex; flex-direction: column; }
.bind-row {
  display: grid; grid-template-columns: minmax(120px, 1fr) 150px minmax(160px, 1.2fr);
  gap: 8px; align-items: center; padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
}
.bind-row:last-child { border-bottom: none; }
.bind-svc { min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.svc-name {
  font-weight: 600; font-size: 13px; color: var(--color-text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.svc-declared {
  font-family: var(--font-mono); font-size: 11px; color: var(--color-text-secondary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.svc-nodeclared { font-size: 11px; color: #b45309; }
/* 降级行(spec §9):凭证已删 — 底色微红 + 警示文案(与 RunDialog .is-degraded 同口径) */
.bind-row.is-degraded { background: #fef2f2; }
.bind-row.is-degraded .bind-alias { border-color: #fca5a5; }
.svc-degraded { font-size: 11px; color: #b91c1c; }
.bind-alias, .bind-url {
  border: 1px solid var(--color-border-secondary); border-radius: 4px;
  padding: 4px 8px; font-size: 13px; min-width: 0;
  background: #fff; color: var(--color-text-primary);
}
.bind-alias:focus, .bind-url:focus {
  border-color: var(--accent); outline: none;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
}

/* ② 参数行:行距节奏(8px 行高步进) */
.param-row { display: flex; align-items: center; gap: 10px; padding: 3px 0; }
/* stepTo 下拉:选项文案较长,给足最小宽防抖动 */
.stepto-select { min-width: 200px; }
.param-row label { width: 150px; flex: none; font-size: 13px; color: var(--color-text-primary); }
.param-hint { font-size: 11px; color: var(--color-text-secondary); }
/* 总量预览 chip:平台摘要 chip 形制(row-count/zone-count 同族,mono 数字) */
.total-chip {
  font-family: var(--font-mono); font-size: 11px; font-weight: 600;
  padding: 1px 6px; border-radius: 3px;
  color: var(--color-text-secondary); background: #f1f5f9;
}
.total-chip.total-over { color: #b91c1c; background: #fef2f2; }
.total-warn { margin: 0; color: #b91c1c; font-size: 12px; }

/* ③ 预埋区 */
.reserve-row { display: flex; flex-direction: column; gap: 4px; }
.reserve-head {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 600; color: var(--color-text-primary);
}
/* 「待引擎支持」:平台 muted tag(CaseDataSetsList .tag 同款形制) */
.tag-reserve {
  font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 3px;
  color: var(--color-text-secondary); background: #f1f5f9; white-space: nowrap;
}
.hint { color: var(--color-text-secondary); }
@media (max-width: 1280px) { .bind-row { grid-template-columns: 1fr; } }
</style>
