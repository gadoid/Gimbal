<!-- WorkbenchView.vue — /home 用户工作台(Phase 1 占位版)。
     正式形态(§7 registry 卡片宿主 + 常量池摘要卡)由 Phase 2 "并行
     /home" 批次落地;本页先承接两件事:登录后默认落地页(F-sitemap:
     原 / → /scenarios 改为 / → /home),以及常量池从顶导航降级后的
     保底入口(空态 = 引导 CTA,不是虚线占位)。 -->
<template>
  <div class="wb">
    <header class="wb-header">
      <h1 class="wb-title">工作台</h1>
      <p class="wb-sub">常用入口与摘要卡将在这里汇集。</p>
    </header>

    <div class="wb-grid">
      <router-link to="/constants" class="wb-card">
        <span class="wb-card-title">常量池</span>
        <span class="wb-card-desc">业务常量与生成器;编排里可直接插入引用。</span>
        <span class="wb-card-cta">进入常量池 →</span>
      </router-link>

      <router-link to="/scenarios" class="wb-card">
        <span class="wb-card-title">场景库</span>
        <span class="wb-card-desc">我的 / 公共 / 收藏三视图。</span>
        <span class="wb-card-cta">进入场景库 →</span>
      </router-link>

      <router-link to="/executions" class="wb-card">
        <span class="wb-card-title">执行历史</span>
        <span class="wb-card-desc">运行记录与结果下钻。</span>
        <span class="wb-card-cta">进入执行历史 →</span>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.wb {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 16px;
}

.wb-header {
  margin-bottom: 20px;
}

.wb-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #10151c;
}

.wb-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.wb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.wb-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  background: #ffffff;
  border: 1px solid #e1e5eb;
  border-radius: 10px;
  text-decoration: none;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.06);
  transition: box-shadow 0.15s ease, border-color 0.15s ease;
}

.wb-card:hover {
  border-color: #2f6fed;
  box-shadow: 0 8px 24px rgba(16, 21, 28, 0.12);
}

.wb-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #10151c;
}

.wb-card-desc {
  font-size: 12px;
  color: #6b7280;
}

.wb-card-cta {
  margin-top: 4px;
  font-size: 12px;
  font-weight: 500;
  color: #2f6fed;
}
</style>
