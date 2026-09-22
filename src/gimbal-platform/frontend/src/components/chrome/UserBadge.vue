<!-- UserBadge.vue — chrome 上的用户身份区(侧栏底部 / 收拢顶条右端共用)。
     layout = 'bar'(默认):横排单行 = 铃铛 + 身份下拉(个人设置/登出),
     适配 48px 收拢顶条;
     layout = 'footer':侧栏底部两行(定稿 2026-09-22)——
       第一行 = 用户名 + 用户类型(整行可点 → 个人设置),
       第二行 = 通知铃铛 + 登出按钮;下拉菜单退役。
     compact(折叠态)随 footer 语义走:首字圆徽 / 铃铛 / 登出纵排。
     深色 chrome 专用;Signal token 经 @apply 消费,不零散写 hex。 -->
<template>
  <!-- 折叠态:纵排图标轨(圆徽 → 个人设置) -->
  <div v-if="compact" class="flex flex-col items-center gap-2">
    <button
      v-if="auth.currentUser"
      class="username flex h-7 w-7 cursor-pointer items-center justify-center rounded-full bg-white/10 text-caption font-semibold text-slate-50 hover:bg-white/20"
      :title="badgeTitle"
      aria-label="个人设置"
      data-testid="user-badge-profile"
      @click="goProfile"
    >
      {{ initial }}
    </button>
    <NotificationBell />
    <button
      class="logout-btn flex h-7 w-7 cursor-pointer items-center justify-center rounded-md border border-white/20 bg-transparent text-slate-300 transition-colors hover:border-signal hover:text-white"
      title="登出"
      aria-label="登出"
      @click="onLogout"
    >
      <ExitIcon class="h-3 w-3" />
    </button>
  </div>

  <!-- 侧栏底部:两行定稿 -->
  <div v-else-if="layout === 'footer'" class="flex w-full flex-col gap-1.5">
    <button
      type="button"
      class="identity-row flex w-full cursor-pointer items-center justify-between gap-2 rounded-md px-1 py-0.5 text-left transition-colors hover:bg-white/5"
      title="个人设置"
      data-testid="user-badge-trigger"
      @click="goProfile"
    >
      <span v-if="auth.currentUser" class="username min-w-0 truncate text-body font-medium text-slate-50">
        {{ auth.currentUser.display_name || auth.currentUser.username }}
      </span>
      <span class="role-chip shrink-0">{{ roleLabel }}</span>
    </button>
    <div class="flex w-full items-center justify-between gap-2">
      <NotificationBell />
      <button
        class="logout-btn flex h-[26px] cursor-pointer items-center gap-1 rounded-chip border border-white/20 bg-transparent px-2 text-caption text-slate-300 transition-colors hover:border-signal-failed hover:text-white"
        title="登出"
        data-testid="user-badge-logout"
        aria-label="登出"
        @click="onLogout"
      >
        <ExitIcon class="h-3 w-3" />
        <span>退出</span>
      </button>
    </div>
  </div>

  <!-- 收拢顶条:横排单行(铃铛 + 身份下拉) -->
  <div v-else class="flex shrink-0 items-center gap-3">
    <NotificationBell />
    <DropdownMenu>
      <DropdownMenuTrigger as-child>
        <button
          class="identity-trigger flex cursor-pointer items-center gap-1 rounded-chip border border-transparent px-1.5 py-0.5 transition-colors hover:border-white/20"
          data-testid="user-badge-trigger"
        >
          <span v-if="auth.currentUser" class="flex items-center gap-1">
            <span class="username max-w-24 truncate text-body font-medium text-slate-50">
              {{ auth.currentUser.display_name || auth.currentUser.username }}
            </span>
            <span class="role-chip">{{ roleLabel }}</span>
          </span>
          <ChevronDownIcon class="h-3 w-3 text-slate-400" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" class="w-44">
        <div class="px-2 py-1.5">
          <p class="text-body font-medium">{{ auth.currentUser?.username }}</p>
          <p class="text-caption text-slate-500">{{ roleLabel }} · 个人设置在此管理账号</p>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem data-testid="user-badge-profile-item" @click="goProfile">
          <GearIcon class="h-3.5 w-3.5" /> 个人设置
        </DropdownMenuItem>
        <DropdownMenuItem class="text-signal-failed" data-testid="user-badge-logout" @click="onLogout">
          <ExitIcon class="h-3.5 w-3.5" /> 登出
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ChevronDownIcon, ExitIcon, GearIcon } from '@radix-icons/vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NotificationBell from '@/components/chrome/NotificationBell.vue'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

withDefaults(defineProps<{
  compact?: boolean
  /** bar = 收拢顶条单行下拉;footer = 侧栏底部两行定稿。 */
  layout?: 'bar' | 'footer'
}>(), { layout: 'bar' })

const auth = useAuthStore()
const router = useRouter()

const ROLE_LABELS: Record<string, string> = { member: '成员', operator: '运维', admin: '管理员' }
const roleLabel = computed(() => ROLE_LABELS[auth.role] ?? auth.role)

const initial = computed(() =>
  (auth.currentUser?.display_name || auth.currentUser?.username || '?').slice(0, 1),
)

const badgeTitle = computed(() => {
  const name = auth.currentUser?.display_name || auth.currentUser?.username || ''
  return `${name}(${roleLabel.value})`
})

function goProfile() {
  router.push('/profile')
}

async function onLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.role-chip {
  padding: 0 6px;
  border-radius: 999px;
  font-size: 10px;
  background: rgba(255, 255, 255, 0.12);
  color: #cbd5e1;
}
</style>
