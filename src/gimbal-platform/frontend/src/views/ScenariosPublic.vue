<!-- ScenariosPublic.vue — 场景库 / 公共场景(统一模板库)。
     原 Scenarios.vue「公共编排」tab 拆出独立页:只读浏览 + 复用。
     无新建入口;操作合并为 ⋯(执行 / 复制到我的)。定义本身只读。 -->
<template>
  <section class="slib">
    <PageHead
      icon="globe"
      title="公共场景"
      subtitle="团队共享的场景,定义本身只读:可直接执行(锁定默认 config)做验证,或“复制到我的”后再编辑"
    />

    <div class="slib-toolbar">
      <input v-model="q" class="slib-search" data-testid="pub-search"
        placeholder="按名 / 模块 / 系统 / scenarioId / tag 搜索" />
      <FilterPopover v-model="filters" :pool="filterableRows" />
    </div>

    <div v-if="store.scenariosStatus === 'loading'" class="slib-loading">加载中…</div>

    <div v-else-if="paged.length" class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th>场景名</th>
            <th style="width:120px">系统</th>
            <th style="width:90px">模块</th>
            <th style="width:70px" class="c-center">优先级</th>
            <th style="width:110px">作者</th>
            <th style="width:70px" class="c-center">被复制</th>
            <th style="width:100px">最后编辑</th>
            <th>Tags</th>
            <th style="width:56px" class="c-center">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in paged" :key="row.meta.scenarioId" class="slib-row" :class="{ 'row-expired': row.meta.expire }">
            <td>
              <div class="sl-name">
                <StarToggle :starred="!!row.starred" @toggle="toggleStar(row)" />
                <span class="nm-plain" :title="row.meta.name || row.meta.scenarioId">{{ row.meta.name || row.meta.scenarioId }}</span>
              </div>
              <div class="sl-sid">{{ row.meta.scenarioId }}</div>
              <div v-if="row.meta.description" class="sl-desc">{{ row.meta.description }}</div>
            </td>
            <td><div class="sys-list"><SystemChip v-for="sys in row.meta.system" :key="sys" :sys="sys" /></div></td>
            <td><TagPill :label="row.meta.module || '未分类'" /></td>
            <td class="c-center"><PriorityPill :priority="row.meta.priority" /></td>
            <td><span class="author">{{ row.meta.author || row.meta.owner || '—' }}</span></td>
            <!-- 被复制:当前数据结构无复制计数字段,如实留白 -->
            <td class="c-center"><span class="muted">—</span></td>
            <td><span class="muted">{{ formatTime(row.meta?.updateTime) }}</span></td>
            <td>
              <div v-if="row.tags.length" class="sys-list">
                <TagPill v-for="t in row.tags.slice(0, MAX)" :key="t" :label="t" tone="accent" />
                <TagPill v-if="row.tags.length > MAX" :label="`+${row.tags.length - MAX}`" />
              </div>
              <span v-else class="muted">—</span>
            </td>
            <td class="c-center">
              <DropdownMenu>
                <DropdownMenuTrigger class="more-btn" :data-testid="`pub-more-${row.meta.scenarioId}`" @click.stop>⋯</DropdownMenuTrigger>
                <DropdownMenuContent align="end" class="sl-menu">
                  <DropdownMenuItem class="sl-menu-item" :data-testid="`pub-run-${row.meta.scenarioId}`" @click="runPublic(row)">执行</DropdownMenuItem>
                  <DropdownMenuItem class="sl-menu-item" :data-testid="`pub-copy-${row.meta.scenarioId}`" @click="copyToMine(row)">复制到我的</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="slib-empty">
      <p>暂无公共场景 — 团队共享的模板会出现在这里</p>
    </div>

    <div v-if="total > pageSize" class="pager">
      <button type="button" class="pg-btn" :disabled="page <= 1" @click="page--">&#8249;</button>
      <button v-for="p in pageCount" :key="p" type="button" class="pg-btn" :class="{ active: p === page }" @click="page = p">{{ p }}</button>
      <button type="button" class="pg-btn" :disabled="page >= pageCount" @click="page++">&#8250;</button>
      <span class="pg-total">共 {{ total }} 条</span>
    </div>

    <p class="slib-note">
      公共场景没有「+ 新建场景」——创建永远发生在我的场景,这里只做浏览/复用,避免两套编排入口混淆。公共场景不暴露「方案」这个概念——直接用 config 里写好的默认配置跑,没有多方案可选。要跑不同参数组合,先「复制到我的」再去方案管理拆场景。「执行」和「复制到我的」都收进「⋯」菜单里——执行只会用这个场景锁死的默认 config 跑,不能改参数,主要用途是验证公共场景里定义的步骤能不能正常跑通(尤其是适配中心提示接口有变更的时候,可以直接在这里跑一次确认),不是替代「复制到我的」之后的正式编排使用。
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { toast } from '@/utils/toast'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { listDataSets, runScenario } from '@/api/scenario-composer'
import { useListSearch } from '@/utils/useListSearch'
import { showError } from '@/utils/errorFallback'
import { shortDateTime } from '@/utils/datetime'
import { applyFiltersToList, emptyFilters, type ScenarioFilters } from '@/utils/filters'
import { FOLLOW_CAP } from '@/composables/useFollowLayout'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import StarToggle from '@/components/scenario-lib/StarToggle.vue'
import FilterPopover from '@/components/FilterPopover.vue'
import TagPill from '@/components/TagPill.vue'
import SystemChip from '@/components/SystemChip.vue'
import PriorityPill from '@/components/PriorityPill.vue'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import type { Scenario } from '@/types/scenario-composer'

