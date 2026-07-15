<!-- CaseConfigReadonly.vue — wireframe 1/? 案例详情只读视图.
     4 tab card-stack + 默认折叠 step-card + L3 预设已应用 + L1 字段👁 (内存).
     Spec-1 不支持编辑：所有 entry 都是只读视图；编辑能力留给 Spec-2. -->
<template>
  <section v-if="payload" class="config-view">
    <!-- 顶部固定栏（深色） -->
    <header class="topbar">
      <span class="status-dot" aria-hidden="true" />
      <span class="brand">platform · connected</span>
      <span class="scenario-label">SCENARIO ID</span>
      <code class="scenario-id">{{ scenarioId }}</code>
      <button
        v-if="canRename"
        class="topbar-btn topbar-rename"
        type="button"
        title="重命名 scenarioId"
        @click="openRename"
      >✎ 重命名</button>
      <span class="spacer" />
      <button
        v-if="!editStore.isEditMode"
        class="topbar-btn"
        type="button"
        @click="enterEditMode"
      >✏️ 编辑</button>
      <template v-else>
        <span :class="['dirty-tag', { visible: editStore.dirty }]">
          {{ editStore.dirty ? '● 未保存' : '✓ 已保存' }}
        </span>
        <button
          class="topbar-btn"
          type="button"
          :disabled="!editStore.dirty || editStore.saving"
          @click="saveEdit"
        >保存</button>
        <button class="topbar-btn" type="button" @click="cancelEdit">取消</button>
      </template>
      <label class="show-hidden-toggle">
        <input v-model="hideStore.showHidden" type="checkbox" />
        <span>👁 显示隐藏</span>
      </label>
      <button class="topbar-btn" type="button" @click="yamlOpen = true">
        只读 YAML
      </button>
      <button class="topbar-btn" type="button" @click="helpOpen = true">
        帮助
      </button>
    </header>

    <!-- Tab 行 -->
    <nav class="tab-row" role="tablist">
      <button
        v-for="tab in TABS"
        :key="tab.key"
        :class="['tab', `tab-${tab.color}`, { active: activeTab === tab.key }]"
        :aria-selected="activeTab === tab.key"
        role="tab"
        type="button"
        @click="activeTab = tab.key"
      >
        {{ tab.icon }} {{ String(tab.idx).padStart(2, '0') }} · {{ tab.label }}
      </button>
      <span class="spacer" />
      <span class="tab-summary">{{ summaryText }}</span>
    </nav>

    <!-- Card stack：单个 tab-pane -->
    <article class="card">
      <!-- ── meta ──────────────────────────────────────────── -->
      <div v-if="activeTab === 'meta'" class="tab-panel">
        <PanelHeader icon="📝" title="01 · META" subtitle="用例元数据" />
        <EditableMetaPanel
          v-if="editStore.isEditMode"
          :case-id="caseId"
          :meta="meta"
          @update="(m) => editStore.patchCurrent((p) => { p.meta = { ...(p.meta || {}), ...m } })"
        />
        <div v-else class="field-grid">
          <FieldRow label="name" :value="meta.name" />
          <FieldRow label="description" :value="meta.description || '—'" />
          <FieldRow label="module" :value="meta.module" />
          <FieldRow label="priority" :value="String(meta.priority ?? '—')" />
          <FieldRow label="author" :value="meta.author || '—'" />
          <FieldRow label="owner" :value="meta.owner || '—'" />
          <FieldRow label="version" :value="meta.version || '—'" />
          <FieldRow label="createTime" :value="meta.createTime || '—'" />
          <FieldRow
            label="tags"
            :value="(meta.tags ?? []).join(', ') || '—'"
          />
          <FieldRow
            v-if="metaPath('requirementRef')"
            :hidden="hideStore.isHidden(metaPath('requirementRef')!)"
            label="requirementRef"
            :value="(meta.requirementRef ?? []).join(', ') || '[]'"
            :eye="true"
            @toggle-eye="toggleHide(metaPath('requirementRef')!)"
          />
        </div>
      </div>

      <!-- ── config ────────────────────────────────────────── -->
      <div v-else-if="activeTab === 'config'" class="tab-panel">
        <PanelHeader icon="⚙️" title="02 · CONFIG" subtitle="服务 / 用户 / 变量 / 重试" />

        <EditableConfigPanel
          v-if="editStore.isEditMode"
          :config="(editStore.current?.config as Record<string, unknown>) || {}"
          :auths="authsList"
          @update="(c) => editStore.patchCurrent((p) => { p.config = { ...(p.config || {}), services: c.services, users: c.users, vars: c.vars } })"
        />

        <!-- Vars editor (Spec-2-5) — readonly outside edit mode -->
        <VarsEditor
          v-else
          class="vars-block"
          :model-value="configVars"
          :readonly="true"
          :saving="varsSaving"
          @update:model-value="saveVars"
          @cancel="varsCancel"
        />

        <!-- Other config groups (services / users / retry) -->
        <section v-for="group in otherConfigGroups" :key="group.label" class="config-group">
          <h4 class="group-title">{{ group.label }}</h4>
          <div class="field-grid">
            <FieldRow
              v-for="row in group.rows"
              :key="row.label"
              :label="row.label"
              :value="row.value"
            />
          </div>
          <div v-if="group.tables" class="kv-tables">
            <div v-for="tbl in group.tables" :key="tbl.label" class="kv-table">
              <div class="kv-table-title">{{ tbl.label }}</div>
              <div v-for="(v, k) in tbl.data" :key="k" class="kv-row">
                <code class="kv-key">{{ k }}</code>
                <code class="kv-val mono">{{ v }}</code>
              </div>
              <div v-if="Object.keys(tbl.data).length === 0" class="kv-empty">
                （空）
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- ── resource ──────────────────────────────────────── -->
      <div v-else-if="activeTab === 'resource'" class="tab-panel">
        <PanelHeader icon="🗂️" title="03 · RESOURCE" subtitle="附加资源（db / mock / file / variable）" />
        <EditableResourcePanel
          v-if="editStore.isEditMode"
          :resource="(editStore.current?.resource as Record<string, unknown>) || {}"
          @update="(r) => editStore.patchCurrent((p) => { p.resource = r })"
        />
        <div v-else-if="resourceEntries.length === 0" class="empty-state">
          当前用例未声明额外资源
        </div>
        <div v-else class="resource-list">
          <div v-for="entry in resourceEntries" :key="entry.key" class="resource-row">
            <code class="resource-key">{{ entry.key }}</code>
            <span class="resource-kind">{{ entry.kind }}</span>
            <code class="resource-val mono">{{ entry.summary }}</code>
          </div>
        </div>
      </div>

      <!-- ── steps ─────────────────────────────────────────── -->
      <div v-else class="tab-panel">
        <PanelHeader
          icon="📋"
          title="04 · STEPS"
          subtitle="用例步骤（默认折叠，点 step 行展开）"
        />

        <div v-if="l3Hint" class="l3-banner">
          <b>L3 预设已应用：</b>{{ l3Hint }}
          <router-link to="#" class="banner-link" @click.prevent>
            顶部「👁 显示隐藏」切换可见
          </router-link>
        </div>

        <div class="step-list">
          <template v-if="editStore.isEditMode && editStore.current">
            <draggable
              :model-value="(editStore.current.steps as Step[]) || []"
              @update:model-value="(v: Step[]) => editStore.patchCurrent((p) => { p.steps = v })"
              :animation="150"
              item-key="__id"
              handle=".estep-header"
            >
              <template #item="{ element, index }">
                <EditableStepCard
                  :step="element"
                  :index="index + 1"
                  :auths="authsList"
                  @update="(s) => replaceStep(index, s)"
                  @remove="removeStep(index)"
                />
              </template>
            </draggable>
            <el-button type="primary" plain @click="appendStep" class="add-step-btn">
              + 新增步骤
            </el-button>
          </template>
          <template v-else>
            <StepCard
              v-for="(step, idx) in steps"
              :key="idx"
              :step="step"
              :index="idx + 1"
              @persist-hidden="onStepToggleHidden"
            />
          </template>
        </div>
      </div>
    </article>
  </section>

  <section v-else-if="errorMsg" class="state error-state">
    <p>{{ errorMsg }}</p>
    <el-button @click="reload">重试</el-button>
  </section>

  <section v-else class="state loading-state">
    <el-skeleton :rows="6" animated />
  </section>

  <!-- Modals (Spec-2-9 + 2-10) -->
  <YamlPreviewModal v-model="yamlOpen" :case-id="caseId" />
  <HelpModal v-model="helpOpen" />
  <ScenarioRenameDialog
    v-model="renameOpen"
    :current-id="scenarioId"
    :submitting="renameSubmitting"
    @submit="onRenameSubmit"
  />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useCasesStore } from '@/stores/cases'
