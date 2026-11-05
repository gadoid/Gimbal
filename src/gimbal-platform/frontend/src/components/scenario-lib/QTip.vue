<!-- QTip.vue — 问号说明图标:点击弹出说明(2026-11-05 说明统一轮第四批)。
     页面/区块的说明文字收进这颗图标;状态/计数仍走常驻通道
     (PageHead count/meta、.slib-sub)。交互从 title 悬浮改点击弹
     popover:触屏可见、样式可控、可承载长文案;触发器保留 .slib-q
     形态,data-tip 挂说明文本供测试断言(弹层走 portal,断言不便)。
     图标 = radix QuestionMarkCircled(经 SlibIcon 'help')。
     第五批(逐页收纳):弹层宽度自适应内容、上限 420px——短说明
     气泡贴合,页脚长说明/图例并入后不再挤成窄条;text 里 \n\n 分段,
     whitespace-pre-line 落成多段。 -->
<template>
  <Popover>
    <PopoverTrigger as-child>
      <button type="button" class="slib-q" :data-tip="text" aria-label="查看说明">
        <SlibIcon name="help" :size="16" />
      </button>
    </PopoverTrigger>
    <PopoverContent side="bottom" align="start" :side-offset="4"
      class="w-fit max-w-[420px] whitespace-pre-line p-3 text-[12px] leading-5">
      {{ text }}
    </PopoverContent>
  </Popover>
</template>

<script setup lang="ts">
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

defineProps<{
  /** 点击弹出的说明文字 */
  text: string
}>()
</script>
