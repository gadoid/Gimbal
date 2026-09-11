<!--
  AssertionRegistryEditor.vue — 断言管理(偏离注入)编辑器(spec v2 §7)

     场景级注册表的独立编辑视图(路由 /scenarios/:scenarioId/assertions):
       - 条目列表:名称 / 锚定徽标(步骤N · jsonpath + ↗ 跳编排器)/
         值偏离摘要 / 期望数;悬空条目(步骤越界 / 变量未声明 /
         override 无匹配,registryIssues)标灰 + title 摘要,不阻断编辑
       - 条目详情:anchor 只读展示 + 跳转;injection 编辑
         (varName 候选 = config.vars);asserts 编辑
         (步骤/target/操作符/期望值/mode,操作符允许自定义)
       - 手工新建(genEntryId);整体 PUT 保存 — 只动 assertion_registry 键,
         definition/orchestration 原样透传(编辑器不改被测系统)
       - 值类别快捷/生成器等 v2 协议位不做(spec §7 收敛)
-->
<template>
  <section class="are-editor">
    <header class="page-header">
      <div>
        <h2 class="page-title">断言管理(偏离注入)</h2>
        <p>
          场景 <strong class="scenario-name">{{ scenarioName }}</strong>
          <code class="sid">{{ scenarioId }}</code>
          · {{ registry.entries.length }} 条目 · 悬空 {{ deadCount }} 条
        </p>
      </div>
      <div class="header-actions">
        <el-button :icon="Back" @click="router.push(composerUrl(scenarioId, 1))">返回编排器</el-button>
        <el-button :disabled="!draft" @click="addEntry">新建条目</el-button>
        <el-button type="primary" plain :loading="saving" :disabled="!draft" @click="save">保存</el-button>
      </div>
    </header>

    <p class="are-lead">
      每条 = 一次偏离注入:值偏离(运行时覆写 config.vars 基线)+ 期望配对
      (override 覆写既有断言 / append 追加),执行时与数据集并列选择(spec v2 §3)。
      悬空条目标灰只提示,不阻断编辑。
    </p>

    <!-- 条目列表:锚定徽标 / 偏离摘要 / 期望数 / 死条目灰 -->
    <div class="are-list-card">
      <div
        v-for="e in registry.entries"
        :key="e.id"
        class="are-row"
        :class="{ 'are-dead': deadOf(e), 'are-active': selectedId === e.id }"
        :title="deadOf(e) ? `悬空:${issueSummary(e)}` : ''"
        @click="selectedId = e.id"
      >
        <span class="are-name">{{ e.name }}</span>
        <span v-if="e.anchor" class="are-anchor">
          步骤{{ e.anchor.stepIndex + 1 }} · {{ e.anchor.jsonpath }}
          <button
            type="button"
            class="are-anchor-jump"
            title="跳编排器该步骤"
            @click.stop="jumpToAnchor(e.anchor!.stepIndex)"
          >↗</button>
        </span>
        <span v-else class="are-anchor are-anchor-none">无锚点</span>
        <span class="are-inject" :title="injectionSummary(e)">{{ injectionSummary(e) }}</span>
        <span class="are-count">{{ e.asserts.length }} 期望</span>
        <span v-if="deadOf(e)" class="are-dead-mark" :title="`悬空:${issueSummary(e)}`">悬空</span>
        <button type="button" class="are-del" title="删除条目" @click.stop="removeEntry(e.id)">×</button>
      </div>
      <div v-if="!registry.entries.length" class="are-empty">
        还没有偏离注入条目 — 「新建条目」手工建,或在编排器标记锚点自动带来
      </div>
    </div>

    <!-- 详情:anchor 只读 + injection / asserts 编辑 -->
    <div v-if="selected" class="are-detail">
      <div class="are-detail-head">
        <el-input v-model="selected.name" class="are-name-input" size="small" placeholder="条目名称" />
        <span v-if="selected.anchor" class="are-anchor">
          锚点:步骤{{ selected.anchor.stepIndex + 1 }} · {{ selected.anchor.source }} · {{ selected.anchor.jsonpath }}
          <template v-if="selected.anchor.varName"> · var {{ selected.anchor.varName }}</template>
          <button
            type="button"
            class="are-anchor-jump"
            title="跳编排器该步骤"
            @click="jumpToAnchor(selected.anchor!.stepIndex)"
          >↗</button>
        </span>
        <span v-else class="are-anchor-none">无锚点(溯源面 — 编排器标记自动带来,执行不依赖)</span>
      </div>

      <!-- 值偏离(injection)-->
      <div class="are-sec">
        <h4>值偏离(injection)<span class="are-sec-hint">物化 = 运行时覆写 config.vars 基线</span></h4>
        <div v-if="!selected.injection.length" class="are-empty">没有值偏离 — varName 从 config.vars 候选选择</div>
        <div v-for="(inj, i) in selected.injection" :key="`${inj.varName}:${i}`" class="are-kv">
          <code>{{ inj.varName }}</code>
          <span class="are-sep">=</span>
          <code class="are-val">{{ fmtVal(inj.value) }}</code>
          <button type="button" class="are-del" title="删除值偏离" @click="selected.injection.splice(i, 1)">×</button>
        </div>
        <div class="are-pending">
          <el-select
            v-model="pendingInject.varName"
            size="small"
            class="are-var-select"
            placeholder="变量(config.vars)"
            filterable
          >
            <el-option v-for="n in varNameOptions" :key="n" :value="n" :label="n" />
          </el-select>
          <el-input v-model="pendingInject.value" size="small" class="are-val-input" placeholder="偏离值(例:-1)" />
          <button type="button" class="are-add-inject" @click="addInject">+ 添加值偏离</button>
        </div>
      </div>

      <!-- 期望配对(asserts)-->
      <div class="are-sec">
        <h4>期望配对(asserts)<span class="are-sec-hint">override 覆写既有断言(匹配键 = 步骤+target)/ append 追加</span></h4>
        <div v-if="!selected.asserts.length" class="are-empty">没有期望配对</div>
        <table v-else class="are-asserts">
          <thead>
            <tr><th>步骤</th><th>target</th><th>op</th><th>expected</th><th>mode</th><th /></tr>
          </thead>
          <tbody>
            <tr v-for="(a, i) in selected.asserts" :key="`${a.stepIndex}:${a.target}:${i}`">
              <td>{{ stepLabels[a.stepIndex] ?? `步骤${a.stepIndex + 1}` }}</td>
              <td><code>{{ a.target }}</code></td>
              <td>{{ a.operator }}</td>
              <td><code class="are-val">{{ fmtVal(a.expected) }}</code></td>
              <td><span class="are-mode" :class="`m-${a.mode}`">{{ a.mode }}</span></td>
              <td><button type="button" class="are-del" title="删除期望" @click="selected.asserts.splice(i, 1)">×</button></td>
            </tr>
          </tbody>
        </table>
        <div class="are-pending are-pending-assert">
          <el-select
            :model-value="pendingAssert.stepIndex"
            size="small"
            class="are-step-select"
            @update:model-value="(v: any) => (pendingAssert.stepIndex = Number(v))"
          >
            <el-option v-for="(label, i) in stepLabels" :key="`sa:${i}`" :value="i" :label="label" />
          </el-select>
          <el-input v-model="pendingAssert.target" size="small" class="are-target-input" placeholder="target($.response_body.code)" />
          <el-select v-model="pendingAssert.operator" size="small" class="are-op-select" filterable allow-create>
            <el-option v-for="op in OPERATORS" :key="op" :value="op" :label="op" />
          </el-select>
          <el-input v-model="pendingAssert.expected" size="small" class="are-exp-input" placeholder="期望值" />
          <el-select v-model="pendingAssert.mode" size="small" class="are-mode-select">
            <el-option value="override" label="override" />
            <el-option value="append" label="append" />
          </el-select>
          <button type="button" class="are-add-assert" @click="addAssert">+ 添加期望</button>
        </div>
      </div>
    </div>
    <div v-else-if="draft" class="are-empty are-select-hint">点击上方条目查看详情</div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'