import { useHideStore } from '@/stores/hide'
import { useEditModeStore } from '@/stores/editMode'
import { useAuthSessionsStore } from '@/stores/auth_sessions'
import { useAuthStore } from '@/stores/auth'
import * as casesApi from '@/api/cases'
import type { CaseDetailOut } from '@/api/cases'
import FieldRow from '@/components/FieldRow.vue'
import PanelHeader from '@/components/PanelHeader.vue'
import StepCard from '@/components/StepCard.vue'
import VarsEditor from '@/components/VarsEditor.vue'
import EditableMetaPanel from '@/components/EditableMetaPanel.vue'
import EditableConfigPanel from '@/components/EditableConfigPanel.vue'
import EditableResourcePanel from '@/components/EditableResourcePanel.vue'
import EditableStepCard from '@/components/EditableStepCard.vue'
import YamlPreviewModal from '@/components/YamlPreviewModal.vue'
import HelpModal from '@/components/HelpModal.vue'
import ScenarioRenameDialog from '@/components/ScenarioRenameDialog.vue'
import draggable from 'vuedraggable'
import { L3_DEFAULTS } from '@/stores/hide'

type TabKey = 'meta' | 'config' | 'resource' | 'steps'

interface TabSpec {
  key: TabKey
  idx: number
  label: string
  icon: string
  color: 'purple' | 'green' | 'yellow' | 'blue'
}

