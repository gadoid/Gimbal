<!-- SlibIcon.vue — 页头 / 卡头图标的唯一实现(全站)。
     形状不许各画一遍:每张工作台卡左侧那颗图标必须就是它指向的功能页
     上那颗,否则图标只是一团装饰,认不出对应关系。
       · 有页头的页面 —— 描线形状原先只写在 PageHead 里,这里抽出来,
         页头与卡头共用同一份(folder/globe/star/grid/layers/lock/
         sliders/activity/key/network);
       · 没有页头图标的三页(执行记录 / 执行器 / 用户管理)—— 全站只有
         侧边栏一颗 @radix-icons 图标,那就直接渲染同一个组件,连描边
         粗细都跟着侧边栏走,不存在"看起来像但其实是两个形状";
       · database / clock 只在卡里出现(常量池无页头也无侧栏条目、时间线
         是卡不是页面),沿用卡片自己那套描线。 -->
<template>
  <component
    :is="RADIX[name]"
    v-if="RADIX[name]"
    :style="{ width: size + 'px', height: size + 'px' }"
    aria-hidden="true"
  />
  <svg
    v-else
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-if="name === 'folder'" d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    <template v-else-if="name === 'globe'">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" />
    </template>
    <template v-else-if="name === 'grid'">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </template>
    <template v-else-if="name === 'layers'">
      <path d="M12 3 3 8l9 5 9-5-9-5z" />
      <path d="M3 13.5 12 18.5l9-5" />
    </template>
    <template v-else-if="name === 'lock'">
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </template>
    <template v-else-if="name === 'sliders'">
      <path d="M4 7h16M4 12h16M4 17h16" />
      <circle cx="9" cy="7" r="2.2" />
      <circle cx="15" cy="12" r="2.2" />
      <circle cx="7" cy="17" r="2.2" />
    </template>
    <path v-else-if="name === 'activity'" d="M3 12h4l3 8 4-16 3 8h4" />
    <template v-else-if="name === 'key'">
      <circle cx="8" cy="16" r="4.5" />
      <path d="m11.2 12.8 8.3-8.3M17 7l2.5 2.5M15.5 8.5 18 11" />
    </template>
    <template v-else-if="name === 'network'">
      <rect x="3" y="15" width="6" height="6" rx="1.5" />
      <rect x="15" y="15" width="6" height="6" rx="1.5" />
      <rect x="9" y="3" width="6" height="6" rx="1.5" />
      <path d="M6 15v-3h12v3M12 12V9" />
    </template>
    <template v-else-if="name === 'database'">
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
      <path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
    </template>
    <template v-else-if="name === 'clock'">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </template>
    <path v-else d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z" />
  </svg>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { CounterClockwiseClockIcon, GearIcon, PlayIcon } from '@radix-icons/vue'

/** 页头图标名(PageHead 的取值域)+ 卡头独有的三种。 */
export type SlibIconName =
  | 'folder' | 'globe' | 'star' | 'grid' | 'layers' | 'lock' | 'sliders'
  | 'activity' | 'key' | 'network' | 'database' | 'clock'
  | 'history' | 'gear' | 'play'

const RADIX: Partial<Record<SlibIconName, Component>> = {
  // 执行记录 / 执行器 / 用户管理三页页面上没有图标,全站唯一的一颗就是侧
  // 边栏这颗 @radix-icons 组件 —— 卡里直接渲染同一个组件,连描边粗细都
  // 跟着侧栏走;自己画一颗"像的"仍然是两个形状。
  history: CounterClockwiseClockIcon,
  play: PlayIcon,
  gear: GearIcon,
}

withDefaults(defineProps<{
  name: SlibIconName
  /** 页头 15,卡头 14 —— 与侧边栏 h-3.5 w-3.5 同一档 */
  size?: number
}>(), { size: 15 })
</script>
