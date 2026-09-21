<!-- UserBadge.vue — chrome 上的用户身份 + 下拉菜单(侧栏底部 / 收拢顶条
     右端共用,P2-1 改下拉:身份徽章 → 个人设置 → 登出)。深色 chrome 专用;
     Signal token 经 @apply 消费,不零散写 hex。
     compact = 侧栏折叠态:姓名/角色收进 title,只留首字圆徽 + 图标登出。 -->
<template>
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
    <button
      class="logout-btn flex h-7 w-7 cursor-pointer items-center justify-center rounded-md border border-white/20 bg-transparent text-slate-300 transition-colors hover:border-signal hover:text-white"
      title="登出"
      aria-label="登出"
      @click="onLogout"
    >
      <ExitIcon class="h-3 w-3" />
    </button>
  </div>

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

defineProps<{ compact?: boolean }>()

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