const TABS: readonly TabSpec[] = [
  { key: 'meta',     idx: 1, label: 'meta',     icon: '📝', color: 'purple' },
  { key: 'config',   idx: 2, label: 'config',   icon: '⚙️', color: 'green'  },
  { key: 'resource', idx: 3, label: 'resource', icon: '🗂️', color: 'yellow' },
  { key: 'steps',    idx: 4, label: 'steps',    icon: '📋', color: 'blue'   },
]

const route = useRoute()
const router = useRouter()
const casesStore = useCasesStore()
const hideStore = useHideStore()
const editStore = useEditModeStore()
const authsStore = useAuthSessionsStore()
const authStore = useAuthStore()
const authsList = computed(() => authsStore.list)
const yamlOpen = ref(false)
const helpOpen = ref(false)
const renameOpen = ref(false)
const renameSubmitting = ref(false)

const payload = ref<CaseDetailOut | null>(null)
const errorMsg = ref<string>('')
const activeTab = ref<TabKey>('meta')

const scenarioId = computed(() => payload.value?.summary.case_id ?? '')

const meta = computed(() => payload.value?.payload.meta ?? {})
const config = computed(() => payload.value?.payload.config ?? {})
const steps = computed(() => payload.value?.payload.steps ?? [])

const summaryText = computed(() => {
  if (!payload.value) return ''
  const n = steps.value.length
  return `${n} 步 · ${hideStore.hiddenCount} 字段已批量隐藏 · ~${Math.max(0, 100 - hideStore.hiddenCount * 5)}% 噪声被屏蔽`
})

