<!--
  AssertionRegistryEditor.vue — 断言管理编辑器(spec v3 §5/§8)

     场景级注册表的独立编辑视图(路由 /scenarios/:scenarioId/assertions):
       - 条目列表:名称 / path 徽标(步骤N · jsonpath + ↗ 跳编排器)/
         值摘要 / 期望数;悬空条目(step-oob / path-unresolvable /
         override-no-match,registryIssues)标灰;v2 旧条目(无 path)灰显
         「旧版条目,请重建」,不可选不可编辑(保留原样不删)
       - 条目详情:path 只读 + 跳编排器;value 类型化编辑
         (str/num/bool/json,按字段当前字面量类型还原);
         asserts 编辑(步骤/target/操作符/期望值/mode,继承 v2)
       - 手工新建 = 步骤下拉 + jsonpath 输入(path 是注入地址,不预设
         模板化);整体 PUT 保存 — 只动 assertion_registry 键
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
        <el-button type="primary" plain :loading="saving" :disabled="!draft" @click="save">保存</el-button>
      </div>
    </header>

    <p class="are-lead">
      每条 = 一次偏离注入:定位 path(引擎 Assign 直补 request_body,与数据集 vars 解耦)
      + 注入值 + 期望配对(override 覆写既有断言 / append 追加),执行时与数据集行
      交叉(spec v3 §3/§4)。悬空条目标灰只提示,不阻断编辑。
    </p>

    <!-- 手工新建:步骤 + jsonpath(path 即注入地址) -->
    <div class="are-new-bar">
      <el-select
        :model-value="pendingPath.stepIndex"
        size="small"
        class="are-step-select"
        @update:model-value="(v: any) => (pendingPath.stepIndex = Number(v))"
      >
        <el-option v-for="(label, i) in stepLabels" :key="`np:${i}`" :value="i" :label="label" />
      </el-select>
      <el-input v-model="pendingPath.jsonpath" size="small" class="are-path-input" placeholder="jsonpath($.amount)" />
      <el-button size="small" :disabled="!draft" @click="addEntry">新建条目</el-button>
    </div>

    <!-- 条目列表:path 徽标 / 值摘要 / 期望数 / 死条目灰 / 旧版条目灰 -->
    <div class="are-list-card">
      <div
        v-for="e in registry.entries"
        :key="e.id"
        class="are-row"
        :class="{ 'are-dead': deadOf(e), 'are-legacy': isLegacyEntry(e), 'are-active': selectedId === e.id }"
        :title="isLegacyEntry(e) ? '旧版条目,请重建' : deadOf(e) ? `悬空:${issueSummary(e)}` : ''"
        @click="selectEntry(e)"
      >
        <span class="are-name">{{ e.name }}</span>
        <span v-if="!isLegacyEntry(e)" class="are-anchor">
          步骤{{ e.path.stepIndex + 1 }} · {{ e.path.jsonpath }}
          <button
            type="button"
            class="are-anchor-jump"
            title="跳编排器该步骤"
            @click.stop="jumpToAnchor(e.path.stepIndex)"
          >↗</button>
        </span>
        <span v-else class="are-anchor are-anchor-none">旧版条目,请重建</span>
        <span class="are-inject" :title="valueSummary(e)">{{ valueSummary(e) }}</span>
        <span class="are-count">{{ e.asserts?.length ?? 0 }} 期望</span>
        <span v-if="isLegacyEntry(e)" class="are-legacy-mark">旧版</span>
        <span v-else-if="deadOf(e)" class="are-dead-mark" :title="`悬空:${issueSummary(e)}`">悬空</span>
        <button type="button" class="are-del" title="删除条目" @click.stop="removeEntry(e.id)">×</button>
      </div>
      <div v-if="!registry.entries.length" class="are-empty">
        还没有偏离注入条目 — 上方手工建,或在编排器字段菜单「加入断言管理」自动带来
      </div>
    </div>

    <!-- 详情:path 只读 + value 类型化编辑 / asserts 编辑 -->
    <div v-if="selected && !isLegacyEntry(selected)" class="are-detail">
      <div class="are-detail-head">
        <el-input v-model="selected.name" class="are-name-input" size="small" placeholder="条目名称" />
        <span class="are-anchor">
          锚点:步骤{{ selected.path.stepIndex + 1 }} · {{ selected.path.source }} · {{ selected.path.jsonpath }}
          <button
            type="button"
            class="are-anchor-jump"
            title="跳编排器该步骤"
            @click="jumpToAnchor(selected.path.stepIndex)"
          >↗</button>
        </span>
      </div>

      <!-- 注入值(value)— 类型化编辑 -->
      <div class="are-sec">
        <h4>注入值(value)<span class="are-sec-hint">物化 = 引擎 Assign 直补 request_body(spec v3 §3);原样覆写不 coerce</span></h4>
        <div class="are-value-edit">
          <el-select v-model="valueDraft.kind" size="small" class="are-kind-select" @change="onKindChange">
            <el-option value="str" label="str" />
            <el-option value="num" label="num" />
            <el-option value="bool" label="bool" />
            <el-option value="json" label="json" />
          </el-select>
          <el-checkbox
            v-if="valueDraft.kind === 'bool'"
            v-model="valueDraft.bool"
            @change="applyValue"
          >true</el-checkbox>
          <el-input
            v-else
            v-model="valueDraft.text"
            size="small"
            class="are-val-input"
            placeholder="偏离值(例:-1 / &quot;中文&quot; / {&quot;a&quot;:1})"
            @change="applyValue"
          />
          <code class="are-val-preview" :title="fmtVal(selected.value)">→ {{ fmtVal(selected.value) }}</code>
        </div>
        <!-- 送达面注记(spec v3 §3 引擎语义):三类形状各自的真话 —
             $. 类可兜 / ${...} 类预处理先行 / null 类送不到 -->
        <div v-if="valueRefNote" class="are-val-note">{{ valueRefNote }}</div>
      </div>

      <!-- 期望配对(asserts)— 继承 v2 段 -->
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
    <div v-else-if="selected && isLegacyEntry(selected)" class="are-empty are-select-hint">旧版条目(v2 形状)— 不可编辑,请在编排器重新标记创建</div>
    <div v-else-if="draft" class="are-empty are-select-hint">点击上方条目查看详情</div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'
