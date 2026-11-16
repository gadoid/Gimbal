<!-- ProjectDetailView.vue — M2a S7.1:项目详情(/projects/:id)。
     2026-11-16 重塑:页头落 PageHead(icon + 项目名 + meta 行),右侧
     「编辑项目」(ProjectEditDialog 共享件)与 ⋯「删除项目」(Admin+,
     公共项目后端保护不展示);页签走令牌色 + 加入申请 pending 徽标
     (详情端点 pendingPromotions);场景/用例集/集成任务三表落
     .lib-card + .slib-table(系统列 SystemChip)。公共项目的场景/
     用例集页签 = 原公共页原样迁入;成员/配置/令牌页签委托子面板。 -->
<template>
  <section class="slib">
    <p v-if="notFound" class="empty">项目不存在或无权访问。<router-link to="/projects">返回项目列表</router-link></p>
    <template v-else-if="project">
      <PageHead
        icon="layers"
        :title="project.name"
        title-test-id="prj-detail-name"
        subtitle="项目 = 场景 / 用例集 / 集成任务的内容分区;成员按角色读写,凭证跟人走。"
        :meta="metaText"
        :hint="project.description"
      >
        <template #right>
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
        </template>
      </PageHead>

      <nav class="tabs" data-testid="prj-tabs">
        <button
          v-for="t in visibleTabs"
          :key="t.key"
          type="button"
          class="tab"
          :class="{ on: tab === t.key }"
          :data-testid="`prj-tab-${t.key}`"
          @click="switchTab(t.key)"
        >{{ t.label }}<span v-if="tabCount(t.key) != null" class="cnt">{{ tabCount(t.key) }}</span></button>
      </nav>

      <!-- 公共项目:场景/用例集页签 = 原公共页原样迁入(读/复制/fork) -->
      <ScenariosPublic v-if="isPublic && tab === 'scenarios'" />
      <SuitesPublic v-else-if="isPublic && tab === 'suites'" />

      <template v-else-if="tab === 'scenarios'">
        <div class="slib-toolbar">
          <input
            v-model="scenQ"
            class="slib-search"
            placeholder="按名 / scenarioId 搜索"
            data-testid="prj-scen-q"
            @keyup.enter="loadScenarios(1)"
          />
          <button v-if="canWrite" type="button" class="slib-create" data-testid="prj-scen-new"
                  @click="newScenarioInProject">在本项目新建场景</button>
        </div>
        <div v-if="!scenLoaded" class="empty">加载中…</div>
        <div v-else-if="scenarios.length" class="lib-card">
          <table class="slib-table">
            <thead><tr><th>场景名</th><th style="width:8.75rem">系统</th><th style="width:6.25rem">模块</th><th style="width:6.875rem">作者</th><th style="width:6.875rem">最后编辑</th></tr></thead>
            <tbody>
              <tr v-for="r in scenarios" :key="r.meta.scenarioId" class="slib-row"
                  :data-testid="`prj-scen-${r.meta.scenarioId}`"
                  @click="openScenario(r.meta.scenarioId)">
                <td>
                  <div class="sl-name">{{ r.meta.name || r.meta.scenarioId }}</div>
                  <div class="sl-sid">{{ r.meta.scenarioId }}</div>
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
                <td><span class="muted">{{ r.meta.module || '未分类' }}</span></td>
                <td><span class="muted">{{ r.meta.author || r.meta.owner || '—' }}</span></td>
                <td><span class="muted">{{ formatTime(r.meta.updateTime) }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-cta">
          <p>本项目还没有场景<template v-if="canWrite"> —— 点右上「在本项目新建场景」开始</template>。</p>
        </div>
        <div class="pager" v-if="scenTotal > scenPageSize">
          <button type="button" class="pager-btn" :disabled="scenPage <= 1" @click="loadScenarios(scenPage - 1)">上一页</button>
          <span class="muted">{{ scenPage }} / {{ Math.ceil(scenTotal / scenPageSize) }}</span>
          <button type="button" class="pager-btn" :disabled="scenPage * scenPageSize >= scenTotal" @click="loadScenarios(scenPage + 1)">下一页</button>
        </div>
      </template>

      <template v-else-if="tab === 'suites'">
        <div class="slib-toolbar">
          <input
            v-model="suiteQ"
            class="slib-search"
            placeholder="按名称搜索"
            data-testid="prj-suite-q"
            @keyup.enter="loadSuites()"
          />
          <button v-if="canWrite" type="button" class="slib-create" data-testid="prj-suite-new"
                  @click="newSuiteInProject">在本项目新建用例集</button>
        </div>
        <div v-if="!suiteLoaded" class="empty">加载中…</div>
        <div v-else-if="suites.length" class="lib-card">
          <table class="slib-table">
            <thead><tr><th>名称</th><th style="width:6.25rem">模式</th><th style="width:5.625rem">成员数</th><th style="width:6.875rem">最后编辑</th></tr></thead>
            <tbody>
              <tr v-for="s in suites" :key="s.suiteId" class="slib-row"
                  :data-testid="`prj-suite-${s.suiteId}`" @click="openSuite(s)">
                <td>
                  <div class="sl-name">{{ s.name }}<span v-if="s.isDraft" class="draft-chip">草稿</span></div>
                  <div class="sl-sid">{{ s.description || '—' }}</div>
                </td>
                <td><span class="muted">{{ s.mode }}</span></td>
                <td><span class="muted">{{ s.memberCount }}</span></td>
                <td><span class="muted">{{ formatTime(s.updatedAt ?? undefined) }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-cta">
          <p>本项目还没有用例集。</p>
        </div>
      </template>

      <template v-else-if="tab === 'tasks'">
        <div v-if="!taskLoaded" class="empty">加载中…</div>
        <div v-else-if="tasks.length" class="lib-card">
          <table class="slib-table">
            <thead><tr><th>名称</th><th style="width:9.375rem">调度</th><th>引用</th><th style="width:6.25rem">状态</th></tr></thead>
            <tbody>
              <tr v-for="t in tasks" :key="t.id" class="slib-row"
                  :data-testid="`prj-task-${t.id}`" @click="$router.push(`/integrations/${t.id}`)">
                <td><div class="sl-name">{{ t.name }}</div></td>
                <td><span class="muted">{{ t.cronText }}</span></td>
                <td><span class="muted">{{ t.scenarioId ?? t.suiteId ?? '—' }}</span></td>
                <td><span class="svc-flag" :class="taskStateTone(t)">{{ taskStateLabel(t) }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-cta">
          <p>本项目还没有集成任务 —— 集成中心创建时选择项目内场景即可挂到本项目。</p>
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
import { projectRoleLabel } from '@/utils/projectRole'
import { listScenarios } from '@/api/scenario-composer'
import type { ScenarioListItem } from '@/types/scenario-composer'
import { listSuites, createSuite, type SuiteSummary } from '@/api/suites'
import { listIntegrationTasks, type IntegrationTaskItem } from '@/api/integration'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import SystemChip from '@/components/SystemChip.vue'
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
const formatTime = shortDateTime

const project = ref<ProjectOut | null>(null)
const notFound = ref(false)

const metaText = computed(() => {
  const p = project.value
  if (!p) return undefined
  if (p.kind === 'public') return `公共项目 · 全员可见 · ${p.scenarioCount ?? 0} 场景 / ${p.suiteCount ?? 0} 用例集`
  const env = p.defaultEnvironmentName ? `默认环境 ${p.defaultEnvironmentName}` : '默认环境未设置'
  return `${projectRoleLabel(p.myRole)} · ${env} · ${p.memberCount} 名成员`
})

const TABS = [
  { key: 'scenarios', label: '场景' },
  { key: 'suites', label: '用例集' },
  { key: 'tasks', label: '集成任务' },
  // S7.2:加入申请(管理员裁决;成员看自己的 —— 后端按角色过滤)
  { key: 'promotions', label: '加入申请' },
  { key: 'members', label: '成员' },
  // S7.3:配置(普通项目 = 默认环境/项目层 carry/装载状态/生效预览;
  // 公共项目 = 全局默认,原 /carry-config 落位)
  { key: 'config', label: '配置' },
  // M2b Q2:项目令牌(普通项目 ∧ 项目管理员 —— r5-2.2 同口径,
  // Admin+ 非成员不旁路,与后端 /tokens 门一致)
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

// ── 普通项目:场景页签(projectId 过滤 + 在本项目新建) ──────────
const scenarios = ref<ScenarioListItem[]>([])
const scenQ = ref('')
const scenPage = ref(1)
const scenTotal = ref(0)
const scenPageSize = 20
const scenLoaded = ref(false)

async function loadScenarios(page = scenPage.value): Promise<void> {
  if (!project.value) return
  scenPage.value = page
  const env = await listScenarios({
    projectId: project.value.id,
    q: scenQ.value.trim() || undefined,
    page, page_size: scenPageSize,
  })
  scenarios.value = env.items
  scenTotal.value = env.total
  scenLoaded.value = true
}

function newScenarioInProject(): void {
  void router.push({ path: '/composer/new', query: { projectId: String(project.value?.id) } })
}
function openScenario(id: string): void {
  void router.push(`/scenarios/${encodeURIComponent(id)}/detail`)
}

// ── 普通项目:用例集页签 ─────────────────────────────────────────
const suites = ref<SuiteSummary[]>([])
const suiteQ = ref('')
const suiteLoaded = ref(false)

async function loadSuites(): Promise<void> {
  if (!project.value) return
  const env = await listSuites({
    projectId: project.value.id,
    q: suiteQ.value.trim() || undefined,
    page_size: 100,
  })
  suites.value = env.items
  suiteLoaded.value = true
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

// ── 集成任务页签 ────────────────────────────────────────────────
const tasks = ref<IntegrationTaskItem[]>([])
const taskLoaded = ref(false)

async function loadTasks(): Promise<void> {
  if (!project.value) return
  const items = await listIntegrationTasks(project.value.id)
  tasks.value = items
  taskLoaded.value = true
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
    else if (tab.value === 'suites' && !isPublic.value) await loadSuites()
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
  margin-left: 0.25rem;
  font-size: 0.6875rem;
  color: var(--sl-ink-3);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.tab.on .cnt { color: var(--sl-accent); }

/* 表格单元格辅助 */
.sys-cell { display: flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }
.draft-chip {
  margin-left: 0.375rem;
  font-size: 0.65625rem;
  font-weight: 600;
  padding: 0.0625rem 0.5rem;
  border-radius: 62.4375rem;
  background: var(--sl-warn-soft);
  color: var(--sl-warn);
}

/* 分页(与旧版同构,令牌化) */
.pager { display: flex; align-items: center; gap: 0.6rem; }
.pager-btn {
  padding: 0.1875rem 0.625rem;
  font-size: 0.78125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.375rem;
  cursor: pointer;
}
.pager-btn:hover:not(:disabled) { border-color: var(--sl-accent); color: var(--sl-accent); }
.pager-btn:disabled { opacity: 0.45; cursor: not-allowed; }

.empty { color: var(--sl-ink-3); margin: 0; }
.muted { color: var(--sl-ink-3); }
</style>
