<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { ServiceBinding } from '@/api/scenario-composer'
import type {
  AccountComboRow, ComboEntry,
} from '@/api/accountCombos'
import { listAllAliases, type ServiceAliasRow } from '@/api/service-aliases'
import {
  aliasCandidates, degradedAlias, explicitBindingOf,
} from '@/utils/run-bindings'
import { confirmAction } from '@/utils/confirmAction'
import { Input } from '@/components/ui/input'
import EffectivePreviewDialog from '@/components/runs/EffectivePreviewDialog.vue'
import EntriesEditor from '@/components/account-combos/EntriesEditor.vue'

export interface AccountComboOption {
  id: number
  name: string
  scope: 'user' | 'project'
  scopeLabel: string
  isDefault: boolean
  entries: ComboEntry[]
}

interface ComboFormInput {
  name: string
  entries: ComboEntry[]
  scope: 'user' | 'project'
  projectId?: number
}

const props = defineProps<{
  serviceBindings: Record<string, ServiceBinding>
  serviceRows: { service: string; declaredUrl: string | null }[]
  stepIdentityRefs?: { service: string; aliases: string[] }[]
  stepTo: number | null
  nRuns: number
  parallel: number
  stepCount: number
  stepNames?: string[]
  environments?: { id: number; name: string; is_default: boolean }[]
  scenarioId?: string
  schemeId?: string
  schemeName?: string
  accountComboId?: number | null
  accountCombos: AccountComboOption[]
  comboPreselected?: boolean
  comboScopeLabel: string
  comboScope?: 'user' | 'project'
  comboProjectId?: number
  comboDisabled?: boolean
}>()

const emit = defineEmits<{
  'update:serviceBindings': [v: Record<string, ServiceBinding>]
  'update:stepTo': [v: number | null]
  'update:nRuns': [v: number]
  'update:parallel': [v: number]
  'update:accountComboId': [v: number | null]
  'create-combo': [v: ComboFormInput, done: (row: AccountComboRow | null) => void]
  'save-as-combo': [v: ComboFormInput, done: (row: AccountComboRow | null) => void]
}>()

const aliasRows = ref<ServiceAliasRow[]>([])
const aliasNames = computed(() => aliasRows.value.map((a) => a.aliasName))
onMounted(() => {
  try {
    listAllAliases()
      .then((rows) => { aliasRows.value = rows })
      .catch(() => { aliasRows.value = [] })
  } catch { aliasRows.value = [] }
})

const selectedCombo = computed(() => props.accountCombos.find(
  (c) => c.id === props.accountComboId) ?? null)
const comboMissing = computed(() =>
  props.accountComboId != null && selectedCombo.value == null)

function candidatesOf(svc: string): ServiceAliasRow[] {
  return aliasCandidates(svc, aliasRows.value)
}

function comboAliasOf(svc: string): string {
  return selectedCombo.value?.entries.find((e) => e.service === svc)?.alias ?? ''
}

function effectiveAliasOf(svc: string): string {
  return props.serviceBindings[svc]?.alias || comboAliasOf(svc)
}

function sourceOf(svc: string): '方案覆盖' | '组合' | '服务键' {
  if (props.serviceBindings[svc]?.alias) return '方案覆盖'
  if (comboAliasOf(svc)) return '组合'
  return '服务键'
}

function degraded(svc: string): boolean {
  return degradedAlias(effectiveAliasOf(svc), aliasNames.value)
}

function setRowBinding(svc: string, patch: ServiceBinding) {
  const next: Record<string, ServiceBinding> = { ...props.serviceBindings }
  const eb = explicitBindingOf({ ...props.serviceBindings[svc], ...patch })
  if (eb) next[svc] = eb
  else delete next[svc]
  emit('update:serviceBindings', next)
}

