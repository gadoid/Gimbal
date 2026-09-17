<!-- WorkbenchView.vue — /home 用户工作台(Phase 1 占位版)。
     正式形态(§7 registry 卡片宿主 + 常量池摘要卡)由 Phase 2 "并行
     /home" 批次落地;本页先承接两件事:登录后默认落地页(F-sitemap:
     原 / → /scenarios 改为 / → /home),以及常量池从顶导航降级后的
     保底入口(空态 = 引导 CTA,不是虚线占位)。 -->
<template>
  <div class="mx-auto max-w-[960px] px-4 py-6">
    <header class="mb-5">
      <h1 class="m-0 text-display font-semibold text-signal-ink">工作台</h1>
      <p class="mb-0 mt-1 text-body text-muted-foreground">常用入口与摘要卡将在这里汇集。</p>
    </header>

    <div class="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-3">
      <router-link to="/constants" class="wb-card">
        <span class="text-heading text-signal-ink">常量池</span>
        <span class="text-caption text-muted-foreground">业务常量与生成器;编排里可直接插入引用。</span>
        <span class="mt-1 text-caption font-medium text-signal">进入常量池 →</span>
      </router-link>

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

<style scoped>
/* 卡片视觉 token:card/line/ink/accent + 双阴影语义(E-scale/D-palette) */
.wb-card {
  @apply flex flex-col gap-1.5 rounded-card border border-signal-line bg-signal-card p-4 no-underline shadow-sig-hover transition-shadow duration-150 hover:border-signal hover:shadow-sig-float;
}
</style>