const l3Hint = computed(() => {
  const hits = ['sec-ch-ua-platform', 'sec-ch-ua', 'sec-ch-ua-mobile', 'Sec-Fetch-Site', 'Sec-Fetch-Mode', 'Sec-Fetch-Dest']
  const present = hits.filter((h) =>
    steps.value.some((s: any) => s?.api?.headers && h in s.api.headers),
  )
  if (present.length === 0) return ''
  return `本用例隐藏了 ${present.length} 个浏览器嗅探 header（${present.slice(0, 3).join(', ')}…）。`
})

// ── meta tab helpers ─────────────────────────────────────
function metaPath(field: string): string | null {
  return `meta.${field}`
}

function toggleHide(path: string) {
  hideStore.toggleL1(path)
  scheduleSave()
}

function onStepToggleHidden() {
  // StepCard already toggled the store; we just persist.
  scheduleSave()
}

// ── config tab groups ────────────────────────────────────
interface Step {
  description?: string
  api?: {
    service?: string
    method?: string
    path?: string
    headers?: Record<string, string>
  }
  request?: { body?: unknown }
}

interface ConfigRow { label: string; value: string }
interface ConfigTable { label: string; data: Record<string, string> }
interface ConfigGroup {
  label: string
  rows: ConfigRow[]
  tables?: ConfigTable[]
}

// ── config tab groups ────────────────────────────────────
// `vars` is rendered via VarsEditor (Spec-2-5); other groups are
// shown as generic KV tables / rows below it.
const configVars = computed<Record<string, unknown>>(() => config.value?.vars ?? {})
const varsSaving = ref(false)

const otherConfigGroups = computed<ConfigGroup[]>(() => {
  const c = config.value
  return [
    {
      label: 'services（服务地址）',
      tables: [{ label: 'config.services', data: stringifyDict(c.services ?? {}) }],
    },
    {
      label: 'users（认证用户）',
      tables: [{ label: 'config.users', data: stringifyDict(c.users ?? {}) }],
    },
    {
      label: 'timePolicy / retry / setup / teardown',
      rows: [
        { label: 'timePolicy', value: JSON.stringify(c.timePolicy ?? null) },
        { label: 'retry', value: JSON.stringify(c.retry ?? null) },
        { label: 'setup', value: `${(c.setup ?? []).length} 项` },
        { label: 'teardown', value: `${(c.teardown ?? []).length} 项` },
      ],
    },
  ]
})

async function saveVars(nextVars: Record<string, unknown>) {
  varsSaving.value = true
  try {
    // ``payload.value`` is ``CaseDetailOut = { summary, payload }``,
    // so spreading it directly mixes summary fields into the inner
    // payload, which the backend's CasePayload schema rejects (422).
    // Use ``payload.value.payload`` (the inner CasePayload) as the
    // base, then overlay the updated config.vars only.
    const inner =
      (payload.value?.payload as Record<string, unknown> | null) ??
      ({} as Record<string, unknown>)
    const currentCfg =
      (inner.config as Record<string, unknown> | undefined) ?? {}
    const newPayload = {
      ...inner,
      config: { ...currentCfg, vars: nextVars },
    }
    await casesApi.patch(caseId.value, { payload: newPayload })
    ElMessage.success('vars 已保存')
    // refresh detail
    await casesStore.fetchOne(caseId.value)
    payload.value =
      (casesStore.detail as unknown as CaseDetailOut | null) ?? payload.value
  } catch {
    ElMessage.error('vars 保存失败')
  } finally {
    varsSaving.value = false
  }
}

function varsCancel() {
  // Force re-fetch to revert local edits
  casesStore.fetchOne(caseId.value)
}

function stringifyDict(obj: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [k, v] of Object.entries(obj)) {
    out[k] = typeof v === 'string' ? v : JSON.stringify(v)
  }
  return out
}

// ── resource tab helpers ─────────────────────────────────
const resourceEntries = computed(() => {
  const r = payload.value?.payload.resource ?? {}
  return Object.entries(r).map(([key, value]) => {
    const v = value as Record<string, unknown> | null
    return {
      key,
      kind: v?.kind ?? 'unknown',
      summary: v ? JSON.stringify(v).slice(0, 120) : 'null',
    }
  })
})