async function onComboChange(raw: string) {
  const next = raw === '' ? null : Number(raw)
  if (next === props.accountComboId) return
  if (next === null && props.accountComboId != null) {
    const overridden = props.serviceRows.filter(
      (r) => props.serviceBindings[r.service]?.alias).length
    const ok = await confirmAction(
      `解除组合后,${overridden} 个服务仍由方案绑定覆盖;步骤直引不受影响。其余服务将回落到服务键自身。`,
      '解除账户组合',
      { type: 'warning', confirmButtonText: '解除绑定', cancelButtonText: '取消' },
    )
    if (!ok) return
  }
  emit('update:accountComboId', next)
}

const comboFormMode = ref<'create' | 'save-as' | null>(null)
const comboFormName = ref('')
const comboFormEntries = ref<ComboEntry[]>([])
const comboSaving = ref(false)

function openComboForm(mode: 'create' | 'save-as') {
  comboFormMode.value = mode
  comboFormName.value = mode === 'save-as' && props.schemeName
    ? `${props.schemeName} 组合` : ''
  comboFormEntries.value = mode === 'save-as'
    ? Object.entries(props.serviceBindings)
      .filter(([, b]) => !!b.alias)
      .map(([service, b]) => ({ service, alias: b.alias ?? '' }))
    : []
}

function closeComboForm() {
  if (comboSaving.value) return
  comboFormMode.value = null
  comboFormName.value = ''
  comboFormEntries.value = []
}

function submitComboForm() {
  if (!comboFormMode.value || comboSaving.value) return
  const name = comboFormName.value.trim()
  const entries = comboFormEntries.value.filter(
    (e) => e.service.trim() && e.alias.trim())
  if (!name) return
  comboSaving.value = true
  const done = (row: AccountComboRow | null) => {
    comboSaving.value = false
    if (!row) return
    comboFormMode.value = null
    comboFormName.value = ''
    comboFormEntries.value = []
    emit('update:accountComboId', row.id)
  }
  const scope = props.comboScope ?? 'user'
  const input: ComboFormInput = {
    name, entries, scope,
    ...(scope === 'project' && props.comboProjectId != null
      ? { projectId: props.comboProjectId } : {}),
  }
  if (comboFormMode.value === 'create') emit('create-combo', input, done)
  else emit('save-as-combo', input, done)
}

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
function onStepToChange(raw: string) {
  stepToModel.value = raw === '' ? null : Number(raw)
}
const nRunsModel = computed<number | undefined>({
  get: () => props.nRuns,
  set: (v) => emit('update:nRuns', clampInt(v, 1, 64)),
})
const parallelModel = computed<number | undefined>({
  get: () => props.parallel,
  set: (v) => emit('update:parallel', clampInt(v, 1, 64)),
})
const totalRuns = computed(() =>
  clampInt(props.nRuns, 1, 64) * clampInt(props.parallel, 1, 64))
const overLimit = computed(() => totalRuns.value > MAX_TOTAL_RUNS)

const previewOpen = ref(false)
const previewBindings = computed<Record<string, { alias: string }>>(() => {
  const out: Record<string, { alias: string }> = {}
  for (const [svc, b] of Object.entries(props.serviceBindings)) {
    if (b?.alias) out[svc] = { alias: b.alias }
  }
  return out
})
const previewEnvNames = computed<Record<number, string>>(() =>
  Object.fromEntries((props.environments ?? []).map((e) => [e.id, e.name])))
</script>

