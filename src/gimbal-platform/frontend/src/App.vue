<!-- App.vue — 布局壳(重构方案 Phase 1:导航范式更换)。
     三态 chrome:
     - 未认证:无 chrome,裸 router-view(登录/注册);
     - meta.chromeMode === 'collapsed'(编排器/方案工作台/断言注册表/
       常量池等编辑流页):收起侧边栏,48px 收拢顶条承载统一面包屑;
     - 默认 'full':四域侧边栏 + 内容区两栏。
     ToastHost / ConfirmHost 是全站单点,任何 chrome 态都在场。 -->
<template>
  <ToastHost />
  <ConfirmHost />

  <template v-if="!auth.isAuthenticated">
    <router-view />
  </template>

  <template v-else-if="chromeMode === 'collapsed'">
    <CollapsedTopbar />
    <main class="min-h-screen pt-12">
      <router-view />
    </main>
  </template>

  <template v-else>
    <Sidebar />
    <main class="ml-[200px] min-h-screen min-w-0">
      <router-view />
    </main>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Sidebar from '@/components/chrome/Sidebar.vue'
import CollapsedTopbar from '@/components/chrome/CollapsedTopbar.vue'
import ToastHost from '@/components/chrome/ToastHost.vue'
import ConfirmHost from '@/components/chrome/ConfirmHost.vue'

const auth = useAuthStore()
const route = useRoute()

const chromeMode = computed(() => (route.meta.chromeMode as 'full' | 'collapsed' | undefined) ?? 'full')

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