import { getScenarioDraft, updateScenario } from '@/api/scenario-composer'
import type { ScenarioDraft } from '@/types/scenario-composer'
import type { AssertionEntry, AssertionRegistry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'
import { bodyPathSetOf, genEntryId, isDeadEntry, normalizeRegistry, registryIssues } from '@/utils/assertion-registry'
import { fieldPathsOf } from '@/utils/dataset-segments'
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
const steps = computed(() => (draft.value?.definition.steps ?? []) as Array<Record<string, unknown>>)
const stepLabels = computed(() =>
  steps.value.map((s, i) => `${i + 1}·${(s as any)?.description || `Step ${i + 1}`}`),
)
const scenarioName = computed(() => draft.value?.definition?.meta?.name || scenarioId)

/** steps[si].request.body 叶子集合(悬空检测 path 维度,spec v3 §2) */
function bodyPathsOfStep(si: number): ReadonlySet<string> {
  return bodyPathSetOf(fieldPathsOf(steps.value[si] as any))
}
/** steps[si].strategy 的 assertion target 集合(悬空检测 override 维度) */
function assertTargetsOf(si: number): ReadonlySet<string> {
  const st = (steps.value[si]?.strategy as any[] | undefined) ?? []
  return new Set(st.filter((x) => x?.kind === 'assertion').map((x) => String(x.target)))
}
const deadOf = (e: AssertionEntry | LegacyAssertionEntry) =>
  isDeadEntry(e, stepCount.value, bodyPathsOfStep, assertTargetsOf)
const deadCount = computed(() => registry.value.entries.filter(deadOf).length)

/** 旧版条目不可选(不可编辑,spec v3 §8) */
function selectEntry(e: AssertionEntry | LegacyAssertionEntry) {
  if (isLegacyEntry(e)) return
  selectedId.value = e.id
}

/** 悬空原因摘要(title 展示):registryIssues 人话投影 */
function issueSummary(e: AssertionEntry | LegacyAssertionEntry): string {
  if (isLegacyEntry(e)) return '旧版条目(v2 形状),请在编排器重新标记创建'
  return registryIssues(e, stepCount.value, bodyPathsOfStep, assertTargetsOf)
    .map((iss) => {
      if (iss.kind === 'step-oob') return `步骤${iss.stepIndex + 1} 越界(场景共 ${stepCount.value} 步)`
      if (iss.kind === 'path-unresolvable') return `步骤${iss.stepIndex + 1} body 无字段 ${iss.jsonpath}`
      if (iss.kind === 'override-no-match') return `步骤${iss.stepIndex + 1} 无既有断言 ${iss.target}(override 无匹配)`
      return '旧版条目(v2 形状),请在编排器重新标记创建'
    })
    .join('; ')
}

/** 值摘要(列表展示) */
function valueSummary(e: AssertionEntry | LegacyAssertionEntry): string {
  if (isLegacyEntry(e)) return '—'
  return fmtVal(e.value) || '—'
}
function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  return JSON.stringify(v)
}

