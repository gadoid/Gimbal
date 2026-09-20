<!-- PageHead.vue — 全站列表页统一页头:.icon-badge(26×26 浅蓝底)+
     标题 + 副标;右侧 slot 放计数 / 动作。
     形状不在这里画:图标抽进 SlibIcon,页头与工作台卡头共用同一份。
     原先只服务场景库三页(folder/globe/star),服务区域五页接同一套语言
     后一并收在这里;卡头也要同样的形状时,抽出去,不各画一遍。 -->
<template>
  <header class="slib-head">
    <span class="icon-badge" aria-hidden="true">
      <SlibIcon :name="icon" />
    </span>
    <div class="slib-head-text">
      <div class="slib-title-row">
        <h2 class="slib-title">{{ title }}</h2>
        <span v-if="count" class="slib-count">{{ count }}</span>
      </div>
      <p v-if="subtitle" class="slib-sub">{{ subtitle }}</p>
      <p v-if="hint" class="slib-hint">{{ hint }}</p>
    </div>
    <div class="slib-head-right">
      <slot name="right" />
    </div>
  </header>
</template>

<script setup lang="ts">
import SlibIcon, { type SlibIconName } from '@/components/scenario-lib/SlibIcon.vue'

defineProps<{
  icon: SlibIconName
  title: string
  subtitle?: string
  /** 标题下第二行:面包屑 / 深链上下文(比 subtitle 弱一档,只在详情页用) */
  hint?: string
  count?: string
}>()
</script>
