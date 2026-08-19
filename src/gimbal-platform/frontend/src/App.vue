<!-- App.vue — Spec-1 layout shell.
     TopNav renders only when authenticated, so /login + /register
     remain clean (no chrome). Content area is offset by 48px via
     padding-top so it doesn't slide under the fixed topbar. -->
<template>
  <TopNav v-if="auth.isAuthenticated" />
  <main class="app-main" :class="{ 'with-topnav': auth.isAuthenticated }">
    <router-view />
  </main>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import TopNav from '@/components/TopNav.vue'

const auth = useAuthStore()

// 页面刷新后只恢复了 accessToken，currentUser 是 null。
// 依赖 currentUser 的页面(如按 owner 过滤的场景库)需要先确认身份。
// 这里懒拉一次，避免后续 store 拿到 undefined。
onMounted(async () => {
  if (auth.accessToken && !auth.currentUser) {
    try {
      await auth.fetchMe()
    } catch {
      // 401 走 http 拦截器统一跳 /login；忽略即可
    }
  }
})
</script>

<style scoped>
.app-main {
  min-height: 100vh;
}

.app-main.with-topnav {
  padding-top: 48px;
}
</style>