<!-- ProjectDetailView.vue — 项目详情(/projects/:id),2026-11-18 按
     stitch 原型重建(claude/stitch_ux/stitch_/stitch_/_1.._6,全部为
     「公共 (Public Project)」项目页的 6 个页签)。

     §0 心智模型:项目 = 场景 / 用例集 / 集成任务的内容分区;成员按
     角色(admin/member/user)读写,凭证跟人走。页签六枚对齐原型:
     场景(用例) / 用例集 / 集成任务 / 加入申请 / 成员列表 / 项目配置,
     另保留「项目令牌」页签(原型没有、现网功能)。

     §1 原型 → 实现映射(数据面全部真实接线,宁可缺显不做假数据):
     - _1.._6 项目信息区 → .prj-head 头卡:字块 + 名称 + 可见性徽章 +
       统计(用例场景 / 用例集 / 成员 —— 原型的「运行成功率」后端无
       项目维度聚合端点,排期见 docs/project-detail-stitch-plan.md,
       不渲染);右侧「执行历史」→ /executions、「监控指标」→
       /analytics(均为普通跳转,不带项目过滤 —— 同排期)。
     - _2 场景表 → 普通项目内联表对齐公共场景页列面:星标 / 系统 /
       模块 / 优先级 / 作者 / 标签 / 最后编辑 / ⋯(查看·执行·复制到
       我的)。被复制次数后端无字段,整列不渲染(公共页同口径留 —,
       此处普通桶直接省列)。公共项目的场景页签仍整页复用
       ScenariosPublic(embedded,隐藏其 PageHead 消除双头)。
     - _1 用例集卡片流 → 普通项目从表格改 .suite-grid 卡片:模式徽章
       (串联/聚合/扇出/依赖编排)+ 草稿 chip + 成员场景数 + 最近执行
       通过/失败(latestRun,仅本人最近一次 —— 原型的通过率/平均耗时
       无历史台账,不渲染)+ 执行(runSuite)+ 查看。公共项目复用
       SuitesPublic(embedded)。
     - _3 集成任务表 → 列面:任务(TASK-{id} 标识 + 关联引用)/ 触发
       类型徽章(后端仅 cron一种,如示「定时调度 (Cron)」)/ cronText +
       下次触发(nextRunAt)/ 状态徽章 / 操作(执行 runIntegrationTask、
       详情深链);搜索 + 状态筛选(全部/运行中/已暂停,客户端)按原型
       补齐。原型的 4 张统计卡、「最近执行状态」与「执行器集群」列
       后端无台账无概念,不渲染(排期)。
     - _4 加入申请 / _5 成员列表 / _6 项目配置 → 委托 PromotionsPanel /
       ProjectMembersPanel / ProjectConfigPanel(各自面板内 re-skin)。

     §2 原型 M3 语义类(text-headline-md / on-surface / surface-container
     等)不搬:改写为 .slib 基座 + --sl-* 令牌 + 本文件 scoped CSS,
     与 ServiceAdmin 重建同套路。 -->
