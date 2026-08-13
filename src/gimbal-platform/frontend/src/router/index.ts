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

const routes = [
  { path: '/', redirect: '/cases/mine' },
  { path: '/login', component: () => import('@/views/Login.vue') },
  { path: '/register', component: () => import('@/views/Register.vue') },
  // protected
  {
    path: '/cases/mine',
    component: () => import('@/views/CasesMine.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/cases/public',
    component: () => import('@/views/CasesPublic.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/cases/:caseId/config',
    component: () => import('@/views/CaseConfigReadonly.vue'),
    meta: { requiresAuth: true },
  },

  // ── 场景编排 V3 ────────────────────────────────────────────
  {
    path: '/scenarios',
    component: () => import('@/views/Scenarios.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 用例编排 (V3) 专用页面 — 一个页面承载 4 步流程 (Meta → Resource → Config → Canvas)
    // /composer/new         新建 (空白草稿)
    // /composer/:scenarioId 编辑已有
    // ?step=1..4            直接跳到某一步
    path: '/composer/:scenarioId',
    component: () => import('@/views/CaseComposer.vue'),
    meta: { requiresAuth: true },
  },
  {
    // /scenarios/new/edit 或 /scenarios/:scenarioId/edit  (① 基本信息 — 旧版入口,跳转到新页面)
    path: '/scenarios/:scenarioId/edit',
    redirect: (to: any) => ({ path: `/composer/${to.params.scenarioId}`, query: { step: '1' } }),
    meta: { requiresAuth: true },
  },
  {
    // /scenarios/:scenarioId/steps (② 步骤编排 — 旧版入口)
    path: '/scenarios/:scenarioId/steps',
    redirect: (to: any) => ({ path: `/composer/${to.params.scenarioId}`, query: { step: '4' } }),
    meta: { requiresAuth: true },
  },
  {
    // /scenarios/:scenarioId/cases (③ 用例管理 — 旧版入口)
    path: '/scenarios/:scenarioId/cases',
    component: () => import('@/views/CasesOfScenario.vue'),
    meta: { requiresAuth: true },
  },
  {
    // /cases/new/edit 或 /cases/:caseId/edit
    path: '/cases/:caseId/edit',
    component: () => import('@/views/CaseEditorBasic.vue'),
    meta: { requiresAuth: true },
  },
  {
    // /cases/:caseId/data-sets (④ 数据集列表)
    path: '/cases/:caseId/data-sets',
    component: () => import('@/views/CaseDataSetsList.vue'),
    meta: { requiresAuth: true },
  },
  {
    // /cases/:caseId/data-sets/new 或 /:datasetId
    path: '/cases/:caseId/data-sets/:datasetId',
    component: () => import('@/views/DataSetEditor.vue'),
    meta: { requiresAuth: true },
  },
  {
    // 跨场景用例总览
    path: '/cases-overview',
    component: () => import('@/views/Cases.vue'),
    meta: { requiresAuth: true },
  },
  {
    // /cases/:caseId/run（运行配置）
    path: '/cases/:caseId/run',
    component: () => import('@/views/CaseRunConfig.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/admin/users',
    component: () => import('@/views/UsersAdmin.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/auths',
    component: () => import('@/views/Auths.vue'),
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
  if ((to.path === '/login' || to.path === '/register') && auth.accessToken) {
    return { path: '/cases/mine' }
  }
})

export default router