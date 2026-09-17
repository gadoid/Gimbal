<!-- UserBadge.vue — chrome 上的用户身份 + 登出(侧栏底部 / 收拢顶条右端
     共用)。深色 chrome 专用;Signal token 经 @apply 消费,不零散写 hex。 -->
<template>
  <div class="flex shrink-0 items-center gap-3">
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
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function onLogout() {
  await auth.logout()
  router.push('/login')
}
</script>
