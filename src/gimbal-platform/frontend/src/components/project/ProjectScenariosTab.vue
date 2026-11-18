<!-- ProjectScenariosTab.vue — 项目详情「场景 (用例)」页签(普通项目)。

     A 级批次(2026-11-18)起改用场景库共享骨架 useScenarioListView 的
     project 桶:检索 / FilterPopover(facets 项目口径)/ 筛选分组
     (project 桶,按项目隔离)/ 分页全部下推服务端,与「我的 / 公共
     场景」两页同一套心智模型;「★ 仅看关注」为 project 桶专属附加面
     (starred 服务端过滤)。列面对齐公共场景页:星标 / 系统 / 模块 /
     优先级 / 作者 / 标签 / 最后编辑 / ⋯(查看·执行·复制到我的)。
     公共项目不走本组件(整页复用 ScenariosPublic embedded)。 -->
<template>
  <div>
    <div class="slib-toolbar">
      <!-- 分组态下展示值恒空(生效词是分组名,chip 高亮说明在搜什么) -->
      <input
        :value="searchBox"
        class="slib-search"
        placeholder="按名 / 模块 / 系统 / scenarioId / tag 搜索"
        data-testid="prj-scen-q"
        @input="writeSearch(($event.target as HTMLInputElement).value)"
      />
      <button
        type="button" class="seg-btn" :class="{ on: starred }"
        data-testid="prj-scen-starred" title="仅看已关注(★)"
        @click="starred = !starred"
      >★ 仅看关注</button>
      <FilterPopover v-model="filters" :pool="filterableRows" :facets="facets" />
      <span class="flex-1" />
      <button v-if="canWrite" type="button" class="slib-create" data-testid="prj-scen-new"
              @click="newScenarioInProject">在本项目新建场景</button>
    </div>

    <!-- 筛选分组:project 桶(按项目隔离,存服务端 user_prefs) -->
    <FilterGroups
      :groups="groups"
      :state="groupsState"
      :active-id="activeGroupId"
      :can-save="canSaveGroup"
      :busy="savingGroup"
      @apply="applyGroup"
      @remove="removeGroup"
      @save="saveGroup"
      @retry="loadGroups"
    />

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="paged.length" class="lib-card">
      <table class="slib-table">
        <thead><tr>
          <th>场景信息</th>
          <th style="width:8.125rem">系统</th>
          <th style="width:5.625rem">模块</th>
          <th style="width:4.375rem" class="c-center">优先级</th>
          <th style="width:6.25rem">作者</th>
          <th>Tags</th>
          <th style="width:6.25rem">最后编辑</th>
          <th style="width:3.5rem" class="c-center">操作</th>
        </tr></thead>
        <tbody>
          <tr v-for="r in paged" :key="r.meta.scenarioId" class="slib-row"
              :data-testid="`prj-scen-${r.meta.scenarioId}`"
              @click="openScenario(r.meta.scenarioId)">
            <td>
              <div class="sl-name">
                <StarToggle :starred="!!r.starred" @toggle="toggleStar(r)" />
                <button
                  type="button" class="nm"
                  :data-testid="`prj-scen-name-${r.meta.scenarioId}`"
                  :title="r.meta.name || r.meta.scenarioId"
                  @click.stop="openScenario(r.meta.scenarioId)"
                >{{ r.meta.name || r.meta.scenarioId }}</button>
              </div>
              <div class="sl-sid">{{ r.meta.scenarioId }}</div>
              <div v-if="r.meta.description" class="sl-desc">{{ r.meta.description }}</div>
            </td>
            <td>
              <div class="sys-cell">
                <template v-if="r.meta.system.length">
                  <SystemChip v-for="s in r.meta.system.slice(0, 2)" :key="s" :sys="s" />
                  <span v-if="r.meta.system.length > 2" class="muted">+{{ r.meta.system.length - 2 }}</span>
                </template>
                <span v-else class="muted">—</span>
              </div>
            </td>
            <td><TagPill :label="r.meta.module || '未分类'" /></td>
            <td class="c-center"><PriorityPill :priority="r.meta.priority" /></td>
            <td><span class="muted">{{ r.meta.author || r.meta.owner || '—' }}</span></td>
            <td>
              <div v-if="r.tags.length" class="sys-cell">
                <TagPill v-for="t in r.tags.slice(0, 3)" :key="t" :label="t" tone="accent" />
                <TagPill v-if="r.tags.length > 3" :label="`+${r.tags.length - 3}`" />
              </div>
              <span v-else class="muted">—</span>
            </td>
            <td><span class="muted">{{ formatTime(r.meta.updateTime) }}</span></td>
            <td class="c-center">
              <DropdownMenu>
                <DropdownMenuTrigger class="more-btn" :data-testid="`prj-scen-more-${r.meta.scenarioId}`" @click.stop>⋯</DropdownMenuTrigger>
                <DropdownMenuContent align="end" class="sl-menu">
                  <DropdownMenuItem class="sl-menu-item" :data-testid="`prj-scen-detail-${r.meta.scenarioId}`" @click="openScenario(r.meta.scenarioId)">查看详情</DropdownMenuItem>
                  <DropdownMenuItem class="sl-menu-item" :data-testid="`prj-scen-run-${r.meta.scenarioId}`" @click="runVerify(r)">执行</DropdownMenuItem>
                  <DropdownMenuItem class="sl-menu-item" :data-testid="`prj-scen-copy-${r.meta.scenarioId}`" @click="copyToMine(r)">复制到我的</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="empty-cta">
      <p>{{ filtering
        ? '没有匹配的场景 — 换个关键词,或清掉筛选条件'
        : `本项目还没有场景${canWrite ? ' —— 点右上「在本项目新建场景」开始' : ''}。` }}</p>
    </div>
    <Pagination
      v-if="total > 1"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      show-page-size show-jump
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useScenarioListView } from '@/composables/useScenarioListView'
import { listDataSets, runScenario } from '@/api/scenario-composer'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { scenarioDetailUrl } from '@/utils/links'
import { FollowCapError } from '@/composables/useFollowLayout'
import { shortDateTime } from '@/utils/datetime'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import StarToggle from '@/components/scenario-lib/StarToggle.vue'
import SystemChip from '@/components/SystemChip.vue'
import TagPill from '@/components/TagPill.vue'
import PriorityPill from '@/components/PriorityPill.vue'
import FilterPopover from '@/components/FilterPopover.vue'
import FilterGroups from '@/components/scenario-lib/FilterGroups.vue'
import { Pagination } from '@/components/ui/pagination'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { ScenarioListItem } from '@/types/scenario-composer'

