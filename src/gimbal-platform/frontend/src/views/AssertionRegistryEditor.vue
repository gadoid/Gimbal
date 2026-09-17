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

  **界面词汇 ↔ 字段**(每次改动两边同改;界面一律用户词,不印引擎术语):
    注入路径 = `path` · 注入值 = `value` · 绑定断言 = `asserts[]`
-->
<template>
  <section class="are-editor">
    <header class="page-header">
      <div>
        <h2 class="page-title">断言管理</h2>
        <p>
          场景 <strong class="scenario-name">{{ scenarioName }}</strong>
          <code class="sid">{{ scenarioId }}</code>
          · {{ registry.entries.length }} 条目 · 悬空 {{ deadCount }} 条
        </p>
      </div>
      <div class="header-actions">
        <el-button v-if="focusMode" :icon="Back" @click="exitFocus">全部条目</el-button>
        <el-button :icon="Back" @click="router.push(composerUrl(scenarioId, 1))">返回编排器</el-button>
        <el-button type="primary" plain :loading="saving" :disabled="!draft" @click="save">保存</el-button>
      </div>
    </header>

    <p class="are-lead">
      每条 = 一次注入,由三部分构成:<strong>注入路径</strong>(把哪一步请求体里的哪个字段改掉)、
      <strong>注入值</strong>(改成什么)、<strong>绑定断言</strong>(这次改动之后应当看到什么)。
      运行时与数据集行交叉组合。条目标灰只提示地址失效,不阻断编辑。
    </p>

    <!-- 判定面提示位:降级 / 换面两种状态共用一条(SurfaceNotice,三处宿主同一份
         呈现)—— ①降级给重试入口,②换面给关闭口;降级优先(自带恢复动作)。 -->
    <SurfaceNotice
      v-if="notice"
      :kind="notice.kind"
      :text="notice.text"
      @retry="retryDegraded"
      @close="acknowledgeChanged"
    />

    <!-- 草稿到位前不渲染列表/详情:加载中不是「没有」,先闪一句
         「还没有条目」是假话;聚焦态还会先闪一下列表再收起 -->
    <template v-if="draft">
    <!-- 手工新建:步骤 + jsonpath(path 即注入地址);聚焦态收起 -->
    <div v-if="!focusMode" class="are-new-bar">
      <el-select
        :model-value="pendingPath.stepIndex"
        size="small"
        class="are-step-select"
        @update:model-value="(v: any) => (pendingPath.stepIndex = Number(v))"
      >
        <el-option v-for="(label, i) in stepLabels" :key="`np:${i}`" :value="i" :label="label" />
      </el-select>
      <JsonPathInput
        v-model="pendingPath.jsonpath"
        class="are-path-input"
        :candidates="pathCandidates"
        :state-of="stateOfPendingPath"
        placeholder="注入路径(例:$.amount)"
      />
      <el-button size="small" :disabled="!draft" @click="addEntry">新建条目</el-button>
    </div>

    <!-- 条目列表:path 徽标 / 值摘要 / 期望数 / 死条目灰 / 旧版条目灰;
         聚焦态收起(只面对进来的那一条) -->
    <div v-if="!focusMode" class="are-list-card">
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
        还没有条目 — 上方手工建,或在编排器字段菜单「加入断言管理」自动带来
      </div>
    </div>

    <!-- 详情:path 只读 + value 类型化编辑 / asserts 编辑 -->
    <div v-if="selected && !isLegacyEntry(selected)" class="are-detail">
      <div class="are-detail-head">
        <el-input v-model="selected.name" class="are-name-input" size="small" placeholder="条目名称" />
        <span class="are-anchor">
          注入路径:第 {{ selected.path.stepIndex + 1 }} 步请求体 · <code>{{ selected.path.jsonpath }}</code>
          <button
            type="button"
            class="are-anchor-jump"
            title="跳编排器该步骤"
            @click="jumpToAnchor(selected.path.stepIndex)"
          >↗</button>
        </span>
        <!-- 聚焦态没有列表行,删除口只剩这里 —— 不补就等于把删除功能弄丢了
             (全量态仍由列表行的 × 承担,不重复出两个删除口) -->
        <button
          v-if="focusMode"
          type="button"
          class="are-del-focus"
          @click="removeEntry(selected.id)"
        >删除此条</button>
      </div>

      <!-- 注入值(value)— 类型化编辑 -->
      <div class="are-sec">
        <h4>注入值<span class="are-sec-hint">运行时把这个字段改成下面的值;原样写入,不做类型转换</span></h4>
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
            placeholder="注入值(例:-1 / &quot;中文&quot; / {&quot;a&quot;:1})"
            @change="applyValue"
          />
          <code class="are-val-preview" :title="fmtVal(selected.value)">→ {{ fmtVal(selected.value) }}</code>
        </div>
        <!-- 送达面注记(spec v3 §3 引擎语义):三类形状各自的真话 —
             $. 类可兜 / ${...} 类预处理先行 / null 类送不到 -->
        <div v-if="valueRefNote" class="are-val-note">{{ valueRefNote }}</div>
      </div>

      <!-- 绑定断言(asserts)— 继承 v2 段 -->
      <div class="are-sec">
        <h4>绑定断言<span class="are-sec-hint">这次注入之后,应当看到什么</span></h4>
        <div v-if="!selected.asserts.length" class="are-empty">还没有绑定断言</div>
        <table v-else class="are-asserts">
          <thead>
            <tr><th>步骤</th><th>断言哪个响应字段</th><th>判据</th><th>期望值</th><th>动作</th><th /></tr>
          </thead>
          <tbody>
            <tr v-for="(a, i) in selected.asserts" :key="`${a.stepIndex}:${a.target}:${i}`">
              <td>{{ stepLabels[a.stepIndex] ?? `步骤${a.stepIndex + 1}` }}</td>
              <td><code>{{ a.target }}</code></td>
              <td>{{ a.operator }}</td>
              <td><code class="are-val">{{ fmtVal(a.expected) }}</code></td>
              <td><span class="are-mode" :class="`m-${a.mode}`">{{ a.mode === 'append' ? '新增' : '改写' }}</span></td>
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
          <JsonPathInput
            v-model="pendingAssert.target"
            class="are-target-input"
            :candidates="targetCandidates"
            placeholder="断言哪个响应字段(例:$.response_body.code)"
          />
          <el-select v-model="pendingAssert.operator" size="small" class="are-op-select" filterable allow-create>
            <el-option v-for="op in OPERATORS" :key="op" :value="op" :label="op" />
          </el-select>
          <el-input v-model="pendingAssert.expected" size="small" class="are-exp-input" placeholder="期望值" />
          <el-select v-model="pendingAssert.mode" size="small" class="are-mode-select">
            <el-option value="append" label="新增一条" />
            <el-option value="override" label="改写已有" />
          </el-select>
          <button type="button" class="are-add-assert" @click="addAssert">+ 添加期望</button>
        </div>
      </div>
    </div>
    <div v-else-if="selected && isLegacyEntry(selected)" class="are-empty are-select-hint">旧版条目(v2 形状)— 不可编辑,请在编排器重新标记创建</div>
    <div v-else-if="!focusMode" class="are-empty are-select-hint">点击上方条目查看详情</div>
    </template>
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
import { genEntryId, normalizeRegistry } from '@/utils/assertion-registry'
import { assertablePaths } from '@/utils/declarations'
import { toScratchPath } from '@/utils/scratch-path'
import type { FieldState } from '@/types/plate'
import { getEndpointFull } from '@/composables/useEndpointFull'
import { useInjectableSurface } from '@/composables/useInjectableSurface'
import JsonPathInput from '@/components/composer/JsonPathInput.vue'
import SurfaceNotice from '@/components/composer/SurfaceNotice.vue'
import { composerUrl, scenarioAssertionsUrl } from '@/utils/links'
import { showError } from '@/utils/errorFallback'

