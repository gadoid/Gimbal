<!-- PageHead.vue — 全站列表页统一页头:.icon-badge(26×26 浅蓝底)+
     标题 + 问号悬浮说明;右侧 slot 放计数 / 动作。
     形状不在这里画:图标抽进 SlibIcon,页头与工作台卡头共用同一份。
     原先只服务场景库三页(folder/globe/star),服务区域五页接同一套语言
     后一并收在这里;卡头也要同样的形状时,抽出去,不各画一遍。
     2026-11-05 说明统一轮:页面说明文字(subtitle)不再常驻成副标行,
     收进标题旁圆圈问号的悬浮提示(.slib-q,首例 TokensSection 区块头);
     随数据变化的状态/计数走 meta(常驻)与 count。 -->
<template>
  <header class="slib-head">
    <span class="icon-badge" aria-hidden="true">
      <SlibIcon :name="icon" />
    </span>
    <div class="slib-head-text">
      <div class="slib-title-row">
        <h2 class="slib-title">{{ title }}</h2>
        <QTip v-if="subtitle" :text="subtitle" />
        <span v-if="count" class="slib-count">{{ count }}</span>
      </div>
      <p v-if="meta" class="slib-sub">{{ meta }}</p>
      <p v-if="hint" class="slib-hint">{{ hint }}</p>
    </div>
    <div class="slib-head-right">
      <slot name="right" />
    </div>
  </header>
</template>

<script setup lang="ts">
import SlibIcon, { type SlibIconName } from '@/components/scenario-lib/SlibIcon.vue'
import QTip from '@/components/scenario-lib/QTip.vue'

defineProps<{
  icon: SlibIconName
  title: string
  /** 页面说明文字:圆圈问号悬浮展示,不常驻 */
  subtitle?: string
  /** 常驻状态行(统计 / 视角等随数据变化的信息),原副标位置 */
  meta?: string
  /** 标题下第二行:面包屑 / 深链上下文(比 meta 弱一档,只在详情页用) */
  hint?: string
  count?: string
}>()
</script>