// ── value 类型化编辑(str/num/bool/json,spec v3 §2)─────────────────
type ValKind = 'str' | 'num' | 'bool' | 'json'
/** 按字段当前字面量类型还原编辑形态 */
function kindOf(v: unknown): ValKind {
  if (typeof v === 'number') return 'num'
  if (typeof v === 'boolean') return 'bool'
  if (v !== null && typeof v === 'object') return 'json'
  return 'str'
}
function tryJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}
const valueDraft = ref<{ kind: ValKind; text: string; bool: boolean }>({ kind: 'str', text: '', bool: false })
watch(selectedId, () => {
  const e = selected.value
  if (!e || isLegacyEntry(e)) return
  valueDraft.value = { kind: kindOf(e.value), text: fmtVal(e.value), bool: e.value === true }
})
/** 落回条目:str 原样 / num Number(非数回落原串)/ bool 直取 / json parse 失败回落原串 */
function applyValue() {
  const e = selected.value
  if (!e || isLegacyEntry(e)) return
  const d = valueDraft.value
  e.value = d.kind === 'num'
    ? (Number.isFinite(Number(d.text)) ? Number(d.text) : d.text)
    : d.kind === 'bool' ? d.bool
    : d.kind === 'json' ? tryJson(d.text)
    : d.text
}
/** 切类型立即按新形态落值(编辑器随时可切回原类型) */
function onKindChange() {
  applyValue()
}

/** 值送达面注记(与后端 run_injection._assign_strategy 同一份语义,
 *  两处必须同改)。三类形状各自的**真话**,不得混用「default 兜底」——
 *  那句话只对 `$.` 类成立:
 *  · "$.xxx":引擎在 Assign 执行期按 JSONPath 从场景上下文读,读不到得
 *    None —— 平台补的 default(=字面量)+ required:false 在此生效;
 *    上下文恰好同名时解析命中,被上下文值覆写(边界三);
 *  · 整串 "${...}":引擎**在任何策略执行之前**做模板展开(平台的
 *    default 兜不住)—— 变量缺失 → 预处理阶段硬失败(比 Assign 早);
 *    变量存在 → 写入变量值,不是本字面量;
 *  · null / 缺 value 键:送不到 —— plate 导出丢弃 source=null 的
 *    Assign,引擎 Assign.source 必填 → 该用例加载即失败。 */