const route = useRoute()
const router = useRouter()
const scenarioId = route.params.scenarioId as string

const draft = ref<ScenarioDraft | null>(null)
const registry = ref<AssertionRegistry>({ entries: [] })
const selectedId = ref<string | null>(null)

/** 聚焦单条:`?entry=<id>` 命中且可编辑 ⇒ 只渲染该条详情,条目列表与
 *  手工新建栏收起(测试数据页点某一行进来走这条)。**指不到东西就安静
 *  回落**全量视图 —— id 不存在、或指向旧版条目(旧版本就不可编辑,
 *  不能假装能编);回落不报错,列表照常可用。 */
const focusedEntry = computed<AssertionEntry | null>(() => {
  const q = route.query.entry
  const id = typeof q === 'string' && q ? q : null
  if (!id) return null
  const e = registry.value.entries.find((x) => x.id === id)
  return e && !isLegacyEntry(e) ? e : null
})
/** 聚焦态打开的是哪一条(全量态走 selectedId) */
const selected = computed(() =>
  focusedEntry.value ?? registry.value.entries.find((e) => e.id === selectedId.value) ?? null)
const focusMode = computed(() => focusedEntry.value !== null)
const stepCount = computed(() => draft.value?.definition.steps?.length ?? 0)
const steps = computed(() => (draft.value?.definition.steps ?? []) as Array<Record<string, unknown>>)
const stepLabels = computed(() =>
  steps.value.map((s, i) => `${i + 1}·${(s as any)?.description || `Step ${i + 1}`}`),
)
const scenarioName = computed(() => draft.value?.definition?.meta?.name || scenarioId)

