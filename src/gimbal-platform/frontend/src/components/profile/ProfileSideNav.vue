<!-- ProfileSideNav.vue — 个人设置分区导航(原型 Main/Tokens/
     CardSettings 左侧子导航)。按路由高亮当前子页;「访问令牌」挂
     待处理数(7 天内到期 + 已失效,与用户区同口径;user 角色无令牌
     不拉取不出角标)。通知与账号同页(原型 Main.html 兼载)。 -->
<template>
  <nav class="flex w-[168px] flex-none flex-col gap-0.5" aria-label="个人设置分区">
    <RouterLink
      v-for="item in items" :key="item.to" :to="item.to"
      class="flex items-center justify-between rounded-md px-3 py-2 text-body no-underline"
      :class="isActive(item) ? 'bg-[#E7EFFF] font-semibold text-[#1F55C4]' : 'text-signal-ink hover:bg-signal-soft'"
    >
      {{ item.label }}
      <span v-if="item.badge" class="pending-badge">{{ item.badge }}</span>
    </RouterLink>
  </nav>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { listAccessTokens } from '@/api/access-tokens'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()

const pendingCount = ref(0)

const items = computed(() => [
  { label: '账号', to: '/profile/account', active: route.path === '/profile/account' },
  { label: '访问令牌', to: '/profile/tokens',
    active: route.path === '/profile/tokens',
    badge: pendingCount.value ? `${pendingCount.value} 待处理` : '' },
  { label: '工作台身份卡', to: '/profile/card',
    active: route.path === '/profile/card' },
  // 原型 Main.html 同页兼载账号与通知;通知项不做独立高亮
  { label: '通知', to: '/profile/account', active: false },
])

function isActive(item: { active: boolean }): boolean {
  return item.active
}

onMounted(async () => {
  if (!['member', 'admin'].includes(auth.role)) return
  try {
    const env = await listAccessTokens('personal')
    pendingCount.value = env.items.filter((t) =>
      t.status === 'invalidated' || (t.status === 'active' && t.expiresAt
        && new Date(t.expiresAt).getTime() - Date.now() < 7 * 86400e3)).length
  } catch { /* 不可达时不出角标 */ }
})
</script>

<style scoped>
.pending-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 0 6px;
  border-radius: 999px;
  background: #fef3c7;
  color: #b45309;
}
</style>
