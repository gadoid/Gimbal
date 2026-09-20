<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { cn } from "@/lib/utils"

const props = defineProps<{
  class?: HTMLAttributes["class"]
}>()
</script>

<!-- TableHead.vue — 表头单元格的默认形制 = 全站表头规范(scenario-lib.css
     的 .sig-th:冷蓝白带 + 深海军蓝字 + 细墨线)。此前这里是 shadcn 默认的
     `text-muted-foreground` 灰字 + 各页再叠一层 bg-signal-canvas 灰带,
     同一件事三处各写一遍,所以每页长得都不太一样。 -->
<template>
  <th :class="cn('sig-th align-middle [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-0.5', props.class)">
    <slot />
  </th>
</template>