const props = defineProps<{
  projectId: number
  canWrite?: boolean
}>()

const router = useRouter()
const scenStore = useScenarioComposerStore()
const formatTime = shortDateTime

// project 桶:检索/筛选/分页/分组全在共享骨架(与场景库两页同心智模型)
const {
  filters, starred, page, paged, total, loading, filtering,
  filterableRows, facets, load, pageSize,
  searchBox, writeSearch,
  groups, groupsState, savingGroup, activeGroupId, canSaveGroup,
  loadGroups, applyGroup, saveGroup, removeGroup,
} = useScenarioListView('project', { projectId: props.projectId })

onMounted(load)

function newScenarioInProject(): void {
  void router.push({ path: '/composer/new', query: { projectId: String(props.projectId) } })
}
function openScenario(id: string): void {
  void router.push(scenarioDetailUrl(id))
}

/** 验证执行:与公共场景页同款(默认 config 全数据集,无 schemeId) */
async function runVerify(row: ScenarioListItem): Promise<void> {
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

async function copyToMine(row: ScenarioListItem): Promise<void> {
  try {
    const saved = await scenStore.copyScenario(row.meta.scenarioId)
    toast.success(`已复制到我的场景：${saved.meta.name || saved.meta.scenarioId}`)
  } catch (e) {
    showError('复制', undefined, (e as Error).message)
  }
}

/** 星标乐观翻转 + 失败回滚(与公共场景页同款) */
async function toggleStar(row: ScenarioListItem): Promise<void> {
  const next = !row.starred
  row.starred = next
  try {
    await scenStore.toggleStarWithCap(row.meta.scenarioId, next)
  } catch (e) {
    row.starred = !next
    if (e instanceof FollowCapError) toast.error(e.message)
    else showError('关注', undefined, (e as Error).message)
  }
}
</script>

<style scoped>
/* 骨架基座(.slib-toolbar/.slib-table/.lib-card 等)在全局
   scenario-lib.css;这里只补原详情页 scoped 里的页签局部件。 */
.seg-btn {
  padding: 0.4375rem 0.75rem;
  font-size: 0.78125rem;
  cursor: pointer;
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  background: transparent;
  color: var(--sl-ink-2);
}
.seg-btn:hover { color: var(--sl-ink); }
.seg-btn.on { background: var(--sl-accent-soft); color: var(--sl-accent); font-weight: 600; }

.sys-cell { display: flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }
.empty { color: var(--sl-ink-3); margin: 0; }
</style>
