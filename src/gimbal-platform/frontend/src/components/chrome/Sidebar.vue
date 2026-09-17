<!-- Sidebar.vue — 四域侧边栏(重构方案 Phase 1:导航范式更换)。
     结构基准 = F-sitemap:工作台入口置顶,场景 / 服务(分组标签,不可点)
     / 执行中心 / 平台 四组;常量池不再占侧边栏坑位(工作台卡片 +
     "管理"深链承接)。沿用 TopNav 的两条既有语义:adminOnly 过滤
     (用户管理 / 传递字段仅 admin 可见)与适配中心 pendingCount 徽标
     (admin + >0 才显示)。常驻底部:用户身份 + 登出(UserBadge)。
     颜色全部经 Signal token(@apply),组件内零散 hex 为零;暗底上的
     灰阶用 Tailwind 标准 slate 阶(Signal 色板未定义暗底文字档)。 -->
<template>
  <aside class="sidebar fixed inset-y-0 left-0 z-[1000] flex w-[200px] flex-col bg-signal-sidebar text-slate-300">
    <div class="flex items-center gap-2 px-4 pb-3 pt-3.5">
      <span class="status-dot h-2 w-2 shrink-0 rounded-full bg-signal-dot" title="服务在线"></span>
      <span class="text-body font-semibold tracking-wide text-slate-50">platform</span>
    </div>

    <nav class="flex-1 overflow-y-auto px-2">
      <router-link
        v-for="entry in flatEntries"
        :key="entry.path"
        :to="entry.path"
        class="nav-item block rounded-md"
        :class="{ active: isActive(entry.path) }"
      >
        <span v-if="entry.firstOfGroup && entry.group" class="group-label block select-none px-2 pb-1 pt-4 text-caption text-slate-500">
          {{ entry.group }}
        </span>
        <span
          class="row flex h-8 items-center gap-2 rounded-md px-2 text-body transition-colors duration-150"
          :class="isActive(entry.path)
            ? 'bg-white/10 font-semibold text-white'
            : 'text-slate-300 hover:bg-white/5 hover:text-white'"
        >
          <component :is="entry.icon" class="nav-icon h-3.5 w-3.5 shrink-0" />
          <span class="nav-text flex-1 whitespace-nowrap">{{ entry.label }}</span>
          <span
            v-if="entry.path === '/adaptations' && auth.isAdmin && adaptations.pendingCount > 0"
            class="nav-badge h-[18px] min-w-[18px] rounded-full bg-signal-failed px-1.5 text-center text-caption leading-[18px] text-white"
          >{{ adaptations.pendingCount }}</span>
        </span>
      </router-link>
    </nav>

    <div class="flex items-center justify-between gap-2 border-t border-white/10 px-4 py-3">
      <UserBadge />
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
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
import UserBadge from '@/components/chrome/UserBadge.vue'

const auth = useAuthStore()
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
</script>