// ── data fetching ────────────────────────────────────────
const caseId = computed(() => decodeURIComponent(String(route.params.caseId ?? '')))

// Hidden-field profile persistence (Spec-2-6 §4.3 C2):
//   1. on mount: load profile from /hidden, replace L3_DEFAULTS with saved paths
//   2. on L1 toggle: debounce-save the new paths back
//   3. on unmount: reset hide store to L3_DEFAULTS (don't pollute next case)
let saveHandle: ReturnType<typeof setTimeout> | null = null

async function loadHiddenProfile() {
  try {
    const profile = await casesApi.getHidden(caseId.value)
    const paths = new Set<string>(profile.hidden_paths)
    // Merge L3 defaults that aren't in the user's profile
    for (const d of L3_DEFAULTS) paths.add(d)
    hideStore.setPaths(paths)
  } catch {
    // Silent: keep L3_DEFAULTS on load failure
  }
}

function scheduleSave() {
  if (saveHandle !== null) clearTimeout(saveHandle)
  saveHandle = setTimeout(async () => {
    saveHandle = null
    const all = hideStore.snapshot()
    // Strip L3_DEFAULTS — they're implicit per-case, not user choices
    const userPaths = all.filter((p) => !L3_DEFAULTS.includes(p))
    try {
      await casesApi.putHidden(caseId.value, { hidden_paths: userPaths })
    } catch {
      ElMessage.error('保存隐藏字段失败')
    }
  }, 500)
}

async function load() {
  if (!caseId.value) {
    errorMsg.value = '无效的用例 ID'
    return
  }
  // Reset tab + edit state on every (re)load.  Both are session-scoped
  // Pinia refs, so leaving them set between cases made the new case
  // land on the previous tab and/or render the editable panels (config /
  // resource / steps) before the user clicked 编辑.
  activeTab.value = 'meta'
  editStore.cancelEdit()
  errorMsg.value = ''
  try {
    payload.value = await casesStore.fetchOne(caseId.value)
    await loadHiddenProfile()
  } catch {
    errorMsg.value = casesStore.lastError || '加载用例失败'
    ElMessage.error(errorMsg.value)
  }
}

function reload() {
  hideStore.reset()
  load()
}

// ── edit mode handlers (Spec-2-4) ───────────────────────────
function enterEditMode() {
  if (!payload.value) return
  editStore.enterEdit(payload.value.payload as Record<string, unknown>)
}

async function saveEdit() {
  if (!editStore.current) return
  editStore.saving = true
  try {
    await casesApi.patch(caseId.value, { payload: editStore.current })
    editStore.markClean(editStore.current)
    ElMessage.success('已保存')
    // Exit edit mode after a successful save.  Without this the page
    // would stay in edit state with a "✓ 已保存" tag — confusing because
    // there is no further "save" pending.  Drop the in-memory buffer;
    // next click on 编辑 reloads a fresh copy.
    editStore.cancelEdit()
    await casesStore.fetchOne(caseId.value)
  } catch {
    ElMessage.error(editStore.lastError || '保存失败')
  } finally {
    editStore.saving = false
  }
}

function cancelEdit() {
  editStore.cancelEdit()
}

// ── scenarioId rename (Spec-2 §4.3 C10) ────────────────────────
// Owners can rename private cases anytime; admins can rename public
// cases.  Server enforces the same rules — disable the button in
// read-only mode (or when we know the user is neither owner nor admin)
// so the round-trip error never lands.
const canRename = computed(() => {
  if (!payload.value) return false
  const sum = payload.value.summary
  const u = authStore.currentUser
  if (!u) return false
  if (sum.visibility === 'private') return sum.owner_id === u.id
  return authStore.isAdmin
})

function openRename() {
  if (!canRename.value) return
  renameOpen.value = true
}