<template>
  <section class="slib">
    <p v-if="notFound" class="empty">项目不存在或无权访问。<router-link to="/projects">返回项目列表</router-link></p>
    <template v-else-if="project">
      <!-- ══ 原型 _1.._6 · 项目信息区(头卡)═════════════════════ -->
      <header class="prj-head" data-testid="prj-head">
        <span class="prj-avatar" aria-hidden="true">{{ projectInitial }}</span>
        <div class="prj-head-main">
          <div class="prj-title-row">
            <h2 class="prj-name" data-testid="prj-detail-name">{{ project.name }}</h2>
            <span class="vis-badge" :class="isPublic ? 'public' : 'normal'" data-testid="prj-vis-badge">
              <i class="dot" />{{ isPublic ? '全员可见' : '成员可见' }}
            </span>
          </div>
          <!-- 统计:场景 / 用例集 / 成员(原型的运行成功率 → 排期,不渲染) -->
          <div class="prj-stats" data-testid="prj-stats">
            <div class="stat">
              <span class="k">用例场景</span>
              <span class="v">{{ project.scenarioCount ?? 0 }}</span>
            </div>
            <div class="stat">
              <span class="k">用例集</span>
              <span class="v">{{ project.suiteCount ?? 0 }}</span>
            </div>
            <div class="stat">
              <span class="k">成员</span>
              <span class="v">{{ project.memberCount ?? 0 }}</span>
            </div>
          </div>
          <p v-if="project.description" class="prj-desc">{{ project.description }}</p>
          <p v-if="metaText" class="prj-meta" data-testid="prj-meta">{{ metaText }}</p>
        </div>
        <div class="prj-head-actions">
          <Button variant="outline" size="sm" data-testid="prj-history"
                  @click="router.push('/executions')">执行历史</Button>
          <Button size="sm" data-testid="prj-metrics"
                  @click="router.push('/analytics')">监控指标</Button>
          <!-- 编辑/删除只对普通项目(公共项目后端 409 保护,入口不展示) -->
          <Button
            v-if="project.canManage && !isPublic"
            variant="outline" size="sm" data-testid="prj-edit"
            @click="editOpen = true"
          >编辑项目</Button>
          <DropdownMenu v-if="auth.can('ops.write') && !isPublic">
            <DropdownMenuTrigger class="more-btn" aria-label="项目操作" data-testid="prj-more">⋯</DropdownMenuTrigger>
            <DropdownMenuContent align="end" class="sl-menu">
              <DropdownMenuItem class="sl-menu-item danger" data-testid="prj-del" @click="removeProject">
                删除项目
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <!-- ══ 原型 _1.._6 · 页签导航(计数徽章)═══════════════════ -->
      <nav class="tabs" data-testid="prj-tabs">
        <button
          v-for="t in visibleTabs"
          :key="t.key"
          type="button"
          class="tab"
          :class="{ on: tab === t.key }"
          :data-testid="`prj-tab-${t.key}`"
          @click="switchTab(t.key)"
        >{{ t.label }}<span
            v-if="tabCount(t.key) != null"
            class="cnt"
            :class="{ alert: t.key === 'promotions' }"
          >{{ tabCount(t.key) }}</span></button>
      </nav>

      <!-- 公共项目:场景/用例集页签 = 原公共页迁入(embedded 隐藏其页头) -->
      <ScenariosPublic v-if="isPublic && tab === 'scenarios'" embedded />
      <SuitesPublic v-else-if="isPublic && tab === 'suites'" embedded />

      <!-- ══ 原型 _2 · 场景(用例)页签(普通项目)═══════════════ -->
      <template v-else-if="tab === 'scenarios'">
        <div class="slib-toolbar">
          <input
            v-model="scenQ"
            class="slib-search"
            placeholder="按名 / scenarioId 搜索"
            data-testid="prj-scen-q"
            @keyup.enter="loadScenarios(1)"
          />
          <select v-model="scenPriority" class="toolbar-select" data-testid="prj-scen-priority"
                  @change="loadScenarios(1)">
            <option value="">全部优先级</option>
            <option v-for="p in [0, 1, 2, 3]" :key="p" :value="String(p)">P{{ p }}</option>
          </select>
          <button
            type="button" class="seg-btn" :class="{ on: scenStarred }"
            data-testid="prj-scen-starred" title="仅看已关注(★)"
            @click="scenStarred = !scenStarred; loadScenarios(1)"
          >★ 仅看关注</button>
          <span class="flex-1" />
          <button v-if="canWrite" type="button" class="slib-create" data-testid="prj-scen-new"
                  @click="newScenarioInProject">在本项目新建场景</button>
        </div>
        <div v-if="!scenLoaded" class="empty">加载中…</div>
        <div v-else-if="scenarios.length" class="lib-card">
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
              <tr v-for="r in scenarios" :key="r.meta.scenarioId" class="slib-row"
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
          <p>本项目还没有场景<template v-if="canWrite"> —— 点右上「在本项目新建场景」开始</template>。</p>
        </div>
        <Pagination
          v-if="scenTotal > 1"
          v-model:page="scenPage"
          v-model:page-size="scenPageSize"
          :total="scenTotal"
          show-page-size show-jump
        />
      </template>

      <!-- ══ 原型 _1 · 用例集卡片流(普通项目)══════════════════ -->
      <template v-else-if="tab === 'suites'">
        <div class="slib-toolbar">
          <input
            v-model="suiteQ"
            class="slib-search"
            placeholder="按名称 / 描述 / 发布者搜索"
            data-testid="prj-suite-q"
            @keyup.enter="loadSuites(1)"
          />
          <div class="seg-group" data-testid="prj-suite-mode-filter">
            <button
              v-for="m in suiteModeFilters"
              :key="m.key"
              type="button"
              class="seg-btn"
              :class="{ on: suiteMode === m.key }"
              :data-testid="`prj-suite-filter-${m.key || 'all'}`"
              @click="suiteMode = m.key"
            >{{ m.label }}</button>
          </div>
          <span class="flex-1" />
          <button v-if="canWrite" type="button" class="slib-create" data-testid="prj-suite-new"
                  @click="newSuiteInProject">在本项目新建用例集</button>
        </div>
        <div v-if="!suiteLoaded" class="empty">加载中…</div>
        <div v-else-if="suites.length" class="suite-grid">
          <article
            v-for="s in suites" :key="s.suiteId" class="suite-card"
            :data-testid="`prj-suite-${s.suiteId}`"
            @click="openSuite(s)"
          >
            <header class="sc-tags">
              <span class="mode-chip" :class="s.mode">{{ MODE_LABEL[s.mode] || s.mode }}编排</span>
              <span v-if="s.isDraft" class="draft-chip">草稿</span>
            </header>
            <h3 class="sc-name">{{ s.name }}</h3>
            <p class="sc-desc">{{ s.description || '—' }}</p>
            <div class="sc-stats">
              <div class="sc-stat">
                <span class="k">用例场景</span>
                <span class="v">{{ s.memberCount }}</span>
              </div>
              <!-- 最近执行(仅本人最近一次;原型的通过率/平均耗时无台账 → 排期) -->
              <div class="sc-stat">
                <span class="k">最近执行</span>
                <span class="v run" :class="latestRunTone(s)">
                  {{ s.latestRun ? `过 ${s.latestRun.passed ?? 0} / 败 ${s.latestRun.failed ?? 0}` : '—' }}
                </span>
              </div>
            </div>
            <footer class="sc-foot">
              <span class="sc-owner" :title="s.ownerName ?? undefined">{{ s.ownerName || '—' }}</span>
              <div class="sc-ops" @click.stop>
                <button type="button" class="run-btn" :disabled="suiteRunning === s.suiteId"
                        :data-testid="`prj-suite-run-${s.suiteId}`"
                        @click="runSuiteNow(s)">{{ suiteRunning === s.suiteId ? '执行中…' : '▶ 执行' }}</button>
                <button type="button" class="view-btn" :data-testid="`prj-suite-view-${s.suiteId}`"
                        @click="openSuite(s)">查看</button>
              </div>
            </footer>
          </article>
        </div>
        <div v-else class="empty-cta">
          <p>本项目还没有用例集。</p>
        </div>
        <Pagination
          v-if="suiteTotal > 1"
          v-model:page="suitePage"
          v-model:page-size="suitePageSize"
          :total="suiteTotal"
          show-page-size show-jump
        />
      </template>

      <!-- ══ 原型 _3 · 集成任务页签(公共/普通同构,?projectId 过滤)═ -->
      <template v-else-if="tab === 'tasks'">
        <div class="slib-toolbar">
          <input
            v-model="taskQ"
            class="slib-search"
            placeholder="按名称 / TASK 标识搜索"
            data-testid="prj-task-q"
          />
          <div class="seg-group" data-testid="prj-task-state-filter">
            <button
              v-for="f in taskStateFilters"
              :key="f.key"
              type="button"
              class="seg-btn"
              :class="{ on: taskState === f.key }"
              :data-testid="`prj-task-filter-${f.key || 'all'}`"
              @click="taskState = f.key"
            >{{ f.label }}<span class="stn">{{ taskStateCount(f.key) }}</span></button>
          </div>
        </div>
        <div v-if="!taskLoaded" class="empty">加载中…</div>
        <div v-else-if="shownTasks.length" class="lib-card">
          <table class="slib-table">
            <thead><tr>
              <th>集成任务</th>
              <th>关联场景 / 用例集</th>
              <th style="width:8.75rem">触发类型</th>
              <th style="width:10.625rem">调度 / 下次触发</th>
              <th style="width:5.625rem">状态</th>
              <th style="width:8.75rem" class="c-center">操作</th>
            </tr></thead>
            <tbody>
              <tr v-for="t in shownTasks" :key="t.id" class="slib-row"
                  :data-testid="`prj-task-${t.id}`" @click="$router.push(`/integrations/${t.id}`)">
                <td>
                  <div class="sl-name">{{ t.name }}</div>
                  <div class="sl-sid mono">TASK-{{ t.id }}</div>
                </td>
                <td><span class="muted mono">{{ t.scenarioId ?? (t.suiteId != null ? `suite:${t.suiteId}` : '—') }}</span></td>
                <td><span class="trigger-chip">定时调度 (Cron)</span></td>
                <td>
                  <div class="muted">{{ t.cronText }}</div>
                  <div v-if="t.instance?.nextRunAt" class="sl-sid">下次 {{ formatTime(t.instance.nextRunAt) }}</div>
                </td>
                <td><span class="svc-flag" :class="taskStateTone(t)">{{ taskStateLabel(t) }}</span></td>
                <td class="c-center" @click.stop>
                  <button type="button" class="act-btn primary" :disabled="taskRunning === t.id"
                          :data-testid="`prj-task-run-${t.id}`"
                          @click="runTaskNow(t)">{{ taskRunning === t.id ? '执行中…' : '▶ 执行' }}</button>
                  <button type="button" class="act-btn" :data-testid="`prj-task-detail-${t.id}`"
                          @click="$router.push(`/integrations/${t.id}`)">详情</button>
                </td>
              </tr>
            </tbody>
          </table>
          <!-- 原型 _3 表尾:共挂载数 + 当前筛选提示 -->
          <div class="task-foot" data-testid="prj-task-foot">
            <span class="muted">共挂载 {{ tasks.length }} 个集成任务</span>
            <span v-if="taskQ.trim() || taskState" class="muted">
              · 当前筛选 {{ shownTasks.length }} 项
            </span>
          </div>
        </div>
        <div v-else class="empty-cta">
          <p v-if="tasks.length">当前筛选没有匹配的集成任务 —— 换个关键词或状态。</p>
          <p v-else>本项目还没有集成任务 —— 集成中心创建时选择项目内场景即可挂到本项目。</p>
        </div>
      </template>

      <PromotionsPanel
        v-else-if="tab === 'promotions' && project"
        :project-id="project.id"
        :can-manage="!!project.canManage"
      />
      <ProjectMembersPanel
        v-else-if="tab === 'members' && project"
        :project="project"
        @changed="refreshDetail"
      />
      <ProjectTokensPanel
        v-else-if="tab === 'tokens' && project"
        :project="project"
        :can-manage="project.myRole === 'admin'"
      />
      <ProjectConfigPanel
        v-else-if="tab === 'config' && project"
        :project="project"
        @changed="refreshDetail"
      />

      <!-- 编辑项目信息(与列表页 ⋯ 菜单共用件) -->
      <ProjectEditDialog
        :open="editOpen"
        :project="project"
        @update:open="editOpen = $event"
        @saved="refreshDetail"
      />
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getProject, deleteProject, type ProjectOut } from '@/api/projects'
import { useAuthStore } from '@/stores/auth'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { projectRoleLabel } from '@/utils/projectRole'
import { listScenarios, listDataSets, runScenario } from '@/api/scenario-composer'
import type { ScenarioListItem } from '@/types/scenario-composer'
import { listSuites, createSuite, runSuite, type SuiteSummary } from '@/api/suites'
import { listIntegrationTasks, runIntegrationTask, type IntegrationTaskItem } from '@/api/integration'
import { MODE_LABEL } from '@/utils/suiteStructure'
import { scenarioDetailUrl } from '@/utils/links'
import { FollowCapError } from '@/composables/useFollowLayout'
import { usePagerSize } from '@/composables/usePagerSize'
import StarToggle from '@/components/scenario-lib/StarToggle.vue'
import SystemChip from '@/components/SystemChip.vue'
import TagPill from '@/components/TagPill.vue'
import PriorityPill from '@/components/PriorityPill.vue'
import { Pagination } from '@/components/ui/pagination'
import ProjectEditDialog from '@/components/project/ProjectEditDialog.vue'
import ProjectMembersPanel from '@/components/project/ProjectMembersPanel.vue'
import ProjectConfigPanel from '@/components/project/ProjectConfigPanel.vue'
import PromotionsPanel from '@/components/project/PromotionsPanel.vue'
import ProjectTokensPanel from '@/components/project/ProjectTokensPanel.vue'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { confirmAction } from '@/utils/confirmAction'
import { shortDateTime } from '@/utils/datetime'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'

