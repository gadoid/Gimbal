<script setup lang="ts">
/** 方案工作台壳:左右分栏、取数编排、选中态;编辑区 = 数据区(Task 5)+ 后续任务区。 */
import { computed, onMounted, ref, toRaw, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listRunSchemes, getScenarioDraft, listDataSets, createRunScheme, updateRunScheme,
  type SchemeV2,
} from '@/api/scenario-composer'
import type { DataSetSummary } from '@/types/scenario-composer'
import { composerUrl } from '@/utils/links'
import SchemeListPanel from '@/components/schemes/SchemeListPanel.vue'
import SchemeDataSection from '@/components/schemes/SchemeDataSection.vue'

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
      getScenarioDraft(scenarioId),   // steps/registry 后续任务消费
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
          <p v-else class="hint">默认方案不可编辑数据区(始终全量基线执行)。</p>
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
