<!-- ProfileSideNav.vue — 个人设置分区导航(原型 Main/Tokens/
     CardSettings 左侧子导航)。按路由高亮当前子页;「访问令牌」挂
     待处理数(7 天内到期 + 已失效,与用户区同口径;user 角色无令牌
     不拉取不出角标)。通知与账号同页(原型 Main.html 兼载):「通知」
     链到 /profile/account#notify,由 ProfileAccount 滚到通知区;两项按
     hash 区分高亮(此前通知链到无锚点的账号页,点了停在账号卡顶部、
     高亮的也是「账号」)。 -->
<template>
  <nav class="flex w-[168px] flex-none flex-col gap-0.5" aria-label="个人设置分区">
    <RouterLink
      v-for="item in items" :key="item.to" :to="item.to"
      class="flex items-center justify-between rounded-md px-3 py-2 text-body no-underline"
      :class="isActive(item) ? 'bg-[#E7EFFF] font-semibold text-[#1F55C4]' : 'text-signal-ink hover:bg-signal-soft'"
      :aria-current="isActive(item) ? 'page' : undefined"
      :data-testid="`profile-nav-${item.id}`"
      @click="onReclick(item)"
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

const route = useRoute()
const pendingCount = ref(0)

const onAccount = computed(() => route.path === '/profile/account')
const onNotify = computed(() => onAccount.value && route.hash === '#notify')

const items = computed(() => [
  { id: 'account', label: '账号', to: '/profile/account',
    active: onAccount.value && !onNotify.value },
  { id: 'tokens', label: '访问令牌', to: '/profile/tokens',
    active: route.path === '/profile/tokens',
    badge: pendingCount.value ? `${pendingCount.value} 待处理` : '' },
  { id: 'card', label: '工作台身份卡', to: '/profile/card',
    active: route.path === '/profile/card' },
  // S7.3:我的配置(默认环境偏好 + 个人层 carry 默认)
  { id: 'config', label: '我的配置', to: '/profile/config',
    active: route.path === '/profile/config' },
  { id: 'notify', label: '通知', to: '/profile/account#notify', active: onNotify.value },
])

function isActive(item: { active: boolean }): boolean {
  return item.active
}

/** 再点当前项:路由不变、hash watch 不触发 —— 用户手动滚走后点「通知」
 * 不回通知区。同页两项在这里补滚动(通知 → 通知区,账号 → 顶部);
 * 非当前项照常交给 RouterLink 导航(onClick 与其 navigate 合并执行)。 */
function onReclick(item: { id: string; active: boolean }) {
  if (!item.active) return
  if (item.id === 'notify') {
    document.getElementById('notify')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  } else if (item.id === 'account') {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

onMounted(async () => {
  // authz W5:个人令牌开放至全体用户 —— 角色门删除,人人可有待处理角标
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
