<script setup lang="ts">
/** 方案工作台壳:左右分栏、取数编排、选中态;编辑区 = 数据区(Task 5)+ 后续任务区。 */
import { computed, onMounted, ref, toRaw, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listRunSchemes, getScenarioDraft, listDataSets, createRunScheme, updateRunScheme,
  deleteRunScheme, updateScenario, type SchemeV2,
} from '@/api/scenario-composer'
import { list as listAuthSessions } from '@/api/auth_sessions'
import { confirmAction, promptAction } from '@/utils/confirmAction'
import type { DataSetSummary, ScenarioDraft } from '@/types/scenario-composer'
import type { AssertionEntry, AssertionRegistry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'
import { genEntryId, normalizeRegistry } from '@/utils/assertion-registry'
import { useInjectableSurface } from '@/composables/useInjectableSurface'
import { composerUrl, scenarioAssertionsUrl } from '@/utils/links'
import SchemeListPanel from '@/components/schemes/SchemeListPanel.vue'
import SchemeDataSection from '@/components/schemes/SchemeDataSection.vue'
import SchemeInjectionSection from '@/components/schemes/SchemeInjectionSection.vue'
import SchemeRunConfigSection from '@/components/schemes/SchemeRunConfigSection.vue'

const route = useRoute()
const router = useRouter()
const scenarioId = route.params.scenarioId as string

const loading = ref(false)
const schemes = ref<SchemeV2[]>([])
const selectedId = ref<string | null>(null)
const dataSets = ref<DataSetSummary[]>([])

const selected = computed(() =>
  schemes.value.find((s) => s.schemeId === selectedId.value) ?? null)

// ── 编辑草稿 + 脏态 + 保存/放弃(Task 5,供 Task 6/7 复用)────────────
const dirty = ref(false)
const draft = ref<SchemeV2 | null>(null)
const saving = ref(false)

// 选中变化 → 草稿快照(structuredClone 断开引用;toRaw 拿原始对象再克隆)。
// dirty watch 用 flush:'sync':快照赋值同步触发一次 dirty=true,
// 随后一行 dirty=false 收尾,保证「选中/放弃/保存后」脏态确定为 false。
watch(selected, (s) => {
  draft.value = s ? structuredClone(toRaw(s)) : null
  dirty.value = false
}, { immediate: true })
watch(draft, () => { dirty.value = true }, { deep: true, flush: 'sync' })

async function saveScheme() {
  if (!draft.value || saving.value) return
  saving.value = true
  try {
    // omit(schemeId/isDefault) 用解构实现 — PUT 体不带主键与系统位
    const { schemeId: _s, isDefault: _d, ...body } = draft.value
    await updateRunScheme(scenarioId, draft.value.schemeId, body)
    await refresh()
    draft.value = selected.value ? structuredClone(toRaw(selected.value)) : null
    dirty.value = false
    ElMessage.success('方案已保存')
  } catch (e) {
    ElMessage.error(`保存方案失败:${e instanceof Error ? e.message : String(e)}`)
  } finally {
    saving.value = false
  }
}

function discardDraft() {
  draft.value = selected.value ? structuredClone(toRaw(selected.value)) : null
  dirty.value = false
}

// ── 断言注入区(Task 6)──────────────────────────────────────────────
/** 场景 draft 载荷留存(原 onMounted 只消费 dataSets):注入区的 steps/registry
 *  派生与快建保存(updateScenario 整包 PUT 需 definition/orchestration 原样
 *  透传,与 AssertionRegistryEditor.save 同机制)都吃它。 */
const scenarioDraft = ref<ScenarioDraft | null>(null)
const registry = ref<AssertionRegistry>({ entries: [] })
const steps = computed(() =>
  (scenarioDraft.value?.definition.steps ?? []) as Array<Record<string, unknown>>)

/** 判定面唯一消费面(spec §2.1):死集/契约在途信号只从这里出,本页不复刻。 */
const surface = useInjectableSurface(steps, computed(() => registry.value.entries))
onMounted(() => surface.ensure())

/** 注入区条目行:id + 步骤/jsonpath 摘要(旧形状条目无 path,用 name 摘要)。 */
const injectionEntries = computed(() => registry.value.entries.map((e) => ({
  id: e.id,
  label: isLegacyEntry(e) ? (e.name || e.id) : `步骤${e.path.stepIndex} ${e.path.jsonpath}`,
})))
/** 死条目集:surface.deadIds 是数组,组件 prop 收 Set(受控口径)。 */
const injectionDeadIds = computed(() => new Set(surface.deadIds.value))

const registrySaving = ref(false)

/** 快建落库:条目造形抄 CaseComposer.onRegistryAdd 请求侧(id=genEntryId /
 *  name=jsonpath / path 三元组 source='body' / value 空串预填 / asserts 空);
 *  保存机制与 AssertionRegistryEditor.save 同款 —— 整体 PUT,只动
 *  assertion_registry 键,definition/orchestration 原样透传。
 *  失败回调化(§13 T6-1):结果经 onDone 回传组件 — 成功 true 才关弹层,
 *  失败 false 弹层保持打开、输入保留(不再乐观关闭吞掉用户输入)。 */
async function onQuickCreate(
  q: { stepIndex: number; jsonpath: string },
  onDone: (ok: boolean) => void,
) {
  if (!scenarioDraft.value) {
    ElMessage.error('快建条目失败:场景草稿未加载')
    onDone(false)
    return
  }
  if (registrySaving.value) { onDone(false); return }
  registrySaving.value = true
  try {
    const entry: AssertionEntry = {
      id: genEntryId(),
      name: q.jsonpath,
      path: { stepIndex: q.stepIndex, source: 'body', jsonpath: q.jsonpath },
      value: '',
      asserts: [],
    }
    const next: AssertionRegistry = { entries: [...registry.value.entries, entry] }
    await updateScenario(scenarioId, { ...scenarioDraft.value, assertion_registry: next })
    registry.value = next
    scenarioDraft.value = { ...scenarioDraft.value, assertion_registry: next }
    // 写入注册表并自动勾选:深 watch 即脏,随方案「保存」落库
    if (draft.value && !draft.value.injectionEntryIds.includes(entry.id)) {
      draft.value.injectionEntryIds.push(entry.id)
    }
    ElMessage.success('已快建断言条目并勾选(记得保存方案)')
    onDone(true)
  } catch (e) {
    ElMessage.error(`快建条目失败:${e instanceof Error ? e.message : String(e)}`)
    onDone(false)
  } finally {
    registrySaving.value = false
  }
}

function onManageAssertions() {
  router.push(scenarioAssertionsUrl(scenarioId))
}

// ── 运行配置区(Task 7):绑定行/别名选项派生 + 凭证池 ───────────────
/** 绑定行 = 声明 ∪ 引用并集(spec D3)— 逻辑镜像 RunPanelHost.serviceRows:
 *  声明行来自 definition.config.services(字符串值 = 声明 URL),引用行来自
 *  steps[].api.service(未声明 → declaredUrl null,可 URL 救燃)。 */
const serviceRows = computed(() => {
  const declared = (scenarioDraft.value?.definition.config as
    { services?: Record<string, unknown> } | undefined)?.services ?? {}
  const rows = new Map<string, string | null>()
  for (const [k, v] of Object.entries(declared)) rows.set(k, typeof v === 'string' ? v : null)
  for (const st of steps.value) {
    const svc = (st as { api?: { service?: string } })?.api?.service
    if (svc && !rows.has(svc)) rows.set(svc, null)
  }
  return [...rows].map(([service, declaredUrl]) => ({ service, declaredUrl }))
})

/** 别名选项:owner 凭证池 ∪ 场景内置 users 别名(RunPanelHost.authOptions 同构) */
const authAliases = ref<string[]>([])
const authOptions = computed(() => {
  const users = Object.keys(((scenarioDraft.value?.definition.config as
    { users?: Record<string, unknown> } | undefined)?.users) ?? {})
  return [...new Set([...authAliases.value, ...users])]
})

/** stepTo 钳位上限(0..stepCount;留空 = 全量) */
const stepCount = computed(() => steps.value.length)
/** stepTo 下拉的步骤名(orchestration 平台编排态;plate Step 无 name) */
const stepNames = computed<string[]>(() =>
  (scenarioDraft.value?.orchestration?.steps ?? []).map((s: { name?: string }) => s.name ?? ''))

// ── 左栏操作(Task 7):重命名 / 复制派生 / 删除 ──────────────────────
/** 操作前的脏态闸:三个操作都会 refresh → schemes 换新引用 → watch(selected)
 *  重快照 → 未保存修改静默丢(无论操作目标是否为当前选中),脏态下先确认。 */
async function confirmDiscardForOps(): Promise<boolean> {
  if (!dirty.value) return true
  try {
    await ElMessageBox.confirm('当前方案有未保存的修改,此操作将刷新列表并放弃这些修改。',
      '未保存修改', { type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '取消操作' })
    return true
  } catch {
    return false
  }
}

/** 重命名:prompt 新名 → 以存储载荷(name 除外)整包 PUT → 刷新。 */
async function onRename(s: SchemeV2) {
  if (!(await confirmDiscardForOps())) return
  const name = await promptAction('方案名称', '重命名方案', { inputValue: s.name })
  if (name === null) return
  const trimmed = name.trim()
  if (!trimmed) {
    ElMessage.warning('方案名不能为空')
    return
  }
  try {
    const { schemeId: _s, isDefault: _d, ...body } = s
    await updateRunScheme(scenarioId, s.schemeId, { ...body, name: trimmed })
    await refresh()
    ElMessage.success('方案已重命名')
  } catch (e) {
    ElMessage.error(`重命名失败:${e instanceof Error ? e.message : String(e)}`)
  }
}

/** 复制派生:深拷贝载荷 + 原名「 副本」→ create → 刷新并选中新副本。 */
async function onDuplicate(s: SchemeV2) {
  if (!(await confirmDiscardForOps())) return
  try {
    const { schemeId: _s, isDefault: _d, ...body } = structuredClone(toRaw(s))
    const made = await createRunScheme(scenarioId, { ...body, name: `${s.name} 副本` })
    await refresh()
    selectedId.value = made.schemeId
    ElMessage.success('已复制派生方案')
  } catch (e) {
    ElMessage.error(`复制派生失败:${e instanceof Error ? e.message : String(e)}`)
  }
}

/** 删除:confirmAction 确认 → deleteRunScheme → 刷新;删中选中项回落置顶
 *  (default)。405 = default 系统位不可删(左栏本就不给入口,此处兜底)。 */
async function onDelete(s: SchemeV2) {
  if (!(await confirmDiscardForOps())) return
  const ok = await confirmAction(`删除方案「${s.name}」?此操作不可恢复。`, '删除方案',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  if (!ok) return
  try {
    await deleteRunScheme(scenarioId, s.schemeId)
    await refresh()
    if (selectedId.value === s.schemeId) selectedId.value = schemes.value[0]?.schemeId ?? null
    ElMessage.success('方案已删除')
  } catch (e) {
    if ((e as { status?: number })?.status === 405) ElMessage.warning('默认方案不可删除')
    else ElMessage.error(`删除方案失败:${e instanceof Error ? e.message : String(e)}`)
  }
}

/** 切换选中:脏态下先确认丢弃(cancel 走 reject,吞掉留在原方案)。 */
async function onSelect(id: string) {
  if (id === selectedId.value) return
  if (dirty.value) {
    try {
      await ElMessageBox.confirm('当前方案有未保存的修改,切换将放弃这些修改。', '未保存修改',
        { type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '留在本方案' })
    } catch {
      return
    }
  }
  selectedId.value = id
}

async function refresh() {
  loading.value = true
  try {
    schemes.value = await listRunSchemes(scenarioId)
    if (!selectedId.value && schemes.value.length)
      selectedId.value = (route.query.scheme as string)
        || schemes.value[0].schemeId  // default 置顶
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  if (!(await confirmDiscardForOps())) return   // 脏态闸同 rename/duplicate/delete(终审 M-1)
  try {
    const made = await createRunScheme(scenarioId, {
      name: `方案 ${schemes.value.length}`, dataSetSelection: [],
      injectionEntryIds: [], serviceBindings: {},
      stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
    })
    await refresh()
    selectedId.value = made.schemeId
  } catch (e) {
    ElMessage.error(`新建方案失败:${e instanceof Error ? e.message : String(e)}`)
  }
}

onMounted(async () => {
  await refresh()
  // owner 凭证池(运行配置区别名下拉)— RunPanelHost 同款:await + try,
  // 取不到不阻塞工作台(list 内 http 异常含同步抛,await-in-try 才兜得住)
  try {
    authAliases.value = (await listAuthSessions()).map((a) => a.alias)
  } catch { /* 凭证池不可达不阻塞 */ }
  try {
    await Promise.all([
      // draft 载荷留存(Task 6):注入区 steps/registry 与快建整包 PUT 都吃它;
      // registry 归一(旧场景该键后端 default 补 {},?? 兜不住 — 与编辑器同款)
      getScenarioDraft(scenarioId).then((d) => {
        scenarioDraft.value = d
        registry.value = normalizeRegistry(d.assertion_registry)
      }),
      // listDataSets 收对象参数:{ scenarioId?: string }(api/scenario-composer.ts)
      listDataSets({ scenarioId }).then((d) => { dataSets.value = d }),
    ])
  } catch (e) {
    ElMessage.error(`加载场景失败:${e instanceof Error ? e.message : String(e)}`)
  }
})
</script>

<template>
  <section class="scheme-workbench">
    <header class="page-header">
      <div>
        <h2 class="page-title">方案工作台</h2>
        <p>场景 <code class="sid">{{ scenarioId }}</code></p>
      </div>
      <div class="header-actions">
        <el-button @click="router.push(composerUrl(scenarioId))">编排器</el-button>
      </div>
    </header>
    <div class="wb-body">
      <SchemeListPanel
        :schemes="schemes"
        :selected-id="selectedId"
        :loading="loading"
        @select="onSelect"
        @create="onCreate"
        @rename="onRename"
        @duplicate="onDuplicate"
        @delete="onDelete"
      />
      <div class="wb-editor">
        <template v-if="draft">
          <header class="editor-head">
            <div class="editor-title">
              <h3>{{ draft.name }}</h3>
              <span class="save-state" :class="dirty ? 'is-dirty' : 'is-clean'">
                {{ dirty ? '未保存' : '已保存' }}
              </span>
            </div>
            <div class="editor-ops">
              <el-button data-testid="save-scheme" type="primary" size="small"
                :disabled="!dirty" :loading="saving" @click="saveScheme">保存</el-button>
              <el-button data-testid="discard-scheme" size="small"
                :disabled="!dirty" @click="discardDraft">放弃</el-button>
              <!-- 阶段③:RunDialog v2 深链 — ?runScheme= 选中方案 id,编排器
                   onMounted 打开弹窗并预选(读后 replace 清 query)。composerUrl
                   已含 ?step=1,故用 & 追加。dirty 禁用:跑的须与看见的一致 -->
              <el-button type="primary" data-testid="run-scheme"
                :disabled="dirty" title="先保存再运行"
                @click="router.push(composerUrl(scenarioId) + '&runScheme=' + encodeURIComponent(draft.schemeId))">▶ 运行此方案</el-button>
            </div>
          </header>
          <SchemeDataSection
            v-if="!draft.isDefault"
            v-model="draft.dataSetSelection"
            :data-sets="dataSets"
            :scenario-id="scenarioId"
          />
          <SchemeInjectionSection
            v-if="!draft.isDefault"
            v-model="draft.injectionEntryIds"
            :entries="injectionEntries"
            :dead-ids="injectionDeadIds"
            :locked="registrySaving"
            @quick-create="onQuickCreate"
            @manage="onManageAssertions"
          />
          <p v-if="draft.isDefault" class="hint">默认方案不可编辑数据区(始终全量基线执行)。</p>
          <!-- 运行配置区:所有方案可见(default 亦然,spec §6)— 绑定/参数/
               预埋均为方案级字段;变更经 update:* 直写 draft,深 watch 即脏 -->
          <SchemeRunConfigSection
            v-if="draft"
            v-model:service-bindings="draft.serviceBindings"
            v-model:step-to="draft.stepTo"
            v-model:n-runs="draft.nRuns"
            v-model:parallel="draft.parallel"
            v-model:plugins="draft.plugins"
            v-model:log-sub="draft.logSub"
            :service-rows="serviceRows"
            :auth-options="authOptions"
            :step-count="stepCount"
            :step-names="stepNames"
          />
        </template>
        <div v-else class="wb-empty">
          <el-empty description="选择左侧方案">
            <el-button type="primary" plain @click="onCreate">+ 新建方案</el-button>
          </el-empty>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* 页面容器:对齐平台视图容器(AssertionRegistryEditor / DataSetEditor 同款) */
.scheme-workbench {
  max-width: 1480px; min-height: calc(100vh - 48px);
  padding: 28px 32px 48px; margin: 0 auto; box-sizing: border-box;
}
.page-header {
  display: flex; gap: 24px; align-items: center;
  justify-content: space-between; margin-bottom: 16px;
}
.page-header h2 { margin: 0; font-size: 22px; color: var(--color-text-primary); }
.page-header p { margin: 5px 0 0; font-size: 12px; color: var(--color-text-secondary); }
.page-header code.sid {
  padding: 1px 4px; font-family: var(--font-mono); font-size: 11px;
  background: var(--accent-soft); border-radius: 3px;
}
.header-actions { display: flex; gap: 8px; }

.wb-body {
  display: grid; grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 20px; align-items: start; min-height: 400px;
}
/* 编辑区:外框退役 — 各分区自带卡片,直接以统一节奏(16px)排列 */
.wb-editor { display: flex; flex-direction: column; gap: 16px; min-width: 0; }

/* 编辑头:方案名 + 保存状态 + 操作(底边框分隔,AssertionRegistryEditor 详情头同款) */
.editor-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding-bottom: 12px; border-bottom: 1px solid var(--color-border-tertiary);
}
.editor-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
.editor-title h3 {
  margin: 0; font-size: 16px; font-weight: 700; color: var(--color-text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
/* 保存状态:脏 = 平台 warn tag(amber),净 = muted tag */
.save-state {
  flex: none; font-size: 11px; font-weight: 600;
  padding: 1px 6px; border-radius: 3px; white-space: nowrap;
}
.save-state.is-dirty { color: #b45309; background: #fef3c7; }
.save-state.is-clean { color: var(--color-text-secondary); background: #f1f5f9; }
.editor-ops { display: flex; gap: 8px; flex: none; }

.hint { margin: 0; padding: 8px 12px; font-size: 12px; color: var(--color-text-secondary); background: #f8fafc; border-radius: 6px; }
.wb-empty { background: #fff; border: 1px dashed var(--color-border-tertiary); border-radius: 8px; }
@media (max-width: 1280px) { .wb-body { grid-template-columns: minmax(0, 1fr); } }
</style>
