<!-- Sidebar.vue — 四域侧边栏(重构方案 Phase 1:导航范式更换)+ 整体折叠。
     结构基准 = F-sitemap:工作台入口置顶,场景 / 服务(分组标签,不可点)
     / 执行中心 / 平台 四组;常量池不再占侧边栏坑位(工作台卡片 +
     "管理"深链承接)。沿用 TopNav 的两条既有语义:adminOnly 过滤
     (用户管理 / 传递字段仅 admin 可见)与适配中心 pendingCount 徽标
     (admin + >0 才显示)。常驻底部:用户身份 + 登出(UserBadge)。
     折叠态(« 钮切换,localStorage 持久化):200px → 56px 图标轨道 —
     brand 只留状态点;一级层次(组标签)保留小字;二级按钮只留图标,
     悬浮 title 提示功能名;pendingCount 退化为图标角点。
     颜色全部经 Signal token(@apply),组件内零散 hex 为零;暗底上的
     灰阶用 Tailwind 标准 slate 阶(Signal 色板未定义暗底文字档)。 -->
<template>
  <aside
    class="sidebar fixed inset-y-0 left-0 z-[1000] flex flex-col bg-signal-sidebar text-slate-300 transition-[width] duration-200"
    :class="collapsed ? 'w-[56px]' : 'w-[200px]'"
  >
    <!-- brand 行:展开 = 状态点 + platform + 折叠钮;折叠 = 状态点 + 折叠钮纵排。
         brand 可点 → 回工作台(/home);折叠态状态点承接同一入口。 -->
    <div v-if="collapsed" class="flex flex-col items-center gap-2 pb-3 pt-3.5">
      <router-link
        to="/home"
        class="status-dot flex h-5 w-5 items-center justify-center rounded-md transition-colors hover:bg-white/5"
        title="回到工作台"
        aria-label="回到工作台"
        data-testid="sb-brand"
      >
        <span class="h-2 w-2 rounded-full bg-signal-dot"></span>
      </router-link>
      <button
        type="button"
        class="collapse-toggle flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-slate-400 transition-colors duration-150 hover:bg-white/5 hover:text-white"
        :data-testid="'sb-expand'"
        title="展开侧边栏"
        aria-label="展开侧边栏"
        @click="toggle"
      >
        <ChevronRightIcon class="h-3.5 w-3.5" />
      </button>
    </div>
    <div v-else class="flex items-center gap-2 px-4 pb-3 pt-3.5">
      <router-link
        to="/home"
        class="flex min-w-0 items-center gap-2 rounded-md py-0.5 pr-1 text-inherit no-underline transition-colors hover:bg-white/5"
        title="回到工作台"
        aria-label="回到工作台"
        data-testid="sb-brand"
      >
        <span class="status-dot h-2 w-2 shrink-0 rounded-full bg-signal-dot" title="服务在线"></span>
        <span class="text-body font-semibold tracking-wide text-slate-50">platform</span>
      </router-link>
      <span class="flex-1"></span>
      <button
        type="button"
        class="collapse-toggle flex h-6 w-6 cursor-pointer items-center justify-center rounded-md text-slate-400 transition-colors duration-150 hover:bg-white/5 hover:text-white"
        :data-testid="'sb-collapse'"
        title="折叠侧边栏"
        aria-label="折叠侧边栏"
        @click="toggle"
      >
        <ChevronLeftIcon class="h-3.5 w-3.5" />
      </button>
    </div>

    <nav class="nav-scroll flex-1 overflow-y-auto" :class="collapsed ? 'px-1.5' : 'px-2'">
      <component
        :is="entry.disabled ? 'span' : 'router-link'"
        v-for="entry in flatEntries"
        :key="entry.path"
        :to="entry.disabled ? undefined : entry.path"
        class="nav-item block rounded-md"
        :class="{ active: isActive(entry.path), 'opacity-[.42]': entry.disabled || entry.dimmed }"
        :title="entry.disabled ? (entry.disabledTitle ?? entry.label)
          : entry.dimmed ? (entry.dimmedTitle ?? entry.label) : undefined"
      >
        <!-- 一级层次(组标签)两态都保留:折叠 = 居中小字(仅一级可见) -->
        <span
          v-if="entry.firstOfGroup && entry.group"
          class="group-label block select-none pb-1 pt-4 text-caption text-slate-500"
          :class="collapsed ? 'px-0 text-center text-[9px] leading-tight' : 'px-2'"
        >
          {{ entry.group }}
        </span>
        <!-- 二级按钮:折叠 = 只留图标,title 悬浮提示功能名 -->
        <span
          class="row relative flex h-8 items-center gap-2 rounded-md text-body transition-colors duration-150"
          :class="[
            collapsed ? 'justify-center px-0' : 'px-2',
            isActive(entry.path)
              ? 'bg-white/10 font-semibold text-white'
              : entry.disabled
                ? 'cursor-default text-slate-300'
                : 'text-slate-300 hover:bg-white/5 hover:text-white',
          ]"
          :title="collapsed ? entry.label : undefined"
          :aria-label="collapsed ? entry.label : undefined"
        >
          <component :is="entry.icon" class="nav-icon h-3.5 w-3.5 shrink-0" />
          <span v-if="!collapsed" class="nav-text flex-1 whitespace-nowrap">{{ entry.label }}</span>
          <span
            v-if="!collapsed && entry.path === '/adaptations' && auth.isAdmin && adaptations.pendingCount > 0"
            class="nav-badge h-[18px] min-w-[18px] rounded-full bg-signal-failed px-1.5 text-center text-caption leading-[18px] text-white"
          >{{ adaptations.pendingCount }}</span>
          <!-- 折叠态徽标退化为图标右上角红点(title 带数值) -->
          <span
            v-if="collapsed && entry.path === '/adaptations' && auth.isAdmin && adaptations.pendingCount > 0"
            class="nav-badge-dot absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-signal-failed"
            :title="`${adaptations.pendingCount} 条适配待处理`"
          ></span>
        </span>
      </component>
    </nav>

    <div
      class="flex items-center justify-between gap-2 border-t border-white/10 py-3"
      :class="collapsed ? 'flex-col px-0' : 'flex-col px-4'"
    >
      <UserBadge :compact="collapsed" layout="footer" />
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
  BarChartIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CounterClockwiseClockIcon,
  GearIcon,
  GlobeIcon,
  GridIcon,
  HomeIcon,
  LayersIcon,
  LockClosedIcon,
  MagnifyingGlassIcon,
  MixerHorizontalIcon,
  PlayIcon,
  StarIcon,
} from '@radix-icons/vue'
import { useAuthStore } from '@/stores/auth'
import { useAdaptationsStore } from '@/stores/adaptations'
import { useSidebarCollapse } from '@/composables/sidebar-collapse'
import UserBadge from '@/components/chrome/UserBadge.vue'

