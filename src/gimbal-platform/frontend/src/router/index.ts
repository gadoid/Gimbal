/**
 * router/index.ts — Spec-1 routing table + simple auth guard.
 *
 * Views are dynamic imports so Vite lazy-loads them.  The guard is
 * intentionally lightweight: it checks for an access token in localStorage
 * (via the Pinia auth store) and redirects; token validity is verified by
 * fetchMe() on first protected visit.
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

/** D1 退役路由兜底:旧数据集深链/书签 → 方案工作台(能力承接处),不白屏 */
const dataSetsFallback = (to: { params: Record<string, string | string[]> }) =>
  `/scenarios/${encodeURIComponent(String(to.params.scenarioId))}/schemes`

const routes = [
  // F-sitemap v2:登录后默认落地 = 用户工作台 /home(原为 /scenarios)
  { path: '/', redirect: '/home' },
  { path: '/home', component: () => import('@/views/WorkbenchView.vue'), meta: { requiresAuth: true } },
  { path: '/login', component: () => import('@/views/Login.vue') },
  { path: '/register', component: () => import('@/views/Register.vue') },
  // protected
  // ── 场景编排 V3 ────────────────────────────────────────────
  // 场景库拆三页(我的场景 / 公共场景 / 关注);/scenarios 旧入口重定向到我的场景。
  { path: '/scenarios', redirect: '/scenarios/mine' },
  {
    path: '/scenarios/mine',
    component: () => import('@/views/ScenariosMine.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/scenarios/public',
    component: () => import('@/views/ScenariosPublic.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/scenarios/follows',
    component: () => import('@/views/ScenarioFollows.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 用例编排 (V3) 专用页面 — 一个页面承载 4 步流程 (Meta → Resource → Config → Canvas)
    // /composer/new         新建 (空白草稿)
    // /composer/:scenarioId 编辑已有
    // ?step=1..4            直接跳到某一步
    path: '/composer/:scenarioId',
    component: () => import('@/views/CaseComposer.vue'),
    meta: { requiresAuth: true, chromeMode: 'collapsed' as const },
  },
  {
    // /scenarios/:scenarioId/detail — 场景详情页(数据驱动的可读渲染,
    // 数据源 = composer_scenarios 读侧结构)
    path: '/scenarios/:scenarioId/detail',
    component: () => import('@/views/ScenarioDetailView.vue'),
    meta: { requiresAuth: true },
  },
  // 数据集独立路由已退役(D1,重构方案 Phase 2 批次 0):数据集是方案的
  // 实现模块,能力由方案工作台 SchemeDataSection 承接,不设独立入口。
  // 旧深链/书签兜底重定向到方案工作台,不白屏。
  {
    path: '/scenarios/:scenarioId/data-sets',
    redirect: dataSetsFallback,
  },
  {
    path: '/scenarios/:scenarioId/data-sets/:datasetId',
    redirect: dataSetsFallback,
  },
  {
    // 断言管理编辑器 — 场景级注册表(spec v2 §7)
    path: '/scenarios/:scenarioId/assertions',
    component: () => import('@/views/AssertionRegistryEditor.vue'),
    meta: { requiresAuth: true, chromeMode: 'collapsed' as const },
  },
  {
    // /scenarios/:scenarioId/schemes — 方案工作台(spec 2026-09-14 §6)
    path: '/scenarios/:scenarioId/schemes',
    component: () => import('@/views/SchemeWorkbench.vue'),
    meta: { requiresAuth: true, chromeMode: 'collapsed' as const },
  },
  {
    // carry 值表配置页(T15)— admin 维护入口(TopNav adminOnly);
    // 路由本身只 requiresAuth:member 直接访问时 GET 可读、PUT 由后端 403(spec §6)
    path: '/carry-config',
    component: () => import('@/views/CarryConfig.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/admin/users',
    component: () => import('@/views/UsersAdmin.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    // 通知页(F5,2026-09-23;侧边栏入口名「通知」):全员;审计 tab 仅
    // admin(渲染层隐藏 + 后端 /admin/audit-logs 403 双层守卫,方案 §5.5 T5)
    path: '/notifications',
    component: () => import('@/views/NotificationsCenter.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 个人设置(P2-1):全员
    path: '/profile',
    component: () => import('@/views/Profile.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/auths',
    component: () => import('@/views/Auths.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/constants',
    component: () => import('@/views/ConstantsPool.vue'),
    // 常量池:从顶导航降级,经工作台深链进入(侧边栏收起,见 H-constants)
    meta: { requiresAuth: true, chromeMode: 'collapsed' as const },
  },
  {
    // P5 适配中心 —— admin 全量视图;member 自动只读 owner 视图(页内 scope=mine)
    path: '/adaptations',
    component: () => import('@/views/AdaptationCenter.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/adaptations/batches/:batchId',
    component: () => import('@/views/AdaptationBatchDetail.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 执行器(执行设计 §1):发起入口从运行对话框升为页面 — 队列挑 N 条
    // 逐条顺序发起,按批次在执行记录归并;对话框(编排页)保留单条路径。
    path: '/run',
    component: () => import('@/views/Runner.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/executions',
    component: () => import('@/views/ExecutionsList.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/executions/:id(\\d+)',
    component: () => import('@/views/Executions.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 数据分析(执行设计 §4:本期延后)— 说明页:前置(行级/步骤级结果
    // 落库)+ 已在别处的两个去向。侧边栏入口置灰但可点(§4.4:留个灰
    // 入口,点进来撞上那条说明;本页正常高亮 + 琥珀「延后」小标)。
    path: '/analytics',
    component: () => import('@/views/AnalyticsDeferred.vue'),
    meta: { requiresAuth: true },
  },
  // ── 服务画像 P1(服务画像方案 §5.4)───────────────────────────
  {
    // 落地页:列 plate 目录服务,点进 /services/:name 热力网格
    path: '/services',
    component: () => import('@/views/ServicesIndex.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 服务级热力网格(方案 §2);service 名可含 '-',路由段天然安全
    path: '/services/:name',
    component: () => import('@/views/ServiceGrid.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 接口级线索板(方案 §3);endpoint_id 是点分命名空间(如 fin.order.add)
    path: '/services/:name/endpoints/:endpointId',
    component: () => import('@/views/EndpointBoard.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 服务信息管理(方案 §4;P1 唯一净新增页面)— 配置池,admin 写面
    path: '/service-admin',
    component: () => import('@/views/ServiceAdmin.vue'),
    // 权限方案 §1.2:服务信息管理 = operator+(共享别名行);旧 requiresAdmin 误标修正
    meta: { requiresAuth: true, requiresRoles: ['operator', 'admin'] },
  },
  {
    // 键详情(配套方案 §2.2):别名全名或 base 服务名同一详情页,
    // 字段默认值 tab 在此编辑;?tab=credential 供认证管理反查深链
    path: '/service-admin/:alias',
    component: () => import('@/views/ServiceAliasDetail.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  // /dev/dual-stack 双栈验证页已随 Phase 3 退役(EP 摘除,使命完成)
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.accessToken) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  // M2.5:requiresAdmin 泛化为 requiresRoles(旧 meta 继续有效 = ['admin'])
  const needRoles: string[] = to.meta.requiresRoles
    ?? (to.meta.requiresAdmin ? ['admin'] : [])
  if (needRoles.length && !auth.hasRole(...(needRoles as never[]))) {
    // Backend enforces admin-only on these endpoints too; this is the
    // UX-side guard so members never land on a page that 403s.
    return { path: '/home' }
  }
  if ((to.path === '/login' || to.path === '/register') && auth.accessToken) {
    return { path: '/home' }
  }
})

export default router