import { getScenarioDraft, updateScenario } from '@/api/scenario-composer'
import type { ScenarioDraft } from '@/types/scenario-composer'
import type { AssertionEntry, AssertionRegistry } from '@/types/assertion-registry'
import { genEntryId, isDeadEntry, registryIssues } from '@/utils/assertion-registry'
import { composerUrl } from '@/utils/links'
import { showError } from '@/utils/errorFallback'

const route = useRoute()
const router = useRouter()
const scenarioId = route.params.scenarioId as string

const draft = ref<ScenarioDraft | null>(null)
const registry = ref<AssertionRegistry>({ entries: [] })
const selectedId = ref<string | null>(null)
const selected = computed(() => registry.value.entries.find((e) => e.id === selectedId.value) ?? null)
const stepCount = computed(() => draft.value?.definition.steps?.length ?? 0)
const varNames = computed(() => new Set(Object.keys(draft.value?.definition.config?.vars ?? {})))
/** el-option 候选数组(Set 不进模板,vue-tsc 纪律) */
const varNameOptions = computed(() => [...varNames.value])
const stepLabels = computed(() =>
  (draft.value?.definition.steps ?? []).map((s: any, i: number) => `${i + 1}·${s?.description || `Step ${i + 1}`}`),
)
const scenarioName = computed(() => draft.value?.definition?.meta?.name || scenarioId)