const auth = useAuthStore()
const route = useRoute()

const adaptations = useAdaptationsStore()

const { collapsed, toggle } = useSidebarCollapse()

// D3:admin 登录/刷新后静默拉一次 diff(幂等,冷启动落基线属预期副作用)
watch(
  () => auth.role,
  (role) => {
    if (role !== 'member') void adaptations.ensureBadgeLoaded()
  },
  { immediate: true },
)

interface SidebarEntry {
  path: string
  label: string
  icon: Component
  /** Render only for admins (route guard would bounce members anyway). */
  adminOnly?: boolean
    /** M2.5:角色白名单(adminOnly 的泛化;适配/别名/默认值 = operator+) */
    roles?: string[]
  /** 未落地入口:置灰且不可点(字段来源分析 — E2 未建,无页面可落)。 */
  disabled?: boolean
  disabledTitle?: string
  /** 延后但有自己的说明页(§4.4):置灰保留、可点进去撞上那条说明;
   *  它自己这一页正常高亮 + 延后小标。 */
  dimmed?: boolean
  dimmedTitle?: string
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
  {
    label: '场景',
    entries: [
      { path: '/scenarios/mine', label: '我的场景', icon: ArchiveIcon },
      { path: '/scenarios/public', label: '公共场景', icon: GlobeIcon },
      { path: '/scenarios/follows', label: '关注', icon: StarIcon },
    ],
  },
  {
    label: '服务',
    entries: [
      { path: '/services', label: '服务画像', icon: GridIcon },
      { path: '/service-admin', label: '服务信息管理', icon: LayersIcon, roles: ['operator', 'admin'] },
      { path: '/auths', label: '认证管理', icon: LockClosedIcon },
      // 配套方案 §2.2:传递字段 → 默认值(服务/别名绑定层已并进
      // 服务信息管理的键详情,本页只剩跨服务兜底层)
      { path: '/carry-config', label: '默认值', icon: MixerHorizontalIcon, roles: ['operator', 'admin'] },
      { path: '/adaptations', label: '适配中心', icon: ActivityLogIcon },
    ],
  },
  // 执行组(执行设计 §0):执行器(/run)/ 执行记录;字段来源分析(E2a)
  // 置灰不可点;数据分析(延后)置灰但可点 — §4.4:延后的东西藏起来会被
  // 遗忘,留灰入口,点进去撞上那条说明;opacity .42,不加角标。
  { label: '执行', entries: [
    { path: '/run', label: '执行器', icon: PlayIcon },
    { path: '/field-trace', label: '字段来源分析', icon: MagnifyingGlassIcon, disabled: true, disabledTitle: '字段来源分析 — 待 E2a 落地(预测模式无前置,事实模式等执行时快照)' },
    { path: '/executions', label: '执行记录', icon: CounterClockwiseClockIcon },
    { path: '/analytics', label: '数据分析', icon: BarChartIcon, dimmed: true, dimmedTitle: '数据分析已延后 — 解锁前置:行级/步骤级结果落库。点进去看说明' },
  ] },
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
      .filter((e) => !e.adminOnly && !e.roles
        || (e.adminOnly && auth.isAdmin)
        || (e.roles && auth.hasRole(...e.roles)))
      .map((e, i) => ({ ...e, group: g.label, firstOfGroup: i === 0 })),
  ),
)

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}
</script>

<style scoped>
/* 导航滑轨:与工作台时间线 .tl-scroll 同一范式(8px 车道挤成 2px 圆胶囊、
   轨道透明、hover 才加深一档、scrollbar-gutter 保住车道防条目跳宽),
   滑块换白系贴 #0B0E14 深色 chrome —— 系统默认灰轨在暗侧栏上像贴错
   系统的补丁。引擎分流原因见 ActivityTimeline 同款注释。 */
.nav-scroll { scrollbar-gutter: stable; }
.nav-scroll::-webkit-scrollbar { width: 8px; }
.nav-scroll::-webkit-scrollbar-track { background: transparent; }
.nav-scroll::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.14);
  border: 3px solid transparent;
  background-clip: content-box;
  border-radius: 999px;
}
.nav-scroll:hover::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.28); }
@supports (-moz-appearance: none) {
  .nav-scroll { scrollbar-width: thin; scrollbar-color: rgba(255, 255, 255, 0.16) transparent; }
}
</style>