<template>
  <div class="run-config">
    <section class="wb-section">
      <header class="zone-head">
        <span class="zone-name">用户与服务</span>
        <span class="zone-spacer"></span>
        <span class="zone-hint">组合垫底 · 方案覆盖 · 步骤直引优先</span>
      </header>

      <div class="combo-panel" :class="{ 'is-preselected': comboPreselected }">
        <label class="combo-label" for="scheme-account-combo">账户组合</label>
        <select id="scheme-account-combo" class="bind-alias combo-select"
          data-testid="account-combo-select"
          :value="accountComboId ?? ''" :disabled="comboDisabled"
          @change="onComboChange(($event.target as HTMLSelectElement).value)">
          <option value="">不绑定</option>
          <option v-for="c in accountCombos" :key="c.id" :value="c.id">
            {{ c.name }} · {{ c.scopeLabel }}{{ c.isDefault ? ' · 默认' : '' }}
          </option>
          <option v-if="comboMissing" :value="accountComboId ?? ''">
            已绑定组合不可用 #{{ accountComboId }}
          </option>
        </select>
        <button type="button" class="combo-action" data-testid="scheme-new-combo"
          :disabled="comboDisabled || comboSaving" @click="openComboForm('create')">新建组合</button>
        <button type="button" class="combo-action" data-testid="scheme-save-as-combo"
          :disabled="comboDisabled || comboSaving" @click="openComboForm('save-as')">存为组合</button>
        <span v-if="comboPreselected" class="combo-badge" data-testid="combo-preselected">默认预选</span>
        <span v-else-if="comboMissing" class="combo-badge is-warn">组合缺失</span>
        <p class="combo-hint">
          {{ comboDisabled ? '公共场景不绑定账户组合。' : `范围:${comboScopeLabel};选择随方案「保存」生效。` }}
        </p>
      </div>

      <div v-if="comboFormMode" class="combo-form" data-testid="scheme-combo-form">
        <strong>{{ comboFormMode === 'create' ? '新建账户组合' : '将方案绑定存为组合' }}</strong>
        <label>
          <span>名称</span>
          <input v-model="comboFormName" maxlength="64" data-testid="scheme-combo-name"
            :placeholder="comboFormMode === 'save-as' ? '如:测试环境组合' : '如:测试组合'" />
        </label>
        <label>
          <span>范围(按场景硬同区)</span>
          <select class="bind-alias" data-testid="scheme-combo-scope"
            :value="comboScope ?? 'user'" disabled>
            <option value="user">个人</option>
            <option value="project">{{ comboScope === 'project' ? comboScopeLabel : '项目' }}</option>
          </select>
        </label>
        <EntriesEditor v-model="comboFormEntries" :alias-names="aliasNames" />
        <div v-if="comboFormMode === 'save-as'" class="direct-refs"
          data-testid="scheme-step-direct-refs">
          <strong>步骤直引服务</strong>
          <span v-if="!stepIdentityRefs?.length" class="combo-hint">无</span>
          <ul v-else>
            <li v-for="row in stepIdentityRefs" :key="row.service || '__template__'">
              {{ row.service || '模板引用' }} → {{ row.aliases.join('、') }}
            </li>
          </ul>
          <p class="combo-hint">
            只快照方案 serviceBindings;步骤级直引不会自动收进组合,可在此手工补入。
          </p>
        </div>
        <div class="combo-form-actions">
          <button type="button" class="combo-action" data-testid="scheme-combo-cancel"
            :disabled="comboSaving" @click="closeComboForm">取消</button>
          <button type="button" class="combo-action is-primary" data-testid="scheme-combo-save"
            :disabled="comboSaving || !comboFormName.trim()" @click="submitComboForm">
            {{ comboSaving ? '创建中…' : '创建并绑定' }}
          </button>
        </div>
      </div>

      <div v-if="serviceRows.length" class="bind-list">
        <div v-for="r in serviceRows" :key="r.service" class="bind-row"
          :class="{ 'is-degraded': degraded(r.service) }">
          <div class="bind-svc">
            <span class="svc-name">{{ r.service }}</span>
            <span v-if="r.declaredUrl" class="svc-declared" :title="r.declaredUrl">{{ r.declaredUrl }}</span>
            <span v-if="degraded(r.service)" class="svc-degraded" data-testid="binding-degraded-warn">别名已删,请重选</span>
          </div>
          <select v-if="candidatesOf(r.service).length || degraded(r.service)"
            class="bind-alias" data-testid="binding-alias"
            :value="effectiveAliasOf(r.service)"
            @change="setRowBinding(r.service, { alias: ($event.target as HTMLSelectElement).value })">
            <option value="">— 继承组合 / 用服务键 —</option>
            <option v-for="c in candidatesOf(r.service)" :key="c.aliasName" :value="c.aliasName">
              {{ c.slot ? `${c.aliasName}(条目 ${c.slot})` : c.aliasName }}
            </option>
            <option v-if="degraded(r.service)" :value="effectiveAliasOf(r.service)" disabled>
              {{ effectiveAliasOf(r.service) }}(已删)
            </option>
          </select>
          <span v-else class="svc-noalias">该服务暂无同基别名 — 用服务键本身</span>
          <span class="binding-source" :class="`source-${sourceOf(r.service)}`"
            :data-testid="`binding-source-${r.service}`">{{ sourceOf(r.service) }}</span>
        </div>
      </div>
      <p v-else class="hint">场景内暂无声明/引用的服务。</p>
    </section>

    <section class="wb-section">
      <header class="zone-head">
        <span class="zone-name">运行参数</span>
        <span class="zone-spacer"></span>
        <span class="zone-hint">总量预览:<span data-testid="total-preview" class="total-chip"
          :class="{ 'total-over': overLimit }">{{ nRuns }} × {{ parallel }} = {{ totalRuns }}</span></span>
        <button v-if="scenarioId" type="button" class="preview-btn"
          data-testid="scheme-preview-open" @click="previewOpen = true">生效预览</button>
      </header>
      <div class="param-row">
        <label>截断步骤(stepTo)</label>
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
        <Input v-model="nRunsModel" type="number" min="1" max="1000" class="h-8 w-[6.875rem]"
          size="small" data-testid="param-nruns" />
      </div>
      <div class="param-row">
        <label>并发度(parallel)</label>
        <Input v-model="parallelModel" type="number" min="1" max="64" class="h-8 w-[6.875rem]"
          size="small" data-testid="param-parallel" />
      </div>
      <p v-if="overLimit" class="total-warn">超出单次执行总量上限 200</p>
    </section>

    <EffectivePreviewDialog
      :open="previewOpen"
      :scenario-id="scenarioId"
      :scheme-id="schemeId"
      :service-bindings="previewBindings"
      :env-names="previewEnvNames"
      @close="previewOpen = false"
    />
  </div>