/** steps[si].strategy 的 assertion target 集合(悬空检测喂食) */
function assertTargetsOf(si: number): ReadonlySet<string> {
  const st = (draft.value?.definition.steps ?? [])[si]?.strategy as any[] | undefined
  return new Set((st ?? []).filter((x) => x?.kind === 'assertion').map((x) => String(x.target)))
}
const deadOf = (e: AssertionEntry) => isDeadEntry(e, stepCount.value, varNames.value, assertTargetsOf)
const deadCount = computed(() => registry.value.entries.filter(deadOf).length)

/** 悬空原因摘要(title 展示):registryIssues 人话投影 */
function issueSummary(e: AssertionEntry): string {
  return registryIssues(e, stepCount.value, varNames.value, assertTargetsOf)
    .map((iss) => {
      if (iss.kind === 'step-oob') return `步骤${iss.stepIndex + 1} 越界(场景共 ${stepCount.value} 步)`
      if (iss.kind === 'var-unknown') return `变量 ${iss.varName} 未在 config.vars 声明`
      return `步骤${iss.stepIndex + 1} 无既有断言 ${iss.target}(override 无匹配)`
    })
    .join('; ')
}

/** 值偏离摘要:`var = value` 逗号连缀(空 = 长破折) */
function injectionSummary(e: AssertionEntry): string {
  return e.injection.map((inj) => `${inj.varName} = ${fmtVal(inj.value)}`).join(', ') || '—'
}
function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  return JSON.stringify(v)
}

/** injection 行编辑的暂存(下拉 + 值,「添加」入条目) */
const pendingInject = ref<{ varName: string; value: string }>({ varName: '', value: '' })
/** asserts 行编辑暂存(mode 字符串形态,入条目时收窄) */
const pendingAssert = ref({ stepIndex: 0, target: '', operator: 'eq', expected: '', mode: 'override' as string })
const OPERATORS = ['eq', 'ne', 'gt', 'ge', 'lt', 'le', 'contains', 'exists']

const saving = ref(false)

onMounted(async () => {
  try {
    draft.value = await getScenarioDraft(scenarioId)
    registry.value = draft.value.assertion_registry ?? { entries: [] }
  } catch (e) {
    showError('加载', e)
  }
})