const ScenariosPublic = defineAsyncComponent(() => import('@/views/ScenariosPublic.vue'))
const SuitesPublic = defineAsyncComponent(() => import('@/views/SuitesPublic.vue'))

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const scenStore = useScenarioComposerStore()
const formatTime = shortDateTime

const project = ref<ProjectOut | null>(null)
const notFound = ref(false)

// ── 头卡(原型项目信息区)─────────────────────────────────────────
const projectInitial = computed(() => (project.value?.name?.trim()?.[0] ?? 'P').toUpperCase())
/** 普通项目的常驻 meta:角色 + 默认环境;公共项目语义已进徽章,不重复 */
const metaText = computed(() => {
  const p = project.value
  if (!p || p.kind === 'public') return undefined
  const env = p.defaultEnvironmentName ? `默认环境 ${p.defaultEnvironmentName}` : '默认环境未设置'
  return `${projectRoleLabel(p.myRole)} · ${env}`
})

const TABS = [
  { key: 'scenarios', label: '场景 (用例)' },
  { key: 'suites', label: '用例集' },
  { key: 'tasks', label: '集成任务' },
  // S7.2:加入申请(管理员裁决;成员看自己的 —— 后端按角色过滤)
  { key: 'promotions', label: '加入申请' },
  { key: 'members', label: '成员列表' },
  // S7.3:配置(普通项目 = 默认环境/项目层 carry/装载状态/生效预览;
  // 公共项目 = 全局默认,原 /carry-config 落位)
  { key: 'config', label: '项目配置' },
  // M2b Q2:项目令牌(普通项目 ∧ 项目管理员 —— r5-2.2 同口径,
  // Admin+ 非成员不旁路,与后端 /tokens 门一致;原型无此页签,保留)
  { key: 'tokens', label: '项目令牌' },
] as const
type TabKey = (typeof TABS)[number]['key']

