<!-- ProjectDetailView.vue — M2a S7.1:项目详情(/projects/:id)。
     页签:场景 / 用例集 / 集成任务 / 成员(canManage 才显)。
     公共项目的场景/用例集页签 = 原「公共场景/公共用例集」页原样迁入
     (visibility=public 兼容别名 = 公共项目);普通项目页签按
     projectId 过滤,场景页签可「在本项目新建」(?projectId= 深链进
     编排器,首次保存落库进项目)。成员页签 = ProjectMembersPanel。 -->
<template>
  <section class="page">
    <p v-if="notFound" class="empty">项目不存在或无权访问。<router-link to="/projects">返回项目列表</router-link></p>
    <template v-else-if="project">
      <header class="head">
        <div class="row-title">
          <h1 data-testid="prj-detail-name">{{ project.name }}</h1>
          <span v-if="project.kind === 'public'" class="badge pub">公共</span>
          <span v-else-if="project.myRole" class="badge" data-testid="prj-detail-role">
            {{ roleLabel(project.myRole) }}
          </span>
        </div>
        <p class="sub">{{ project.description }}</p>
        <span v-if="project.defaultEnvironmentName" class="meta">
          默认环境:{{ project.defaultEnvironmentName }}
        </span>
      </header>

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
        <div class="toolbar">
          <input
            v-model="scenQ"
            class="search"
            placeholder="按名 / scenarioId 搜索"
            data-testid="prj-scen-q"
            @keyup.enter="loadScenarios(1)"
          />
          <button v-if="canWrite" type="button" class="btn primary" data-testid="prj-scen-new"
                  @click="newScenarioInProject">在本项目新建场景</button>
        </div>
        <table class="tbl" v-if="scenarios.length">
          <thead><tr><th>场景名</th><th style="width:100px">系统</th><th style="width:100px">模块</th><th style="width:110px">作者</th><th style="width:100px">最后编辑</th></tr></thead>
          <tbody>
            <tr v-for="r in scenarios" :key="r.meta.scenarioId" class="row-link"
                :data-testid="`prj-scen-${r.meta.scenarioId}`"
                @click="openScenario(r.meta.scenarioId)">
              <td>
                <div class="sl-name">{{ r.meta.name || r.meta.scenarioId }}</div>
                <div class="sl-sid">{{ r.meta.scenarioId }}</div>
              </td>
              <td><span class="muted">{{ r.meta.system.join(', ') || '—' }}</span></td>
              <td><span class="muted">{{ r.meta.module || '未分类' }}</span></td>
              <td><span class="muted">{{ r.meta.author || r.meta.owner || '—' }}</span></td>
              <td><span class="muted">{{ formatTime(r.meta.updateTime) }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="scenLoaded" class="empty">本项目还没有场景<template v-if="canWrite"> —— 点右上「在本项目新建场景」开始</template>。</p>
        <div class="pager" v-if="scenTotal > scenPageSize">
          <button type="button" class="btn sm" :disabled="scenPage <= 1" @click="loadScenarios(scenPage - 1)">上一页</button>
          <span class="muted">{{ scenPage }} / {{ Math.ceil(scenTotal / scenPageSize) }}</span>
          <button type="button" class="btn sm" :disabled="scenPage * scenPageSize >= scenTotal" @click="loadScenarios(scenPage + 1)">下一页</button>
        </div>
      </template>

      <template v-else-if="tab === 'suites'">
        <div class="toolbar">
          <input
            v-model="suiteQ"
            class="search"
            placeholder="按名称搜索"
            data-testid="prj-suite-q"
            @keyup.enter="loadSuites()"
          />
          <button v-if="canWrite" type="button" class="btn primary" data-testid="prj-suite-new"
                  @click="newSuiteInProject">在本项目新建用例集</button>
        </div>
        <table class="tbl" v-if="suites.length">
          <thead><tr><th>名称</th><th style="width:80px">模式</th><th style="width:90px">成员数</th><th style="width:110px">最后编辑</th></tr></thead>
          <tbody>
            <tr v-for="s in suites" :key="s.suiteId" class="row-link"
                :data-testid="`prj-suite-${s.suiteId}`" @click="openSuite(s)">
              <td>
                <div class="sl-name">{{ s.name }}<span v-if="s.isDraft" class="badge draft">草稿</span></div>
                <div class="sl-sid muted">{{ s.description || '—' }}</div>
              </td>
              <td><span class="muted">{{ s.mode }}</span></td>
              <td><span class="muted">{{ s.memberCount }}</span></td>
              <td><span class="muted">{{ formatTime(s.updatedAt ?? undefined) }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="suiteLoaded" class="empty">本项目还没有用例集。</p>
      </template>

      <template v-else-if="tab === 'tasks'">
        <table class="tbl" v-if="tasks.length">
          <thead><tr><th>名称</th><th style="width:130px">调度</th><th style="width:110px">引用</th><th style="width:90px">状态</th></tr></thead>
          <tbody>
            <tr v-for="t in tasks" :key="t.id" class="row-link"
                :data-testid="`prj-task-${t.id}`" @click="$router.push(`/integrations/${t.id}`)">
              <td><div class="sl-name">{{ t.name }}</div></td>
              <td><span class="muted">{{ t.cronText }}</span></td>
              <td><span class="muted">{{ t.scenarioId ?? t.suiteId ?? '—' }}</span></td>
              <td><span class="muted">{{ t.instance?.state ?? '—' }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="taskLoaded" class="empty">本项目还没有集成任务 —— 集成中心创建时选择项目内场景即可挂到本项目。</p>
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
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getProject, type ProjectOut } from '@/api/projects'
import { projectRoleLabel } from '@/utils/projectRole'
import { listScenarios } from '@/api/scenario-composer'
import type { ScenarioListItem } from '@/types/scenario-composer'
import { listSuites, createSuite, type SuiteSummary } from '@/api/suites'
import { listIntegrationTasks, type IntegrationTaskItem } from '@/api/integration'
import ProjectMembersPanel from '@/components/project/ProjectMembersPanel.vue'
import ProjectConfigPanel from '@/components/project/ProjectConfigPanel.vue'
import PromotionsPanel from '@/components/project/PromotionsPanel.vue'
import ProjectTokensPanel from '@/components/project/ProjectTokensPanel.vue'
import { shortDateTime } from '@/utils/datetime'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'

const ScenariosPublic = defineAsyncComponent(() => import('@/views/ScenariosPublic.vue'))
const SuitesPublic = defineAsyncComponent(() => import('@/views/SuitesPublic.vue'))

const route = useRoute()
const router = useRouter()
const formatTime = shortDateTime

const project = ref<ProjectOut | null>(null)
const notFound = ref(false)

const TABS = [
  { key: 'scenarios', label: '场景' },
  { key: 'suites', label: '用例集' },
  { key: 'tasks', label: '集成任务' },
  // S7.2:加入申请(管理员裁决;成员看自己的 —— 后端按角色过滤)
  { key: 'promotions', label: '加入申请' },
  { key: 'members', label: '成员' },
  // S7.3:配置(普通项目 = 默认环境/项目层 carry/槽位状态/生效预览;
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
const roleLabel = projectRoleLabel
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

/** 页签徽标计数(详情端点的内容计数;拉取前 = null 不显) */
function tabCount(key: TabKey): number | null {
  const p = project.value
  if (!p) return null
  if (key === 'scenarios') return p.scenarioCount ?? null
  if (key === 'suites') return p.suiteCount ?? null
  if (key === 'tasks') return p.taskCount ?? null
  if (key === 'members') return p.memberCount ?? null
  return null
}

async function refreshDetail(): Promise<void> {
  if (project.value) {
    try { project.value = await getProject(project.value.id) } catch { /* 保持旧值 */ }
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
.page { padding: 1rem 1.5rem; display: flex; flex-direction: column; gap: 0.9rem; }
.head { display: flex; align-items: baseline; gap: 0.8rem; flex-wrap: wrap; }
.head h1 { margin: 0; font-size: 1.2rem; }
.row-title { display: flex; align-items: center; gap: 0.5rem; }
.sub { color: #64748b; font-size: 0.85rem; flex: 1; margin: 0; }
.meta { color: #94a3b8; font-size: 0.78rem; }
.tabs { display: flex; gap: 0.25rem; border-bottom: 1px solid #e2e8f0; }
.tab { border: none; background: none; padding: 0.45rem 0.9rem; cursor: pointer; font-size: 0.88rem; color: #64748b; border-bottom: 2px solid transparent; }
.tab.on { color: #2563eb; border-bottom-color: #2563eb; font-weight: 600; }
.cnt { margin-left: 4px; font-size: 0.72rem; color: #94a3b8; }
.toolbar { display: flex; gap: 0.5rem; align-items: center; }
.search { padding: 6px 10px; font-size: 12.5px; border-radius: 8px; border: 1px solid rgb(100 116 139 / 30%); background: transparent; color: inherit; max-width: 280px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 0.85rem; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
.tbl th, .tbl td { text-align: left; padding: 0.45rem 0.6rem; border-bottom: 1px solid #eef2f7; }
.tbl th { background: #f8fafc; color: #64748b; font-weight: 500; }
.row-link { cursor: pointer; }
.row-link:hover td { background: #f8fafc; }
.sl-name { font-weight: 500; }
.sl-sid { color: #94a3b8; font-size: 0.72rem; }
.muted { color: #94a3b8; }
.badge { font-size: 0.7rem; padding: 1px 8px; border-radius: 999px; background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }
.badge.pub { background: rgb(37 99 235 / 8%); color: #2563eb; border-color: rgb(37 99 235 / 30%); }
.badge.draft { margin-left: 6px; }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.3rem 0.8rem; background: #fff; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn.sm { padding: 0.15rem 0.5rem; font-size: 0.78rem; }
.pager { display: flex; align-items: center; gap: 0.6rem; }
.empty { color: #94a3b8; }
</style>
