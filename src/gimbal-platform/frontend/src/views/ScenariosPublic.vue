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
      <!-- 分组态下展示值恒空(生效词是分组名,chip 高亮说明在搜什么);
           一敲键盘即退出分组态转手动搜索 -->
      <input
        :value="searchBox"
        class="slib-search"
        data-testid="pub-search"
        placeholder="按名 / 模块 / 系统 / scenarioId / tag 搜索"
        @input="writeSearch(($event.target as HTMLInputElement).value)"
      />
      <FilterPopover v-model="filters" :pool="filterableRows" :facets="facets" />
    </div>

    <!-- 筛选分组:公共库同样适用(浏览大池时把常用条件存成入口) -->
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

    <div v-if="loading" class="slib-loading">加载中…</div>

    <div v-else-if="paged.length" class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th>场景名</th>
            <th style="width:120px">系统</th>
            <th style="width:90px">模块</th>
            <th style="width:70px" class="c-center">优先级</th>
            <th style="width:110px">作者</th>
            <th style="width:70px" class="c-center" title="后端暂无复制次数字段 — 有数据前如实留空,不做估算">被复制</th>
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
                <button
                  type="button"
                  class="nm"
                  :data-testid="`pub-name-${row.meta.scenarioId}`"
                  :title="row.meta.name || row.meta.scenarioId"
                  @click.stop="openDetail(row)"
                >{{ row.meta.name || row.meta.scenarioId }}</button>
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
                  <DropdownMenuItem class="sl-menu-item" :data-testid="`pub-detail-${row.meta.scenarioId}`" @click="openDetail(row)">查看详情</DropdownMenuItem>
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
      <p>{{ filtering
        ? '没有匹配的公共场景 — 换个关键词,或清掉筛选条件'
        : '暂无公共场景 — 团队共享的模板会出现在这里' }}</p>
    </div>

    <Pagination v-model:page="page" :total="total" :page-size="pageSize" />

    <p class="slib-note">
      公共场景没有「+ 新建场景」——创建永远发生在我的场景,这里只做浏览/复用,避免两套编排入口混淆。公共场景不暴露「方案」这个概念——直接用 config 里写好的默认配置跑,没有多方案可选。要跑不同参数组合,先「复制到我的」再去方案管理拆场景。「执行」和「复制到我的」都收进「⋯」菜单里——执行只会用这个场景锁死的默认 config 跑,不能改参数,主要用途是验证公共场景里定义的步骤能不能正常跑通(尤其是适配中心提示接口有变更的时候,可以直接在这里跑一次确认),不是替代「复制到我的」之后的正式编排使用。
    </p>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
import { listDataSets, runScenario } from '@/api/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { shortDateTime } from '@/utils/datetime'
import { FollowCapError } from '@/composables/useFollowLayout'
import { useScenarioListView } from '@/composables/useScenarioListView'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import StarToggle from '@/components/scenario-lib/StarToggle.vue'
import { Pagination } from '@/components/ui/pagination'
import FilterPopover from '@/components/FilterPopover.vue'
import FilterGroups from '@/components/scenario-lib/FilterGroups.vue'
import TagPill from '@/components/TagPill.vue'
import SystemChip from '@/components/SystemChip.vue'
import PriorityPill from '@/components/PriorityPill.vue'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { scenarioDetailUrl } from '@/utils/links'
import type { ScenarioListItem } from '@/types/scenario-composer'

const MAX = 3

const router = useRouter()

// 公共场景 = public 桶(与我的场景互补);骨架与我的场景共用一套。
const {
  store, filters, page, paged, total, filtering, filterableRows, facets, load, pageSize, loading,
  searchBox, writeSearch,
  groups, groupsState, savingGroup, activeGroupId, canSaveGroup, loadGroups, applyGroup, saveGroup, removeGroup,
} = useScenarioListView('public')

const formatTime = shortDateTime

onMounted(load)

/** 公共场景定义只读,但详情是可读的 —— 之前这里没有任何入口,想看步骤
 *  只能先「复制到我的」造一份副本,等于逼用户复制才能阅读。 */
function openDetail(row: ScenarioListItem) {
  router.push(scenarioDetailUrl(row.meta.scenarioId))
}

/** 验证执行:用场景锁死的默认 config 跑一次(其数据集全集,不改参数、
 *  不套方案 → 执行记录无 schemeId,即关注页公共原件的健康趋势来源)。 */
async function runPublic(row: ScenarioListItem) {
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

async function copyToMine(row: ScenarioListItem) {
  try {
    const saved = await store.copyScenario(row.meta.scenarioId)
    toast.success(`已复制到我的场景：${saved.meta.name || saved.meta.scenarioId}`)
  } catch (e) {
    showError('复制', undefined, (e as Error).message)
  }
}

async function toggleStar(row: ScenarioListItem) {
  // 乐观翻转 + 失败回滚:行来自服务端分页,store.invalidate 不重拉当前页
  const next = !row.starred
  row.starred = next
  try {
    await store.toggleStarWithCap(row.meta.scenarioId, next)
  } catch (e) {
    row.starred = !next
    if (e instanceof FollowCapError) toast.error(e.message)
    else showError('关注', undefined, (e as Error).message)
  }
}
</script>

<style scoped>
.sys-list { display: flex; flex-wrap: wrap; gap: 4px; }
.author { color: #5b6472; }
.row-expired td { opacity: 0.55; }
</style>
