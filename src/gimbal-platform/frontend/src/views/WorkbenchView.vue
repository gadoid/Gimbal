<!-- WorkbenchView.vue — /home 用户工作台(§7 registry 卡片宿主,正式版)。
     工作台只做两件事:按 registry 渲染 + 布局配置(localStorage 起步 —
     当前只有默认顺序,配置面显式延后)。adminOnly 卡复用侧栏同一权限
     判定源(auth.isAdmin)。快捷入口区保留 Phase 1 占位版的三个 CTA
     (registry 卡片之外的全局导航面)。 -->
<template>
  <div class="mx-auto max-w-[960px] px-4 py-6">
    <header class="mb-5">
      <h1 class="m-0 text-display font-semibold text-signal-ink">工作台</h1>
      <p class="mb-0 mt-1 text-body text-muted-foreground">常用入口与摘要卡将在这里汇集。</p>
    </header>

    <!-- registry 卡片区(§7:集中注册、懒加载、三态、故障隔离) -->
    <div v-if="visibleCards.length" class="grid grid-cols-1 gap-3 md:grid-cols-2">
      <WorkbenchCardSlot
        v-for="def in visibleCards"
        :key="def.id"
        :def="def"
      />
    </div>

    <!-- 全局快捷入口(非 registry 卡;常量池深链由卡内"管理"承担) -->
    <h2 class="mb-2 mt-6 text-heading text-signal-ink">快捷入口</h2>
    <div class="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-3">
      <router-link to="/scenarios" class="wb-card">
        <span class="text-heading text-signal-ink">场景库</span>
        <span class="text-caption text-muted-foreground">我的 / 公共 / 收藏三视图。</span>
        <span class="mt-1 text-caption font-medium text-signal">进入场景库 →</span>
      </router-link>
      <router-link to="/executions" class="wb-card">
        <span class="text-heading text-signal-ink">执行历史</span>
        <span class="text-caption text-muted-foreground">运行记录与结果下钻。</span>
        <span class="mt-1 text-caption font-medium text-signal">进入执行历史 →</span>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { workbenchRegistry } from '@/components/workbench/registry'
import WorkbenchCardSlot from '@/components/workbench/WorkbenchCardSlot.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

/** adminOnly 过滤复用侧栏同一权限判定源(§7 第 2 条:不另写一套) */
const visibleCards = computed(() =>
  workbenchRegistry.filter((d) => !d.adminOnly || auth.isAdmin),
)
</script>

<style scoped>
/* 快捷入口卡:Phase 1 占位版样式延续 */
.wb-card {
  @apply flex flex-col gap-1.5 rounded-card border border-signal-line bg-signal-card p-4 no-underline shadow-sig-hover transition-shadow duration-150 hover:border-signal hover:shadow-sig-float;
}
</style>