const tab = computed<TabKey>(() => {
  const t = String(route.query.tab ?? 'scenarios')
  return (TABS.some((x) => x.key === t) ? t : 'scenarios') as TabKey
})
const isPublic = computed(() => project.value?.kind === 'public')
// M2b Q1:项目用户只读 + 执行 → 隐藏「在本项目新建」入口(后端仍是权威)
const canWrite = computed(() => project.value?.canWrite !== false)
const visibleTabs = computed(() =>
  TABS.filter((t) => {
    if (t.key === 'members') return !!project.value?.canManage
    if (t.key === 'tokens')
      return project.value?.myRole === 'admin' && !isPublic.value
    return true
  }))

function switchTab(key: TabKey): void {
  void router.replace({ query: { ...route.query, tab: key } })
}

/** 页签徽标计数(详情端点的内容计数;加入申请 = pending 数;拉取前 = null 不显) */
function tabCount(key: TabKey): number | null {
  const p = project.value
  if (!p) return null
  if (key === 'scenarios') return p.scenarioCount ?? null
  if (key === 'suites') return p.suiteCount ?? null
  if (key === 'tasks') return p.taskCount ?? null
  if (key === 'members') return p.memberCount ?? null
  if (key === 'promotions') return p.pendingPromotions || null
  return null
}

