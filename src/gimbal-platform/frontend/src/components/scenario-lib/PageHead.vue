<!-- PageHead.vue — 场景库三页统一页头:.icon-badge(26×26 浅蓝底)+
     标题 + 副标;右侧 slot 放计数 / 动作。图标形状按页切换
     (我的场景=文件夹 / 公共场景=地球 / 关注=星形),配色恒定。 -->
<template>
  <header class="slib-head">
    <span class="icon-badge" aria-hidden="true">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path v-if="icon === 'folder'" d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        <template v-else-if="icon === 'globe'">
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" />
        </template>
        <path v-else d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z" />
      </svg>
    </span>
    <div class="slib-head-text">
      <div class="slib-title-row">
        <h2 class="slib-title">{{ title }}</h2>
        <span v-if="count" class="slib-count">{{ count }}</span>
      </div>
      <p v-if="subtitle" class="slib-sub">{{ subtitle }}</p>
    </div>
    <div class="slib-head-right">
      <slot name="right" />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  icon: 'folder' | 'globe' | 'star'
  title: string
  subtitle?: string
  count?: string
}>()
</script>