</template>

<style scoped>
.wb-section {
  background: var(--c-surface); border: 1px solid var(--color-border-tertiary);
  border-radius: 0.5rem; padding: 0.75rem 1rem;
  display: flex; flex-direction: column; gap: 0.625rem;
}
.zone-head { display: flex; align-items: center; gap: 0.625rem; }
.zone-name {
  font-size: 0.875rem; font-weight: 700; color: var(--color-text-primary);
  padding-left: 0.625rem; border-left: 3px solid var(--accent);
}
.zone-spacer { flex: 1; }
.zone-hint { font-size: 0.6875rem; color: var(--color-text-secondary); }
.run-config { display: flex; flex-direction: column; gap: 1rem; }
.preview-btn {
  border: 1px solid var(--color-border-secondary); border-radius: 0.375rem; background: var(--c-surface);
  padding: 0.125rem 0.75rem; font-size: 0.75rem; cursor: pointer; color: var(--color-text-primary);
}
.preview-btn:hover { border-color: var(--accent); color: var(--accent); }

.combo-panel {
  display: flex; align-items: center; flex-wrap: wrap; gap: 0.5rem;
  padding: 0.625rem 0.75rem; border: 1px solid var(--color-border-tertiary);
  border-radius: 0.5rem; background: var(--surface-raised);
}
.combo-panel.is-preselected { border-style: dashed; border-color: var(--accent); }
.combo-label { font-size: 0.75rem; font-weight: 600; color: var(--color-text-primary); }
.combo-select { min-width: 15rem; flex: 1; max-width: 25rem; }
.combo-action {
  border: 1px solid var(--color-border-secondary); border-radius: 0.375rem;
  background: var(--c-surface); color: var(--color-text-primary);
  padding: 0.25rem 0.625rem; font-size: 0.75rem; cursor: pointer;
}
.combo-action:hover { border-color: var(--accent); color: var(--accent); }
.combo-action:disabled { opacity: 0.5; cursor: not-allowed; }
.combo-action.is-primary { background: var(--accent); color: white; border-color: var(--accent); }
.combo-badge {
  font-size: 0.6875rem; color: var(--accent); background: var(--accent-soft);
  border-radius: 0.25rem; padding: 0.0625rem 0.375rem;
}
.combo-badge.is-warn { color: var(--sl-warn); background: var(--soft-warn-bg); }
.combo-hint { flex-basis: 100%; margin: 0; font-size: 0.6875rem; color: var(--color-text-secondary); }
.combo-form {
  display: flex; flex-direction: column; gap: 0.5rem; padding: 0.75rem;
  border: 1px solid var(--color-border-secondary); border-radius: 0.5rem;
  background: var(--c-surface);
}
.combo-form > strong { font-size: 0.8125rem; color: var(--color-text-primary); }
.combo-form > label { display: grid; gap: 0.25rem; max-width: 26rem; }
.combo-form > label span { font-size: 0.6875rem; color: var(--color-text-secondary); }
.combo-form > label input {
  padding: 0.3125rem 0.5rem; font-size: 0.8125rem;
  border: 1px solid var(--color-border-secondary); border-radius: 0.375rem;
  background: var(--c-surface); color: var(--color-text-primary);
}
.combo-form > label select { width: 15rem; }
.combo-form > label select:disabled { opacity: 0.7; }
.direct-refs {
  display: flex; flex-direction: column; gap: 0.25rem;
  padding: 0.5rem 0.625rem; border-radius: 0.375rem;
  background: var(--soft-neutral-bg); font-size: 0.75rem;
}
.direct-refs ul { margin: 0; padding-left: 1.25rem; }
.combo-form-actions { display: flex; justify-content: flex-end; gap: 0.5rem; }