async function refreshDetail(): Promise<void> {
  if (project.value) {
    try { project.value = await getProject(project.value.id) } catch { /* 保持旧值 */ }
  }
}

// ── 编辑 / 删除(详情页头动作;公共项目不展示,后端同口径保护)────
const editOpen = ref(false)

async function removeProject(): Promise<void> {
  const p = project.value
  if (!p) return
  const ok = await confirmAction(
    `删除项目「${p.name}」?成员关系随项目消失;项目内有场景 / 用例集 / 集成任务时会被拒绝,须先清空或迁走。`,
    '删除项目',
    { danger: true, confirmButtonText: '删除' },
  )
  if (!ok) return
  try {
    await deleteProject(p.id)
    toast.success(`项目已删除:${p.name}`)
    await router.push('/projects')
  } catch (e) {
    showError('删除项目', undefined, (e as Error).message)
  }
}

// ── 普通项目:场景页签(列面对齐原型 _2 / 公共场景页)────────────
const scenarios = ref<ScenarioListItem[]>([])
const scenQ = ref('')
const scenPriority = ref('')
const scenStarred = ref(false)
const scenPage = ref(1)
const scenTotal = ref(0)
const { pageSize: scenPageSize } = usePagerSize('prj-detail-scen', 20)
const scenLoaded = ref(false)

async function loadScenarios(page = scenPage.value): Promise<void> {
  if (!project.value) return
  scenPage.value = page
  const env = await listScenarios({
    projectId: project.value.id,
    q: scenQ.value.trim() || undefined,
    priority: scenPriority.value || undefined,
    starred: scenStarred.value || undefined,
    page, page_size: scenPageSize.value,
  })
  scenarios.value = env.items
  scenTotal.value = env.total
  scenLoaded.value = true
}

// 筛选变化回第 1 页重拉(watch 而非内联,统一入口)
watch([scenPriority, scenStarred], () => void loadScenarios(1))
watch(scenPageSize, () => void loadScenarios(1))