async function onRenameSubmit(newCaseId: string) {
  if (!scenarioId.value) return
  renameSubmitting.value = true
  try {
    await casesStore.renameCase(scenarioId.value, newCaseId)
    renameOpen.value = false
    // Navigate to the new URL so the rest of the page (editable panels,
    // topbar, hidden profile) reloads against the new case_id.  The
    // case-detail watcher handles the actual re-fetch.
    ElMessage.success(`已重命名为：${newCaseId}`)
    if (route.params.caseId !== newCaseId) {
      router.replace(`/cases/${encodeURIComponent(newCaseId)}/config`)
    }
  } catch (err) {
    // The http interceptor rejects with ApiError whose ``.message`` is
    // FastAPI's ``detail`` (e.g. "目标 scenarioId 已存在", "only owner
    // can rename private case").  Surface that instead of a generic toast.
    const msg =
      (err instanceof Error && err.message) ||
      casesStore.lastError ||
      '重命名失败'
    ElMessage.error(msg)
  } finally {
    renameSubmitting.value = false
  }
}

// ── step CRUD (Spec-2-4 edit mode) ─────────────────────────
function replaceStep(idx: number, s: Step) {
  editStore.patchCurrent((p) => {
    const arr = (p.steps as Step[]) || []
    arr[idx] = s
    p.steps = [...arr]
  })
}

function removeStep(idx: number) {
  editStore.patchCurrent((p) => {
    const arr = (p.steps as Step[]) || []
    p.steps = arr.filter((_, i) => i !== idx)
  })
}

function appendStep() {
  editStore.patchCurrent((p) => {
    const arr = (p.steps as Step[]) || []
    p.steps = [
      ...arr,
      {
        description: 'new step',
        api: { service: '', method: 'GET', path: '/' },
      },
    ]
  })
}

onMounted(load)
watch(() => route.params.caseId, load)

// Keyboard: `?` toggles help modal
function onKeydown(e: KeyboardEvent) {
  // Don't intercept while typing in an input
  const tag = (e.target as HTMLElement)?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable) {
    return
  }
  if (e.key === '?' || (e.shiftKey && e.key === '/')) {
    helpOpen.value = !helpOpen.value
  }
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.config-view {
  background: #f5f3ee;
  min-height: calc(100vh - 48px);
  padding: 0 0 32px;
}

/* ── Topbar ──────────────────────────────────────────── */
.topbar {
  display: flex;
  align-items: center;
  gap: 14px;
  height: 48px;
  padding: 0 18px;
  color: #fff;
  font-size: 12px;
  background: #1f2933;
}

.status-dot {
  width: 8px;
  height: 8px;
  background: #22c55e;
  border-radius: 50%;
}

.brand {
  opacity: 0.8;
}

.scenario-label {
  margin-left: 18px;
  color: #94a3b8;
}

.scenario-id {
  padding: 3px 8px;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 12px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
}

.spacer {
  flex: 1;
}

.show-hidden-toggle {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  cursor: pointer;
}

.show-hidden-toggle input {
  accent-color: #4338ca;
}

.topbar-btn {
  height: 28px;
  padding: 0 12px;
  color: inherit;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.08);
  border: 0;
  border-radius: 6px;
  cursor: pointer;
}

.topbar-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* 重命名 scenarioId — 浅色高亮，让顶部 scenarioId 那块儿变成可点击的
   视觉重心（普通 topbar-btn 是深底白字，这个反过来）。*/
.topbar-rename {
  color: var(--accent);
  background: rgba(99, 102, 241, 0.12);
  font-weight: 600;
}

.topbar-rename:hover,
.topbar-rename:focus-visible {
  color: #fff;
  background: var(--accent);
  outline: none;
}

.dirty-tag {
  display: inline-block;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 600;
  color: #16a34a;
  background: #dcfce7;
  border-radius: 4px;
  transition: all 0.2s;
}

.dirty-tag.visible {
  color: #b45309;
  background: #fef9c3;
}

