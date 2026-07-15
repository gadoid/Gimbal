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