function newScenarioInProject(): void {
  void router.push({ path: '/composer/new', query: { projectId: String(project.value?.id) } })
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

// ── 普通项目:用例集卡片流(原型 _1)─────────────────────────────
const suites = ref<SuiteSummary[]>([])
const suiteQ = ref('')
const suiteMode = ref('')
const suitePage = ref(1)
const suiteTotal = ref(0)
const { pageSize: suitePageSize } = usePagerSize('prj-detail-suite', 12)
const suiteLoaded = ref(false)
const suiteRunning = ref<number | null>(null)

const suiteModeFilters = [
  { key: '', label: '全部' },
  { key: 'aggregate', label: MODE_LABEL.aggregate },
  { key: 'chain', label: MODE_LABEL.chain },
  { key: 'fanout', label: MODE_LABEL.fanout },
  { key: 'compose', label: MODE_LABEL.compose },
]

async function loadSuites(page = suitePage.value): Promise<void> {
  if (!project.value) return
  suitePage.value = page
  const env = await listSuites({
    projectId: project.value.id,
    q: suiteQ.value.trim() || undefined,
    mode: suiteMode.value || undefined,
    page, page_size: suitePageSize.value,
  })
  suites.value = env.items
  suiteTotal.value = env.total
  suiteLoaded.value = true
}

// 搜索防抖 / 模式切换 / 翻页
let suiteQTimer: ReturnType<typeof setTimeout> | undefined
watch(suiteQ, () => {
  clearTimeout(suiteQTimer)
  suiteQTimer = setTimeout(() => void loadSuites(1), 300)
})
watch(suiteMode, () => void loadSuites(1))
watch(suitePageSize, () => void loadSuites(1))

/** 最近执行徽章口径:有失败 → 坏;有通过 → 好;无记录 → 灰 */
function latestRunTone(s: SuiteSummary): string {
  const r = s.latestRun
  if (!r) return 'none'
  if ((r.failed ?? 0) > 0) return 'bad'
  if ((r.passed ?? 0) > 0) return 'ok'
  return 'none'
}

async function runSuiteNow(s: SuiteSummary): Promise<void> {
  suiteRunning.value = s.suiteId
  try {
    await runSuite(s.suiteId)
    toast.success(`已发起用例集执行:${s.name}`)
  } catch (e) {
    toast.error(`执行失败:${(e as Error).message}`)
  } finally {
    suiteRunning.value = null
  }
}

async function newSuiteInProject(): Promise<void> {
  if (!project.value) return
  try {
    const s = await createSuite({ projectId: project.value.id })
    toast.success(`已在项目中创建用例集:${s.name}`)
    await router.push(`/suites/${s.suiteId}/compose`)
  } catch (e) {
    showError('创建用例集', undefined, (e as Error).message)
  }
}
function openSuite(s: SuiteSummary): void {
  void router.push(`/suites/${s.suiteId}`)
}

// ── 集成任务页签(原型 _3)───────────────────────────────────────
const tasks = ref<IntegrationTaskItem[]>([])
const taskLoaded = ref(false)
const taskRunning = ref<number | null>(null)
/** 原型 _3:搜索 + 状态筛选(客户端 —— 项目任务量小,列表一次拉全) */
const taskQ = ref('')
const taskState = ref('')
const taskStateFilters = [
  { key: '', label: '全部' },
  { key: 'running', label: '运行中' },
  { key: 'paused', label: '已暂停' },
]
function taskStateCount(key: string): number {
  if (!key) return tasks.value.length
  return tasks.value.filter((t) => t.instance?.state === key).length
}
const shownTasks = computed(() => {
  let out = tasks.value
  if (taskState.value) out = out.filter((t) => t.instance?.state === taskState.value)
  const kw = taskQ.value.trim().toLowerCase()
  if (kw) {
    out = out.filter((t) =>
      (t.name || '').toLowerCase().includes(kw)
      || String(t.id).includes(kw)
      || `task-${t.id}`.includes(kw))
  }
  return out
})

async function loadTasks(): Promise<void> {
  if (!project.value) return
  const items = await listIntegrationTasks(project.value.id)
  tasks.value = items
  taskLoaded.value = true
}

async function runTaskNow(t: IntegrationTaskItem): Promise<void> {
  taskRunning.value = t.id
  try {
    const res = await runIntegrationTask(t.id)
    if (res.result.status === 'ok') toast.success(`执行成功:${t.name}`)
    else toast.error(`执行异常:${res.result.error || res.result.status}`)
  } catch (e) {
    toast.error(`执行失败:${(e as Error).message}`)
  } finally {
    taskRunning.value = null
  }
}

/** 实例运行态 → 徽章(running 绿 / paused 琥珀 / 其余灰) */
function taskStateTone(t: IntegrationTaskItem): string {
  const s = t.instance?.state
  if (s === 'running') return 'green'
  if (s === 'paused') return 'amber'
  return 'ink'
}
function taskStateLabel(t: IntegrationTaskItem): string {
  const s = t.instance?.state
  if (s === 'running') return '运行中'
  if (s === 'paused') return '已暂停'
  if (s === 'idle') return '空闲'
  return '—'
}

// ── 装载:详情 + 当前页签数据(tab 切换按需拉) ──────────────────
async function loadDetail(): Promise<void> {
  notFound.value = false
  const id = Number(route.params.id)
  if (!Number.isInteger(id) || id <= 0) { notFound.value = true; return }
  try {
    project.value = await getProject(id)
  } catch {
    notFound.value = true
    return
  }
  await refreshTabData()
}

async function refreshTabData(): Promise<void> {
  try {
    if (tab.value === 'scenarios' && !isPublic.value) await loadScenarios(1)
    else if (tab.value === 'suites' && !isPublic.value) await loadSuites(1)
    else if (tab.value === 'tasks') await loadTasks()
  } catch (e) {
    showError('加载项目内容', undefined, (e as Error).message)
  }
}

watch(tab, refreshTabData)
watch(() => route.params.id, loadDetail)
onMounted(loadDetail)
</script>

<style scoped>
/* 与其它 .slib 页一致:整页纵向节奏(头卡 / 页签 / 内容 / 分页之间留白)。
   全局 .slib 只管页垫,不管子元素间距 —— 不补这条,页签下方内容会贴住
   页签底边,列表与分页也会互相贴住。 */
.slib { display: flex; flex-direction: column; gap: 0.875rem; }

/* ── 头卡(原型项目信息区):字块 + 名称 + 徽章 + 统计行 ────────── */
.prj-head {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.625rem;
}
.prj-avatar {
  flex: none;
  width: 3rem; height: 3rem;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.125rem; font-weight: 700; color: #fff;
  background: var(--sl-accent);
  border-radius: 0.625rem;
}
.prj-head-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.5rem; }
.prj-title-row { display: flex; align-items: center; gap: 0.625rem; flex-wrap: wrap; }
.prj-name { margin: 0; font-size: 1.125rem; font-weight: 600; color: var(--sl-ink); }
.vis-badge {
  display: inline-flex; align-items: center; gap: 0.3125rem;
  font-size: 0.71875rem;
  padding: 0.125rem 0.5625rem;
  border-radius: 62.4375rem;
  border: 1px solid var(--sl-line);
  background: var(--soft-neutral-bg);
  color: var(--sl-ink-2);
}
.vis-badge .dot { width: 0.375rem; height: 0.375rem; border-radius: 50%; background: var(--sl-ink-3); }
.vis-badge.public .dot { background: var(--sl-ok); }
.prj-stats { display: flex; gap: 1.75rem; flex-wrap: wrap; }
.stat { display: flex; align-items: baseline; gap: 0.375rem; }
.stat .k { font-size: 0.75rem; color: var(--sl-ink-3); }
.stat .v { font-size: 1rem; font-weight: 600; color: var(--sl-ink); font-variant-numeric: tabular-nums; }
.prj-desc { margin: 0; font-size: 0.8125rem; color: var(--sl-ink-2); }
.prj-meta { margin: 0; font-size: 0.75rem; color: var(--sl-ink-3); }
.prj-head-actions { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; justify-content: flex-end; }

