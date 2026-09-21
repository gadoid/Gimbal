<!-- Pagination.vue — 全站唯一分页实现(M1 三件套之一,PG迁移方案 §6.1)。

     由场景库自绘的 ListPager.vue 升格而来:补省略号( siblingCount 可调)、
     键盘可达(按钮原生 focus + Enter/Space)、总数文案开关。总数不超过
     一页时整体不渲染(与 ListPager 行为一致,列表页空态不必挂分页条)。 -->
<template>
  <nav
    v-if="pageCount > 1"
    class="inline-flex items-center justify-end gap-1"
    aria-label="分页"
  >
    <Button
      variant="outline"
      size="icon-sm"
      :disabled="page <= 1 || disabled"
      aria-label="上一页"
      @click="go(page - 1)"
    >&#8249;</Button>

    <template v-for="(p, i) in slots" :key="`${p}-${i}`">
      <span v-if="p === '…'" class="px-1 text-xs text-muted-foreground">…</span>
      <Button
        v-else
        :variant="p === page ? 'default' : 'outline'"
        size="icon-sm"
        :disabled="disabled"
        :aria-current="p === page ? 'page' : undefined"
        :aria-label="`第 ${p} 页`"
        @click="go(p as number)"
      >{{ p }}</Button>
    </template>

    <Button
      variant="outline"
      size="icon-sm"
      :disabled="page >= pageCount || disabled"
      aria-label="下一页"
      @click="go(page + 1)"
    >&#8250;</Button>

    <span v-if="showTotal" class="ml-2 text-xs text-muted-foreground">
      共 {{ total }} 条
    </span>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Button } from '@/components/ui/button'

const props = withDefaults(defineProps<{
  /** 当前页(1 起)。 */
  page: number
  /** 总条数(不是总页数)。 */
  total: number
  pageSize: number
  /** 当前页两侧各显示几个页码(默认 1 → 1 … 4 5 6 … 20)。 */
  siblingCount?: number
  /** 加载中禁用全部按钮(防重复点击)。 */
  disabled?: boolean
  showTotal?: boolean
}>(), {
  siblingCount: 1,
  disabled: false,
  showTotal: true,
})

const emit = defineEmits<{ 'update:page': [p: number] }>()

/** 至少 1 页 —— 全为空时上游走空态分支,这里不该渲染出 0 个页码钮。 */
const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

/** 页码槽位:数字或 '…'(省略号)。 */
const slots = computed<(number | '…')[]>(() => {
  const last = pageCount.value
  if (last <= 7 + props.siblingCount * 2) {
    return Array.from({ length: last }, (_, i) => i + 1)
  }
  const current = Math.min(Math.max(props.page, 1), last)
  const left = Math.max(current - props.siblingCount, 1)
  const right = Math.min(current + props.siblingCount, last)

  const mid: (number | '…')[] = []
  if (left > 1) mid.push(1)
  if (left > 2) mid.push('…')
  for (let p = left; p <= right; p++) mid.push(p)
  if (right < last - 1) mid.push('…')
  if (right < last) mid.push(last)
  return mid
})

function go(p: number): void {
  const clamped = Math.min(Math.max(p, 1), pageCount.value)
  if (clamped !== props.page) emit('update:page', clamped)
}
</script>
