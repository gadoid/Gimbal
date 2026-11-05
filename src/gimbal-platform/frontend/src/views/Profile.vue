<!-- Profile.vue — 个人设置 · 布局壳(webhook v4 §8;原型 Main /
     Tokens / CardSettings)。原型是每个分区一个子页面(左侧分区
     导航切换),不再是同页锚点滚动;头 = h1 + `用户名 · 角色`,
     内容区由子路由渲染(account / tokens / card)。 -->
<template>
  <section class="slib">
    <header class="flex flex-col gap-0.5">
      <h1 class="m-0 text-[22px] leading-[30px] font-semibold">个人设置</h1>
      <span class="text-caption text-signal-ink/60">
        {{ auth.currentUser?.username }} · {{ roleLabel }}
      </span>
    </header>

    <div class="flex flex-wrap items-start gap-6">
      <ProfileSideNav class="sticky top-4" />
      <div class="flex min-w-0 max-w-[880px] flex-1 flex-col gap-4">
        <RouterView />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ProfileSideNav from '@/components/profile/ProfileSideNav.vue'

const auth = useAuthStore()

const ROLE_LABELS: Record<string, string> = { user: '用户', member: '成员', admin: '管理员' }
const roleLabel = computed(() => ROLE_LABELS[auth.role] ?? auth.role)
</script>
