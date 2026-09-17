<!-- Sidebar.vue — 四域侧边栏(重构方案 Phase 1:导航范式更换)。
     结构基准 = F-sitemap:工作台入口置顶,场景 / 服务(分组标签,不可点)
     / 执行中心 / 平台 四组;常量池不再占侧边栏坑位(工作台卡片 +
     "管理"深链承接)。沿用 TopNav 的两条既有语义:adminOnly 过滤
     (用户管理 / 传递字段仅 admin 可见)与适配中心 pendingCount 徽标
     (admin + >0 才显示)。常驻底部:用户身份 + 登出。 -->
<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="status-dot" title="服务在线"></span>
      <span class="brand-text">platform</span>
    </div>

    <nav class="nav">
      <router-link
        v-for="entry in flatEntries"
        :key="entry.path"
        :to="entry.path"
        class="nav-item"
        :class="{ active: isActive(entry.path), 'group-first': entry.firstOfGroup }"
      >
        <span class="group-label" v-if="entry.firstOfGroup && entry.group">{{ entry.group }}</span>
        <span class="row">
          <component :is="entry.icon" class="nav-icon" />
          <span class="nav-text">{{ entry.label }}</span>
          <span
            v-if="entry.path === '/adaptations' && auth.isAdmin && adaptations.pendingCount > 0"
            class="nav-badge"
          >{{ adaptations.pendingCount }}</span>
        </span>
      </router-link>
    </nav>

    <div class="sidebar-footer">
      <span class="user-info" v-if="auth.currentUser">
        <span class="username">{{ auth.currentUser.display_name || auth.currentUser.username }}</span>
        <span class="role">{{ auth.currentUser.is_admin ? 'admin' : 'member' }}</span>
      </span>
      <button class="logout-btn" @click="onLogout">登出</button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  ActivityLogIcon,
  ArchiveIcon,
  CounterClockwiseClockIcon,
  GearIcon,
  HomeIcon,
  LockClosedIcon,
  MixerHorizontalIcon,
} from '@radix-icons/vue'
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

interface SidebarEntry {
  path: string
  label: string
  icon: Component
  /** Render only for admins (route guard would bounce members anyway). */
  adminOnly?: boolean
}

interface SidebarGroup {
  /** 组标签(null = 置顶的无组条目,如工作台)。 */
  label: string | null
  entries: SidebarEntry[]
}

// 结构基准 = F-sitemap v2:服务组顺序 认证管理/传递字段/适配中心;
// 常量池不进侧边栏(工作台卡片承接,/constants 仅深链可达)。
const groups: SidebarGroup[] = [
  { label: null, entries: [{ path: '/home', label: '工作台', icon: HomeIcon }] },
  { label: '场景', entries: [{ path: '/scenarios', label: '场景库', icon: ArchiveIcon }] },
  {
    label: '服务',
    entries: [
      { path: '/auths', label: '认证管理', icon: LockClosedIcon },
      { path: '/carry-config', label: '传递字段', icon: MixerHorizontalIcon, adminOnly: true },
      { path: '/adaptations', label: '适配中心', icon: ActivityLogIcon },
    ],
  },
  { label: '执行中心', entries: [{ path: '/executions', label: '执行历史', icon: CounterClockwiseClockIcon }] },
  { label: '平台', entries: [{ path: '/admin/users', label: '用户管理', icon: GearIcon, adminOnly: true }] },
]

interface FlatEntry extends SidebarEntry {
  group: string | null
  firstOfGroup: boolean
}

// Hide admin-only entries from members entirely (previously it rendered
// for everyone and clicking it bounced off the router guard).
const flatEntries = computed<FlatEntry[]>(() =>
  groups.flatMap((g) =>
    g.entries
      .filter((e) => !e.adminOnly || auth.currentUser?.is_admin)
      .map((e, i) => ({ ...e, group: g.label, firstOfGroup: i === 0 })),
  ),
)

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}

async function onLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
/* preflight 关闭环境:尺寸/边距全部显式声明 */
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 200px;
  display: flex;
  flex-direction: column;
  background: #0b0e14;
  color: #cbd5e1;
  z-index: 1000;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22d3ee;
  box-shadow: 0 0 4px rgba(34, 211, 238, 0.6);
  flex-shrink: 0;
}

.brand-text {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #f8fafc;
}

.nav {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.nav-item {
  display: block;
  text-decoration: none;
  border-radius: 6px;
}

/* 组标签:跟随组内第一条目渲染(非可点的纯标签) */
.group-label {
  display: block;
  padding: 14px 8px 4px;
  font-size: 11px;
  color: #64748b;
  user-select: none;
}

/* 置顶无组条目与组内条目的行高一致;组标签占额外高度 */
.nav-item.group-first:not(:first-child) {
  margin-top: 6px;
}

.row {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  padding: 0 8px;
  border-radius: 6px;
  font-size: 13px;
  color: #cbd5e1;
  transition: background 0.15s ease, color 0.15s ease;
}

.nav-item:hover .row {
  background: rgba(255, 255, 255, 0.06);
  color: #ffffff;
}

.nav-item.active .row {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  font-weight: 600;
}

.nav-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.nav-text {
  flex: 1;
  white-space: nowrap;
}

.nav-badge {
  min-width: 18px;
  height: 18px;
  line-height: 18px;
  padding: 0 6px;
  border-radius: 9px;
  background: #dc2626;
  color: #ffffff;
  font-size: 11px;
  text-align: center;
}

.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.user-info {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.username {
  font-size: 12px;
  color: #f8fafc;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.role {
  font-size: 11px;
  color: #64748b;
  flex-shrink: 0;
}

.logout-btn {
  height: 26px;
  padding: 0 10px;
  font-size: 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  background: transparent;
  color: #cbd5e1;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}

.logout-btn:hover {
  border-color: #2f6fed;
  color: #ffffff;
}
</style>