const MAX = 3
const pageSize = 20

const store = useScenarioComposerStore()

const q = ref('')
const filters = ref<ScenarioFilters>(emptyFilters())
const page = ref(1)

const { filtered } = useListSearch(
  () => store.scenarios,
  ['meta.name', 'meta.scenarioId', 'meta.module', 'meta.description', 'meta.system', 'tags'],
  q,
)

const filterableRows = computed(() =>
  filtered.value.map((s) => ({
    ...s,
    module: s.meta.module,
    author: s.meta.author || s.meta.owner,
    priority: s.meta.priority,
    updated_at: s.meta.updateTime,
    system: s.meta.system,
    tags: s.meta.tags,
  })),
)

const rows = computed(() =>
  (applyFiltersToList(filterableRows.value, filters.value) as typeof filterableRows.value)
    .filter((r) => r.visibility === 'public'),
)
const total = computed(() => rows.value.length)
const pageCount = computed(() => Math.ceil(total.value / pageSize))
const paged = computed(() => {
  const start = (page.value - 1) * pageSize
  return rows.value.slice(start, start + pageSize)
})
watch(total, () => {
  const maxPage = Math.max(1, Math.ceil(total.value / pageSize))
  if (page.value > maxPage) page.value = maxPage
})

const formatTime = shortDateTime

onMounted(async () => {
  try {
    await store.fetchScenarios()
  } catch {
    showError('加载场景', undefined, store.lastError)
  }
})

/** 验证执行:用场景锁死的默认 config 跑一次(其数据集全集,不改参数、
 *  不套方案 → 执行记录无 schemeId,即关注页公共原件的健康趋势来源)。 */
async function runPublic(row: Scenario) {
  const id = row.meta.scenarioId
  try {
    const sets = await listDataSets({ scenarioId: id })
    const res = await runScenario({
      scenarioId: id,
      dataSetIds: sets.map((d) => d.datasetId),
    })
    toast.success(`已发起验证执行 ${res.runId}`)
  } catch (e) {
    toast.error(`执行失败: ${(e as Error).message}`)
  }
}

async function copyToMine(row: Scenario) {
  try {
    const saved = await store.copyScenario(row.meta.scenarioId)
    toast.success(`已复制到我的场景：${saved.meta.name || saved.meta.scenarioId}`)
  } catch (e) {
    showError('复制', undefined, (e as Error).message)
  }
}

async function toggleStar(row: Scenario) {
  if (!row.starred && store.starredScenarios.length >= FOLLOW_CAP) {
    toast.error(`关注上限 ${FOLLOW_CAP} 个 — 请先在关注页取消部分关注`)
    return
  }
  try {
    await store.toggleStar(row.meta.scenarioId)
  } catch (e) {
    showError('关注', undefined, (e as Error).message)
  }
}
</script>

<style scoped>
.sys-list { display: flex; flex-wrap: wrap; gap: 4px; }
.nm-plain {
  font-size: 13px; font-weight: 700; color: #10151c;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 260px;
}
.author { color: #5b6472; }
.row-expired td { opacity: 0.55; }
.pager { display: flex; justify-content: flex-end; align-items: center; margin-top: 12px; }
.pg-btn {
  min-width: 28px; height: 28px; margin-right: 4px;
  font-size: 12px; text-align: center;
  color: #374151; background: #fff;
  border: 1px solid #e1e5eb; border-radius: 6px;
  cursor: pointer;
}
.pg-btn.active { color: #fff; background: #2f6fed; border-color: #2f6fed; font-weight: 600; }
.pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.pg-total { font-size: 11.5px; color: #64748b; margin-left: 6px; }
</style>