.bind-list { display: flex; flex-direction: column; }
.bind-row {
  display: grid; grid-template-columns: minmax(7.5rem, 1fr) minmax(10rem, 13.75rem) 4.5rem;
  gap: 0.5rem; align-items: center; padding: 0.5rem 0;
  border-bottom: 1px solid var(--soft-neutral-bg);
}
.bind-row:last-child { border-bottom: none; }
.bind-svc { min-width: 0; display: flex; flex-direction: column; gap: 0.0625rem; }
.svc-name {
  font-weight: 600; font-size: 0.8125rem; color: var(--color-text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.svc-declared {
  font-family: var(--font-mono); font-size: 0.6875rem; color: var(--color-text-secondary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.svc-degraded { font-size: 0.6875rem; color: var(--sl-warn); }
.svc-noalias { font-size: 0.6875rem; color: var(--color-text-secondary); }
.bind-row.is-degraded { background: var(--soft-warn-bg); }
.bind-row.is-degraded .bind-alias { border-color: var(--sl-warn); }
.bind-alias {
  border: 1px solid var(--color-border-secondary); border-radius: 0.25rem;
  padding: 0.25rem 0.5rem; font-size: 0.8125rem; min-width: 0;
  background: var(--c-surface); color: var(--color-text-primary);
}
.bind-alias:focus { border-color: var(--accent); outline: none; box-shadow: 0 0 0 2px var(--accent-soft); }
.binding-source { font-size: 0.6875rem; text-align: center; color: var(--color-text-secondary); }
.binding-source.source-组合 { color: var(--accent); }
.binding-source.source-方案覆盖 { color: var(--sl-success); }

.param-row { display: flex; align-items: center; gap: 0.625rem; padding: 0.1875rem 0; }
.stepto-select { min-width: 12.5rem; }
.param-row label { width: 9.375rem; flex: none; font-size: 0.8125rem; color: var(--color-text-primary); }
.param-hint { font-size: 0.6875rem; color: var(--color-text-secondary); }
.total-chip {
  font-family: var(--font-mono); font-size: 0.6875rem; font-weight: 600;
  padding: 0.0625rem 0.375rem; border-radius: 0.1875rem;
  color: var(--color-text-secondary); background: var(--soft-neutral-bg);
}
.total-chip.total-over { color: var(--sl-warn); background: var(--soft-warn-bg); }
.total-warn { margin: 0; color: var(--sl-warn); font-size: 0.75rem; }
.hint { color: var(--color-text-secondary); }
@media (max-width: 1280px) { .bind-row { grid-template-columns: 1fr; } }
</style>
