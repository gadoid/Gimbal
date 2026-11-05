<!-- QTip.vue — 问号悬浮提示(2026-11-05 说明统一轮)。
     页面/区块的说明文字收进这颗图标:title 原生悬浮展示,不常驻;
     状态/计数仍走常驻通道(PageHead count/meta、.slib-sub)。
     图标 = radix QuestionMarkCircled(经 SlibIcon 'help'),描边风格
     与侧栏/页头一致 —— 此前用文字问号拼 CSS 圆圈,两轮评审都被评
     "丑",不再自己画形状。 -->
<template>
  <span class="slib-q" :title="text">
    <SlibIcon name="help" :size="16" />
  </span>
</template>

<script setup lang="ts">
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'

defineProps<{
  /** 悬浮展示的说明文字 */
  text: string
}>()
</script>
