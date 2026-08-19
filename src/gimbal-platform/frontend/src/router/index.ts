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
  // P3:场景库统一入口(原 /cases/mine 工作台 + /cases/public 公共库
  // 已退役,合并进 /scenarios 的"我的/公共/收藏"三 tab)
  { path: '/', redirect: '/scenarios' },
  { path: '/login', component: () => import('@/views/Login.vue') },
  { path: '/register', component: () => import('@/views/Register.vue') },
  // protected
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
    // /cases/:caseId 用例只读详情页(查看 · 说明书)
    path: '/cases/:caseId',
    component: () => import('@/views/CaseDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    // /cases/:caseId/data-sets (数据集列表 — 数据集挂在用例下 1:N)
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
    path: '/admin/users',
    component: () => import('@/views/UsersAdmin.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
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
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    // Backend enforces admin-only on these endpoints too; this is the
    // UX-side guard so members never land on a page that 403s.
    return { path: '/scenarios' }
  }
  if ((to.path === '/login' || to.path === '/register') && auth.accessToken) {
    return { path: '/scenarios' }
  }
})

export default router