function addEntry() {
  const e: AssertionEntry = {
    id: genEntryId(),
    name: `偏离 ${registry.value.entries.length + 1}`,
    injection: [],
    asserts: [],
  }
  registry.value.entries.push(e)
  selectedId.value = e.id
  pendingInject.value = { varName: varNameOptions.value[0] ?? '', value: '' }
  pendingAssert.value = { stepIndex: 0, target: '', operator: 'eq', expected: '', mode: 'override' }
}
function removeEntry(id: string) {
  registry.value.entries = registry.value.entries.filter((e) => e.id !== id)
  if (selectedId.value === id) selectedId.value = null
}
function addInject() {
  if (!selected.value || !pendingInject.value.varName) return
  selected.value.injection.push({ ...pendingInject.value })
  pendingInject.value = { varName: pendingInject.value.varName, value: '' }
}
function addAssert() {
  if (!selected.value || !pendingAssert.value.target) return
  selected.value.asserts.push({
    stepIndex: pendingAssert.value.stepIndex,
    target: pendingAssert.value.target,
    operator: pendingAssert.value.operator,
    expected: pendingAssert.value.expected,
    mode: pendingAssert.value.mode === 'append' ? 'append' : 'override',
  })
}
/** anchor ↗:跳编排器画布聚焦该步骤(与 DataSetEditor jumpToRef 同契约) */
function jumpToAnchor(si: number) {
  router.push({ path: `/composer/${encodeURIComponent(scenarioId)}`, query: { step: '4', focusStep: String(si) } })
}
/** 整体 PUT — 只动 assertion_registry 键,definition/orchestration 原样透传 */
async function save() {
  if (!draft.value || saving.value) return
  saving.value = true
  try {
    await updateScenario(scenarioId, { ...draft.value, assertion_registry: registry.value })
    ElMessage.success('断言管理已保存')
  } catch (e) {
    showError('保存', e)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.are-editor {
  max-width: 1080px; min-height: calc(100vh - 48px);
  padding: 28px 32px 48px; margin: 0 auto; box-sizing: border-box;
}
.page-header {
  display: flex; gap: 24px; align-items: center;
  justify-content: space-between; margin-bottom: 14px;
}
.page-header h2 { margin: 0; font-size: 22px; color: var(--color-text-primary); }
.page-header p { margin: 5px 0 0; font-size: 12px; color: var(--color-text-secondary); }
.page-header code.sid {
  padding: 1px 4px; font-family: var(--font-mono); font-size: 11px;
  background: var(--accent-soft); border-radius: 3px;
}
.page-header .scenario-name {
  color: var(--color-text-primary); font-weight: 600; margin-right: 4px;
}
.header-actions { display: flex; gap: 8px; }

.are-lead {
  margin: 0 0 14px; font-size: 12px; line-height: 1.6;
  color: var(--color-text-secondary);
}

/* ── 条目列表 ── */
.are-list-card {
  background: #fff; border: 1px solid var(--color-border-tertiary);
  border-radius: 8px; overflow: hidden; margin-bottom: 14px;
}
.are-row {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; cursor: pointer; font-size: 13px;
  border-bottom: 1px solid var(--color-border-tertiary);
}
.are-row:last-child { border-bottom: none; }
.are-row:hover { background: #f8faff; }
.are-row.are-active { background: #f0f5ff; box-shadow: inset 2px 0 0 var(--accent); }
.are-row.are-dead { opacity: .55; }
.are-name { font-weight: 600; color: var(--color-text-primary); min-width: 96px; }
.are-anchor {
  font-family: var(--font-mono); font-size: 11px; color: #4338ca;
  background: #eef2ff; border-radius: 3px; padding: 1px 6px;
  white-space: nowrap;
}
.are-anchor-none { font-family: inherit; color: var(--color-text-secondary); background: #f1f5f9; }
.are-anchor-jump {
  border: none; background: transparent; color: #7c3aed; cursor: pointer;
  font-size: 12px; padding: 0 2px; margin-left: 2px;
}
.are-anchor-jump:hover { color: #4c1d95; }
.are-inject {
  flex: 1; font-family: var(--font-mono); font-size: 11px; color: #334155;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.are-count { font-size: 11px; color: var(--color-text-secondary); white-space: nowrap; }
.are-dead-mark {
  font-size: 10px; font-weight: 700; color: #b45309;
  background: #fef3c7; border-radius: 3px; padding: 1px 5px;
}
.are-empty { padding: 14px 16px; font-size: 12px; color: var(--color-text-secondary); }
.are-select-hint { border: 1px dashed var(--color-border-tertiary); border-radius: 8px; }

.are-del {
  width: 24px; height: 24px; background: transparent; border: none; border-radius: 4px;
  color: var(--color-text-secondary); cursor: pointer; font-size: 15px;
  display: inline-flex; align-items: center; justify-content: center;
}
.are-del:hover { background: #fef2f2; color: #ef4444; }

/* ── 详情 ── */
.are-detail {
  background: #fff; border: 1px solid var(--color-border-tertiary);
  border-radius: 8px; padding: 14px 16px;
}
.are-detail-head {
  display: flex; align-items: center; gap: 12px; margin-bottom: 6px;
  padding-bottom: 10px; border-bottom: 1px solid var(--color-border-tertiary);
}
.are-name-input { width: 220px; }
.are-anchor-none { font-size: 11px; }

.are-sec { margin-top: 12px; }
.are-sec h4 { margin: 0 0 6px; font-size: 13px; color: var(--color-text-primary); }
.are-sec-hint { margin-left: 8px; font-size: 11px; font-weight: normal; color: var(--color-text-secondary); }
.are-kv {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 8px; font-size: 12px; border-radius: 4px;
}
.are-kv:hover { background: #f8fafc; }
.are-kv code { font-family: var(--font-mono); color: #334155; }
.are-kv .are-val { color: #0f172a; }
.are-sep { color: var(--color-text-secondary); }
.are-kv .are-del { margin-left: auto; }

.are-pending {
  display: flex; align-items: center; gap: 8px; margin-top: 8px;
}
.are-var-select { width: 200px; }
.are-val-input { width: 200px; }
.are-step-select { width: 160px; }
.are-target-input { flex: 1; min-width: 180px; }
.are-op-select { width: 110px; }
.are-exp-input { width: 160px; }
.are-mode-select { width: 110px; }
.are-add-inject, .are-add-assert {
  border: 1px dashed #cbd5e1; background: transparent; border-radius: 4px;
  color: var(--accent); cursor: pointer; font-size: 12px; padding: 5px 10px;
  white-space: nowrap;
}
.are-add-inject:hover, .are-add-assert:hover { border-color: var(--accent); background: #f8faff; }

/* 期望配对表 */
.are-asserts {
  width: 100%; border-collapse: collapse; font-size: 12px;
  font-family: var(--font-mono);
}
.are-asserts th, .are-asserts td {
  padding: 5px 8px; text-align: left;
  border-bottom: 1px solid var(--color-border-tertiary);
}
.are-asserts th { color: var(--color-text-secondary); font-weight: normal; font-size: 11px; background: #f8fafc; }
.are-mode { font-size: 10px; font-weight: 700; border-radius: 3px; padding: 1px 5px; }
.are-mode.m-override { color: #b45309; background: #fef3c7; }
.are-mode.m-append { color: #065f46; background: #d1fae5; }
</style>
