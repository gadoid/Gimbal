<script setup lang="ts">
/** 方案工作台壳:左右分栏、取数编排、选中态;编辑区 = 数据区(Task 5)+ 后续任务区。 */
import { computed, onMounted, ref, toRaw, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listRunSchemes, getScenarioDraft, listDataSets, createRunScheme, updateRunScheme,
  updateScenario, type SchemeV2,
} from '@/api/scenario-composer'
import type { DataSetSummary, ScenarioDraft } from '@/types/scenario-composer'
import type { AssertionEntry, AssertionRegistry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'
import { genEntryId, normalizeRegistry } from '@/utils/assertion-registry'
import { useInjectableSurface } from '@/composables/useInjectableSurface'
import { composerUrl, scenarioAssertionsUrl } from '@/utils/links'
import SchemeListPanel from '@/components/schemes/SchemeListPanel.vue'
import SchemeDataSection from '@/components/schemes/SchemeDataSection.vue'
import SchemeInjectionSection from '@/components/schemes/SchemeInjectionSection.vue'

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
 *  assertion_registry 键,definition/orchestration 原样透传。 */
async function onQuickCreate(q: { stepIndex: number; jsonpath: string }) {
  if (!scenarioDraft.value || registrySaving.value) return
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
  } catch (e) {
    ElMessage.error(`快建条目失败:${e instanceof Error ? e.message : String(e)}`)
  } finally {
    registrySaving.value = false
  }
}

function onManageAssertions() {
  router.push(scenarioAssertionsUrl(scenarioId))
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
      />
      <div class="wb-editor">
        <template v-if="draft">
          <header class="editor-head">
            <h3>{{ draft.name }}</h3>
            <div class="editor-ops">
              <el-button data-testid="save-scheme" type="primary" size="small"
                :disabled="!dirty" :loading="saving" @click="saveScheme">保存</el-button>
              <el-button data-testid="discard-scheme" size="small"
                :disabled="!dirty" @click="discardDraft">放弃</el-button>
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
        </template>
        <el-empty v-else description="选择左侧方案" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.wb-body { display: grid; grid-template-columns: minmax(260px, 340px) minmax(0, 1fr); gap: 16px; min-height: 500px; }
.wb-editor { border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.editor-head { display: flex; align-items: center; justify-content: space-between; }
.editor-head h3 { margin: 0; }
.editor-ops { display: flex; gap: 8px; }
@media (max-width: 1280px) { .wb-body { grid-template-columns: minmax(0, 1fr); } }
</style>