/** 判定面(spec 架构收敛 §2.1):可注入面 / 悬空判定 / 契约在途信号唯一来源
 *  = useInjectableSurface;本页只消费(与 RunPanelHost/CaseComposer 同源)。
 *  行内「悬空」标注读**门控后死集** —— 契约未落定期间不把契约依赖条目判死
 *  (与运行面板的禁选同口径;`deadOf` 的原始 issue 明细只用于 tooltip 文案)。 */
const surface = useInjectableSurface(steps, computed(() => registry.value.entries))
onMounted(() => surface.ensure())
/** 悬空判定薄壳(模板按布尔消费 class/title/徽标;口径 = 门控后死集) */
const deadOf = (e: AssertionEntry | LegacyAssertionEntry) =>
  surface.deadIds.value.includes(e.id)
const deadCount = computed(() => registry.value.entries.filter(deadOf).length)

/** 判定面提示位:降级 / 换面两态共用(见模板注释)。二者都只提示,不阻断。 */
const changedAcknowledged = ref(false)
/** 换面提示是会话粘性的 ⇒ 呈现位给一个「看过了」的关闭口(仅本视图、本次挂载) */
function acknowledgeChanged() {
  changedAcknowledged.value = true
}
const notice = computed<{ kind: 'degraded' | 'changed'; text: string } | null>(() => {
  if (surface.degraded.value) {
    return {
      kind: 'degraded',
      text: '契约取数失败 —— 判定面退回从严(悬空条目不可勾选);可重试恢复',
    }
  }
  if (surface.surfaceChanged.value && !changedAcknowledged.value) {
    return {
      kind: 'changed',
      text: '契约已更新 —— 判定已按新面重算(因新面悬空的条目已标灰)',
    }
  }
  return null
})

/** 手动重试:走判定面的取数口 `ensure()`(渲染期仍零请求 —— 视图侧只有这一次显式动作取数)。
 *  **`force`**:显式用户动作不受共享缓存的 TTL / 失败负缓存约束 —— 负缓存抑制的是
 *  无人看管时的反复重发,一个点了没反应的「重试」比没有按钮更糟。
 *  按钮不给 busy 态:`ensure()` 同步返回、取数在缓存内进行,失败态本身由
 *  `degraded` 如实驱动(恢复即消失),不谎报一个观察不到的状态。 */
function retryDegraded() {
  surface.ensure({ force: true })
}