/* ── Tab row ──────────────────────────────────────────── */
.tab-row {
  display: flex;
  gap: 4px;
  align-items: flex-end;
  padding: 12px 18px 0;
  background: #f5f3ee;
}

.tab {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 12px;
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 8px 8px 0 0;
  cursor: pointer;
}

.tab.active {
  height: 36px;
  font-weight: 600;
}

.tab-purple.active {
  color: #5b21b6;
  background: #ede9fe;
  border-bottom-color: #c4b5fd;
}

.tab-green.active {
  color: #166534;
  background: #dcfce7;
  border-bottom-color: #86efac;
}

.tab-yellow.active {
  color: #854d0e;
  background: #fef9c3;
  border-bottom-color: #fde68a;
}

.tab-blue.active {
  color: #4338ca;
  background: #ede9fe;
  border-bottom-color: #c4b5fd;
}

.tab-summary {
  padding: 6px 12px;
  color: #64748b;
  font-size: 11px;
}

/* ── Card ────────────────────────────────────────────── */
.card {
  background: #fff;
  margin: 0 18px;
  padding: 18px 28px;
  border-radius: 0 13px 13px 13px;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
}

.tab-panel {
  min-height: 200px;
}

/* ── Meta tab ────────────────────────────────────────── */
.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 24px;
}

/* ── Config tab ──────────────────────────────────────── */
.config-group {
  padding: 14px 0;
  border-bottom: 1px solid #f1f5f9;
}

.config-group:last-child {
  border-bottom: 0;
}

.group-title {
  margin: 0 0 8px;
  color: var(--color-text-secondary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.kv-tables {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px 18px;
}

.kv-table {
  padding: 6px 0;
}

.kv-table-title {
  margin-bottom: 4px;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 10.5px;
}

.kv-row {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px dashed #f1f5f9;
  font-size: 11.5px;
}

.kv-row:last-child {
  border-bottom: 0;
}

.kv-key {
  padding: 2px 6px;
  color: var(--color-text-primary);
  background: #f8fafc;
  border-radius: 4px;
}

.kv-val {
  min-width: 0;
  overflow-wrap: anywhere;
  color: #5b21b6;
}

.kv-empty {
  padding: 8px 0;
  color: var(--color-text-tertiary);
  font-size: 11px;
  text-align: center;
}

/* ── Resource tab ─────────────────────────────────────── */
.empty-state,
.loading-state {
  padding: 60px 20px;
  color: var(--color-text-tertiary);
  font-size: 12px;
  text-align: center;
}

.resource-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.resource-row {
  display: grid;
  grid-template-columns: 140px 100px 1fr;
  gap: 12px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px dashed #f1f5f9;
}

.resource-key {
  padding: 3px 8px;
  color: var(--color-text-primary);
  background: #f8fafc;
  border-radius: 4px;
}

.resource-kind {
  padding: 2px 6px;
  color: #5b21b6;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  background: #ede9fe;
  border-radius: 4px;
}

.resource-val {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Steps tab ────────────────────────────────────────── */
.l3-banner {
  padding: 8px 12px;
  margin-bottom: 12px;
  color: #64748b;
  font-size: 11px;
  background: rgba(99, 102, 241, 0.04);
  border-radius: 6px;
}

.banner-link {
  margin-left: 8px;
  color: var(--accent);
  text-decoration: underline;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ── States ───────────────────────────────────────────── */
.state {
  max-width: 720px;
  padding: 80px 20px;
  margin: 0 auto;
  text-align: center;
}

.error-state p {
  margin-bottom: 12px;
  color: #991b1b;
}

/* ── Responsive ───────────────────────────────────────── */
@media (max-width: 900px) {
  .topbar {
    flex-wrap: wrap;
    height: auto;
    padding: 8px 14px;
  }
  .scenario-label,
  .scenario-id,
  .show-hidden-toggle {
    margin-left: 0;
  }
  .card {
    margin: 0 10px;
    padding: 14px 16px;
  }
  .field-grid,
  .resource-row {
    grid-template-columns: 1fr;
  }
}
</style>