/* ── 页签:下划线活跃态,令牌色(随日夜主题翻转)────────────────── */
.tabs { display: flex; gap: 0.25rem; border-bottom: 1px solid var(--sl-line); }
.tab {
  border: none;
  background: none;
  padding: 0.45rem 0.9rem;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--sl-ink-2);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;   /* 压住容器底线,活跃态下划线不断层 */
}
.tab:hover { color: var(--sl-ink); }
.tab.on { color: var(--sl-accent); border-bottom-color: var(--sl-accent); font-weight: 600; }
.cnt {
  margin-left: 0.375rem;
  font-size: 0.6875rem;
  padding: 0.0625rem 0.5rem;
  border-radius: 62.4375rem;
  color: var(--sl-ink-3);
  background: var(--soft-neutral-bg);
  border: 1px solid var(--sl-line);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
.tab.on .cnt { color: var(--sl-accent); border-color: var(--sl-accent-soft-border, var(--sl-accent)); }
/* 加入申请 pending → 红徽章(原型红色角标口径) */
.cnt.alert { color: var(--sl-bad); background: var(--sl-bad-soft); border-color: var(--sv-bad-line, var(--sl-bad)); }

/* ── 工具条与筛选 ──────────────────────────────────────────────── */
.slib-toolbar { display: flex; gap: 0.625rem; align-items: center; flex-wrap: wrap; margin-bottom: 0; }
.toolbar-select {
  padding: 0.4375rem 0.625rem;
  font-size: 0.78125rem;
  border-radius: 0.5rem;
  border: 1px solid var(--sl-line);
  background: var(--c-surface);
  color: var(--sl-ink);
}
.seg-group { display: flex; border: 1px solid var(--sl-line); border-radius: 0.5rem; overflow: hidden; }
.seg-btn {
  padding: 0.4375rem 0.75rem;
  font-size: 0.78125rem;
  cursor: pointer;
  border: none;
  background: transparent;
  color: var(--sl-ink-2);
  border-right: 1px solid var(--sl-line);
}
.seg-btn:last-child { border-right: none; }
.seg-btn:hover { color: var(--sl-ink); }
.seg-btn.on { background: var(--sl-accent-soft); color: var(--sl-accent); font-weight: 600; }
/* 原型 _3:筛选钮计数 */
.seg-btn .stn {
  margin-left: 0.25rem;
  font-size: 0.6875rem;
  color: var(--sl-ink-3);
  font-variant-numeric: tabular-nums;
}
.seg-btn.on .stn { color: var(--sl-accent); }
.task-foot {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  padding: 0.5rem 0.875rem;
  border-top: 1px solid var(--sl-line);
  font-size: 0.71875rem;
}

/* 表格单元格辅助 */
.sys-cell { display: flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }
.c-center { text-align: center !important; }
.mono { font-family: var(--font-mono, monospace); }
.sl-desc {
  font-size: 0.71875rem;
  color: var(--sl-ink-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 34.375rem;
}

/* ── 用例集卡片流(原型 _1)────────────────────────────────────── */
.suite-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(21.25rem, 1fr));
  gap: 0.875rem;
}
.suite-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.875rem 1rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.625rem;
  cursor: pointer;
}
.suite-card:hover { border-color: var(--sl-accent); }
.sc-tags { display: flex; align-items: center; gap: 0.375rem; }
.mode-chip {
  font-size: 0.71875rem;
  padding: 0.125rem 0.5625rem;
  border-radius: 62.4375rem;
  white-space: nowrap;
  color: var(--sl-ink-2);
  background: var(--soft-neutral-bg);
  border: 1px solid var(--sl-line);
}
.mode-chip.chain, .mode-chip.fanout, .mode-chip.compose {
  color: #6d28d9;
  background: rgb(139 92 246 / 8%);
  border-color: rgb(139 92 246 / 30%);
}
.draft-chip {
  font-size: 0.65625rem;
  font-weight: 600;
  padding: 0.0625rem 0.5rem;
  border-radius: 62.4375rem;
  background: var(--sl-warn-soft);
  color: var(--sl-warn);
}
.sc-name { margin: 0; font-size: 0.9375rem; font-weight: 600; color: var(--sl-ink); }
.sc-desc {
  margin: 0;
  font-size: 0.75rem;
  color: var(--sl-ink-3);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 2.125rem;
}
.sc-stats { display: flex; gap: 1.5rem; }
.sc-stat .k { display: block; font-size: 0.6875rem; color: var(--sl-ink-3); }
.sc-stat .v { font-size: 0.875rem; font-weight: 600; color: var(--sl-ink); font-variant-numeric: tabular-nums; }
.sc-stat .v.run.ok { color: var(--sl-ok); }
.sc-stat .v.run.bad { color: var(--sl-bad); }
.sc-stat .v.run.none { font-weight: 400; }
.sc-foot {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--sl-line);
}
.sc-owner {
  flex: 1;
  font-size: 0.75rem;
  color: var(--sl-ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sc-ops { display: flex; gap: 0.5rem; }
.run-btn {
  font-size: 0.75rem;
  padding: 0.25rem 0.75rem;
  border-radius: 0.375rem;
  cursor: pointer;
  color: var(--sl-accent);
  background: var(--sl-accent-soft);
  border: 1px solid var(--sl-accent-soft-border, var(--sl-accent));
}
.run-btn:hover:not(:disabled) { background: var(--sl-accent); color: #fff; }
.run-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.view-btn {
  font-size: 0.75rem;
  padding: 0.25rem 0.75rem;
  border-radius: 0.375rem;
  cursor: pointer;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
}
.view-btn:hover { border-color: var(--sl-accent); color: var(--sl-accent); }

/* ── 集成任务表 ────────────────────────────────────────────────── */
.trigger-chip {
  font-size: 0.6875rem;
  padding: 0.0625rem 0.5rem;
  border-radius: 62.4375rem;
  color: var(--sl-ink-2);
  background: var(--soft-neutral-bg);
  border: 1px solid var(--sl-line);
  white-space: nowrap;
}
.act-btn {
  height: 1.6875rem;
  padding: 0 0.625rem;
  margin-right: 0.375rem;
  font-size: 0.75rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.375rem;
  cursor: pointer;
  white-space: nowrap;
}
.act-btn:hover:not(:disabled) { border-color: var(--sl-accent); color: var(--sl-accent); }
.act-btn.primary { color: var(--sl-accent); border-color: var(--sl-accent); }
.act-btn.primary:hover:not(:disabled) { background: var(--sl-accent-soft); }
.act-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.empty { color: var(--sl-ink-3); margin: 0; }
.muted { color: var(--sl-ink-3); }
</style>