const valueRefNote = computed(() => {
  const e = selected.value
  if (!e || isLegacyEntry(e)) return ''
  const v = e.value
  if (v === null || v === undefined) {
    return 'null(或缺 value 键)送不到引擎:plate 导出会丢弃 source 为 null 的 Assign,'
      + '该用例加载即失败。请改用字符串(如空串 / "null")表达,或删除本条目。'
  }
  if (typeof v !== 'string') return ''
  if (v.startsWith('${') && v.endsWith('}')) {
    return '整串 ${...} 是引擎的模板引用,平台补的 default 兜不住它:引擎在任何策略执行前'
      + '先做模板展开 —— config.vars 缺同名变量则该用例在预处理阶段即失败;'
      + '有同名变量则此处写入变量值,不是本字面量。'
  }
  if (v.startsWith('$.')) {
    return '以 $. 开头:引擎先按 JSONPath 从场景上下文读,读不到才写入本字面量'
      + '(平台已补 default 兜底);若场景上下文里恰好存在同名路径,会被上下文值覆写。'
  }
  return ''
})

/** 手工新建暂存:步骤 + jsonpath(path 是注入地址,不预设模板化) */
const pendingPath = ref({ stepIndex: 0, jsonpath: '' })
/** asserts 行编辑暂存(mode 字符串形态,入条目时收窄) */
const pendingAssert = ref({ stepIndex: 0, target: '', operator: 'eq', expected: '', mode: 'override' as string })
const OPERATORS = ['eq', 'ne', 'gt', 'ge', 'lt', 'le', 'contains', 'exists']

const saving = ref(false)

onMounted(async () => {
  try {
    draft.value = await getScenarioDraft(scenarioId)
    // 归一:旧场景 draft 该键经后端 default 补成 {}(truthy,?? 兜不住)
    registry.value = normalizeRegistry(draft.value.assertion_registry)
  } catch (e) {
    showError('加载', e)
  }
})

function addEntry() {
  if (!pendingPath.value.jsonpath.startsWith('$')) {
    ElMessage.warning('jsonpath 需以 $ 开头(例:$.amount)')
    return
  }
  const e: AssertionEntry = {
    id: genEntryId(),
    name: `偏离 ${registry.value.entries.length + 1}`,
    path: {
      stepIndex: pendingPath.value.stepIndex,
      source: 'body',
      jsonpath: pendingPath.value.jsonpath,
    },
    value: '',
    asserts: [],
  }
  registry.value.entries.push(e)
  selectedId.value = e.id
  pendingPath.value = { stepIndex: pendingPath.value.stepIndex, jsonpath: '' }
}
function removeEntry(id: string) {
  registry.value.entries = registry.value.entries.filter((e) => e.id !== id)
  if (selectedId.value === id) selectedId.value = null
}
function addAssert() {
  if (!selected.value || isLegacyEntry(selected.value) || !pendingAssert.value.target) return
  selected.value.asserts.push({
    stepIndex: pendingAssert.value.stepIndex,
    target: pendingAssert.value.target,
    operator: pendingAssert.value.operator,
    expected: pendingAssert.value.expected,
    mode: pendingAssert.value.mode === 'append' ? 'append' : 'override',
  })
}
/** path ↗:跳编排器画布聚焦该步骤(与 DataSetEditor jumpToRef 同契约) */
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

/* ── 手工新建条 ── */
.are-new-bar {
  display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
}
.are-path-input { width: 260px; }

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
.are-row.are-legacy { opacity: .55; }
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
.are-legacy-mark {
  font-size: 10px; font-weight: 700; color: #64748b;
  background: #f1f5f9; border-radius: 3px; padding: 1px 5px;
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

/* ── value 类型化编辑 ── */
.are-value-edit { display: flex; align-items: center; gap: 8px; }
.are-kind-select { width: 90px; }
.are-val-preview {
  font-family: var(--font-mono); font-size: 11px; color: #4338ca;
  background: #eef2ff; border-radius: 3px; padding: 1px 6px;
}
/* 送达面注记:引擎把该类值先当上下文引用读 / null 送不到 — 橙底软提示,
   不阻断编辑(条目照常保存,只是运行语义与字面直觉不同) */
.are-val-note {
  margin-top: 6px; font-size: 11px; line-height: 1.5;
  color: #92400e; background: #fef3c7;
  border-radius: 4px; padding: 4px 8px;
}

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
