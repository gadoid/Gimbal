<!-- UserBadge.vue — chrome 上的用户身份 + 登出(侧栏底部 / 收拢顶条右端
     共用)。深色 chrome 专用;Signal token 经 @apply 消费,不零散写 hex。
     compact = 侧栏折叠态:姓名/角色收进 title,只留首字圆徽 + 图标登出。 -->
<template>
  <div v-if="compact" class="flex flex-col items-center gap-2">
    <span
      v-if="auth.currentUser"
      class="username flex h-7 w-7 items-center justify-center rounded-full bg-white/10 text-caption font-semibold text-slate-50"
      :title="badgeTitle"
    >
      {{ initial }}
    </span>
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
    <span v-if="auth.currentUser" class="flex items-center gap-1">
      <span class="username max-w-24 truncate text-body font-medium text-slate-50">
        {{ auth.currentUser.display_name || auth.currentUser.username }}
      </span>
      <span class="text-caption text-slate-500">{{ auth.currentUser.is_admin ? 'admin' : 'member' }}</span>
    </span>
    <button class="logout-btn h-[26px] cursor-pointer rounded-chip border border-white/20 bg-transparent px-2.5 text-caption text-slate-300 transition-colors hover:border-signal hover:text-white" @click="onLogout">
      登出
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ExitIcon } from '@radix-icons/vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

defineProps<{ compact?: boolean }>()

const auth = useAuthStore()
const router = useRouter()

const initial = computed(() =>
  (auth.currentUser?.display_name || auth.currentUser?.username || '?').slice(0, 1),
)

const badgeTitle = computed(() => {
  const name = auth.currentUser?.display_name || auth.currentUser?.username || ''
  return `${name}(${auth.currentUser?.is_admin ? 'admin' : 'member'})`
})

async function onLogout() {
  await auth.logout()
  router.push('/login')
}
</script>