/** 旧版条目不可选(不可编辑,spec v3 §8) */
function selectEntry(e: AssertionEntry | LegacyAssertionEntry) {
  if (isLegacyEntry(e)) return
  selectedId.value = e.id
}

/** 聚焦态 → 全量视图:清掉 query(条目列表与手工新建栏回来)。
 *  用 push 不用 replace —— 浏览器后退能回到刚才那一条。 */
function exitFocus() {
  router.push(scenarioAssertionsUrl(scenarioId))
}

/** 悬空原因摘要(title 展示):registryIssues 人话投影。
 *  path-unresolvable 的判据是**可注入面**(spec v3.1 §2.1)= body 现存 ∪ 契约
 *  声明 —— 文案必须说全两面,否则「body 无」会让用户以为契约已查过。 */
function issueSummary(e: AssertionEntry | LegacyAssertionEntry): string {
  if (isLegacyEntry(e)) return '旧版条目(v2 形状),请在编排器重新标记创建'
  return surface.deadOf(e)
    .map((iss) => {
      if (iss.kind === 'step-oob') return `第 ${iss.stepIndex + 1} 步不存在(场景共 ${stepCount.value} 步)`
      if (iss.kind === 'path-unresolvable') {
        return `第 ${iss.stepIndex + 1} 步的请求体与接口契约里都没有 ${iss.jsonpath}`
      }
      if (iss.kind === 'override-no-match') {
        // 动作列已改叫「改写已有」—— 这里不得再印 override(两边同改)
        return `第 ${iss.stepIndex + 1} 步没有 ${iss.target} 的断言 —— 「改写已有」没有可改写的对象`
      }
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
/** 监听**打开的是哪一条**(不是 selectedId):聚焦态下 selectedId 恒为 null,
 *  监听它则聚焦进来时值编辑器永不初始化,注入值那一栏是空的。 */
watch(() => selected.value?.id, () => {
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
    return '值为空(null)时送不到执行引擎 —— 导出时会丢掉它,这条用例一加载就失败。'
      + '请改用字符串表达(如空串 或 "null"),或删除本条。'
  }
  if (typeof v !== 'string') return ''
  if (v.startsWith('${') && v.endsWith('}')) {
    return '整串 ${...} 会被当作**变量引用**先展开,不是在运行时才替换:'
      + '共享变量里没有同名变量 → 这条用例在开始前就失败;'
      + '有同名变量 → 实际写入的是**变量的值**,不是这里填的字面量。'
  }
  if (v.startsWith('$.')) {
    return '以 $. 开头会被当作**路径**先去场景上下文里读,读不到才用这里的字面量兜底;'
      + '若上下文里恰好有同名路径,会被它覆写。'
  }
  return ''
})

/** 手工新建暂存:步骤 + 注入路径(不预设模板化) */
const pendingPath = ref({ stepIndex: 0, jsonpath: '' })
/** 绑定断言行编辑暂存(mode 字符串形态,入条目时收窄)。
 *  **默认 `append`**:新建一条绑定时选「改写已有」是没有对象的 —— 那一条会
 *  静默无效(见 addAssert 的拦截)。默认值必须落在恒成立的那一侧。 */
const pendingAssert = ref({ stepIndex: 0, target: '', operator: 'eq', expected: '', mode: 'append' as string })
const OPERATORS = ['eq', 'ne', 'gt', 'ge', 'lt', 'le', 'contains', 'exists']

/** 请求侧候选(spec v3.1 §2.1)= 可注入面(body 现存 ∪ 契约声明全状态)。
 *  body 源:headers 是协议位,v1 path 不支持(spec v3 §1 裁定 9)。 */
const pathCandidates = computed<string[]>(() => [
  ...surface.pathsOfStep(pendingPath.value.stepIndex),
])

/** 所选步骤上**已存在**的断言目标(scratch 域)= 「改写已有」的匹配面。
 *  判据与后端 `compose_injection_scenario` 的 override 分支同源
 *  (kind==='assertion' 且 target 相等);取步容错(越界 / 畸形 ⇒ 空集,
 *  与 registryIssues 的 `_step_at` 同口径 —— 判死不在这里)。 */
const existingAssertTargets = computed<Set<string>>(() => {
  const step = steps.value[pendingAssert.value.stepIndex] as Record<string, unknown> | undefined
  const strat = Array.isArray(step?.strategy) ? (step.strategy as unknown[]) : []
  return new Set(
    strat
      .filter((s): s is Record<string, unknown> => !!s && typeof s === 'object')
      .filter((s) => s.kind === 'assertion')
      .map((s) => String(s.target)),
  )
})

/** 建议行状态标注薄壳:判定面按步取态(composable 的 stateOf 显式收 si,
 *  候选来自"当前待选步骤",该下标就在本页手里)。 */
function stateOfPendingPath(path: string): FieldState | undefined {
  return surface.stateOf(pendingPath.value.stepIndex, path)
}

/** asserts.target 候选 = 所选步骤**端点契约**的 assertable 面,经 toScratchPath
 *  归一到引擎域($.code → $.response_body.code)。契约是响应侧唯一标准定义
 *  —— 不引入样本等旁路;契约未声明的字段仍可手打,只是不提示。
 *  **纯缓存读**(裁定 C19):不在此处 ensure —— 取数由 `surface.ensure()` 一次取全
 *  (覆盖全部带 endpoint_id 的步骤),渲染期只读缓存(读 `shallowReactive`
 *  容器即建立响应依赖,契约落定后本 computed 自动重算)。 */
const targetCandidates = computed<string[]>(() => {
  const step = steps.value[pendingAssert.value.stepIndex] as any
  const eid = step?.api?.view_hints?.endpoint_id
  if (!eid) return []
  const full = getEndpointFull(eid)
  return assertablePaths(full?.responses?.['200']?.declarations).map(toScratchPath)
})

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
    ElMessage.warning('注入路径需以 $ 开头(例:$.amount)')
    return
  }
  const e: AssertionEntry = {
    id: genEntryId(),
    // 名字就用注入路径 —— 三元组的第一个元素本身就是这条记录的身份。
    // 不另发明编号(编号没有信息量),也不用「偏离」(对还没有注入面的草稿是假话)。
    name: pendingPath.value.jsonpath,
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
  if (!selected.value || isLegacyEntry(selected.value)) return
  // 绑定断言的两项必备内容,缺了就落不了条目 —— 但**必须出声**:按钮就在那儿
  // 摆着,静默 return 等于「点了没反应」,用户无从知道差什么(与 addEntry 同口径)
  if (!pendingAssert.value.target) {
    ElMessage.warning('要先填「断言哪个响应字段」(例:$.response_body.code)')
    return
  }
  const mode = pendingAssert.value.mode === 'append' ? 'append' : 'override'
  // 「改写已有」的匹配面 = 该步骤上**已存在**的断言目标(与后端
  // compose_injection_scenario 的 override 分支同判据)。没有可改写的对象时
  // 后端什么都不做 —— 落下去就是一条静默无效的绑定,故在此拦下并说清差什么。
  if (mode === 'override' && !existingAssertTargets.value.has(pendingAssert.value.target)) {
    ElMessage.warning(
      '「改写已有」只对步骤上已存在的同目标断言生效 —— 这一步没有该目标的断言,'
      + '这条会什么都不做。要新增请选「新增一条」',
    )
    return
  }
  selected.value.asserts.push({
    stepIndex: pendingAssert.value.stepIndex,
    target: pendingAssert.value.target,
    operator: pendingAssert.value.operator,
    expected: pendingAssert.value.expected,
    mode,
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
  max-width: 1080px; min-height: 100vh;
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
/* 聚焦态的删除口(全量态不出,删除仍由列表行的 × 承担) */
.are-del-focus {
  margin-left: auto; padding: 3px 10px; font-size: 12px;
  color: #dc2626; background: #fff; border: 1px solid #fecaca; border-radius: 4px;
  cursor: pointer; white-space: nowrap;
}
.are-del-focus:hover { background: #fef2f2; border-color: #ef4444; }
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
