<!-- Sidebar.vue — v2 left navigation, replacing TopNav.vue.
     Fixed 220px (--sidebar-width) dark chrome, groups entries by how
     they're actually used instead of one flat row:
       核心工作流 (opened daily)      — 场景库 / 执行历史 / 适配中心
       共享资源   (consumed by the    — 认证管理 / 常量池
                    workflow, e.g. composer's AuthSelectorModal/
                    ConstantPoolPanel — also standalone admin pages)
       后台配置   (admin-only setup)  — 传递字段 / 用户管理
     Only mounted when auth.isAuthenticated (caller in App.vue handles it). -->
<template>
  <aside class="sidebar">
    <div class="sidebar-brand">
      <span class="status-dot" :title="statusTitle"></span>
      <span class="brand-text">platform</span>
    </div>

    <nav class="sidebar-nav">
      <div v-for="group in navGroups" :key="group.label" class="nav-group">
        <div class="nav-section-label">{{ group.label }}</div>
        <router-link
          v-for="entry in group.entries"
          :key="entry.path"
          :to="entry.path"
          class="nav-entry"
          :class="{ active: isActive(entry.path) }"
        ><el-icon><component :is="entry.icon" /></el-icon>{{ entry.label }}<span
            v-if="entry.path === '/adaptations' && auth.isAdmin && adaptations.pendingCount > 0"
            class="nav-badge"
          >{{ adaptations.pendingCount }}</span></router-link>
      </div>
    </nav>

    <div class="sidebar-user" v-if="auth.currentUser">
      <span class="user-info">
        <span class="username">{{ auth.currentUser.display_name || auth.currentUser.username }}</span>
        <span class="role">({{ auth.currentUser.is_admin ? 'admin' : 'member' }})</span>
      </span>
      <el-button
        type="primary"
        plain
        size="small"
        class="logout-btn"
        @click="onLogout"
      >登出</el-button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Coin,
  Collection,
  Connection,
  DataAnalysis,
  Lock,
  Postcard,
  Setting,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useAdaptationsStore } from '@/stores/adaptations'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const adaptations = useAdaptationsStore()

// D3:admin 登录/刷新后静默拉一次 diff(幂等,冷启动落基线属预期副作用)
watch(
  () => auth.currentUser?.is_admin,
  (isAdmin) => {
    if (isAdmin) void adaptations.ensureBadgeLoaded()
  },
  { immediate: true },
)

interface NavEntry {
  path: string
  label: string
  icon: Component
  /** Render only for admins (route guard would bounce members anyway). */
  adminOnly?: boolean
}

interface NavGroup {
  label: string
  entries: NavEntry[]
}

const allGroups: NavGroup[] = [
  {
    label: '核心工作流',
    entries: [
      { path: '/scenarios', label: '场景库', icon: Collection },
      { path: '/executions', label: '执行历史', icon: DataAnalysis },
      { path: '/adaptations', label: '适配中心', icon: Connection },
    ],
  },
  {
    label: '共享资源',
    entries: [
      { path: '/auths', label: '认证管理', icon: Lock },
      { path: '/constants', label: '常量池', icon: Coin },
    ],
  },
  {
    label: '后台配置',
    entries: [
      { path: '/carry-config', label: '传递字段', icon: Postcard, adminOnly: true },
      { path: '/admin/users', label: '用户管理', icon: Setting, adminOnly: true },
    ],
  },
]

// Hide admin-only entries from members entirely, and drop a group that
// ends up empty (a member never sees an empty "后台配置" section).
const navGroups = computed(() =>
  allGroups
    .map((group) => ({
      label: group.label,
      entries: group.entries.filter((e) => !e.adminOnly || auth.currentUser?.is_admin),
    }))
    .filter((group) => group.entries.length > 0),
)

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}

const statusTitle = '服务在线'

async function onLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: var(--sidebar-width, 220px);
  display: flex;
  flex-direction: column;
  background: #1f2933;
  color: #e2e8f0;
  font-size: 12px;
  z-index: 1000;
  box-shadow: 1px 0 3px rgba(0, 0, 0, 0.15);
  box-sizing: border-box;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 48px;
  padding: 0 16px;
  flex-shrink: 0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 4px rgba(34, 197, 94, 0.6);
  flex-shrink: 0;
}

.brand-text {
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #f5f3ff;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-group + .nav-group {
  margin-top: 8px;
}

.nav-section-label {
  padding: 8px 10px 4px;
  color: #f5f3ff;
  opacity: 0.55;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.nav-entry {
  display: flex;
  align-items: center;
  height: 32px;
  padding: 0 10px;
  border-radius: 4px;
  color: #cbd5e1;
  text-decoration: none;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  transition: background 0.15s ease, color 0.15s ease;
  cursor: pointer;
  user-select: none;
}
.nav-entry .el-icon {
  margin-right: 8px;
}

.nav-entry:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.nav-entry.active {
  background: #ede9fe;
  color: #1f2933;
  font-weight: 600;
}

.nav-entry.active:hover {
  background: #ede9fe;
  color: #1f2933;
}

.nav-badge {
  margin-left: auto;
  padding: 0 6px;
  min-width: 18px;
  height: 18px;
  line-height: 18px;
  border-radius: 9px;
  background: #f56c6c;
  color: #fff;
  font-size: 12px;
  text-align: center;
}

.sidebar-user {
  flex-shrink: 0;
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.user-info {
  display: flex;
  align-items: baseline;
  gap: 4px;
  color: #cbd5e1;
  min-width: 0;
}

.username {
  color: #f5f3ff;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
}

.role {
  color: #94a3b8;
  font-size: 11px;
  flex-shrink: 0;
}

.logout-btn {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
  width: 100%;
}
</style>
