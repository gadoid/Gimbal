<!-- Pagination.vue — 全站唯一分页实现(M1 三件套之一,PG迁移方案 §6.1)。

     由场景库自绘的 ListPager.vue 升格而来:补省略号( siblingCount 可调)、
     键盘可达(按钮原生 focus + Enter/Space)、总数文案开关。

     2026-09-23 分页批次:补齐「每页行数选择 + 跳转输入」两项,均默认关闭
     (showPageSize/showJump),既有调用点(场景库/认证/审计面板)行为不变。
     开启 showPageSize 后即使只有一页也渲染(用户需要随时改每页行数);
     未开启时维持原契约:总数不超过一页整体不渲染。 -->
<template>
  <nav
    v-if="pageCount > 1 || (showPageSize && total > 0)"
    class="inline-flex flex-wrap items-center justify-end gap-1"
    aria-label="分页"
    data-testid="pager"
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

    <span v-if="showPageSize" class="ml-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
      每页
      <select
        class="h-7 rounded-md border border-input bg-background px-1.5 text-xs text-foreground outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
        :value="pageSize"
        :disabled="disabled"
        data-testid="pager-size"
        @change="onSizeChange(Number(($event.target as HTMLSelectElement).value))"
      >
        <option v-if="!pageSizes.includes(pageSize)" :value="pageSize">{{ pageSize }}</option>
        <option v-for="n in pageSizes" :key="n" :value="n">{{ n }}</option>
      </select>
      条
    </span>

    <span v-if="showJump && pageCount > 1" class="ml-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
      <input
        v-model="jumpText"
        type="text"
        inputmode="numeric"
        class="h-7 w-12 rounded-md border border-input bg-background px-1.5 text-xs text-foreground outline-none placeholder:text-muted-foreground focus:ring-1 focus:ring-ring disabled:opacity-50"
        placeholder="页码"
        :disabled="disabled"
        data-testid="pager-jump"
        @keyup.enter="doJump"
      />
      <Button
        variant="outline"
        size="sm"
        class="h-7 px-2 text-xs"
        :disabled="disabled"
        data-testid="pager-jump-btn"
        @click="doJump"
      >跳转</Button>
    </span>

    <span v-if="showTotal" class="ml-2 text-xs text-muted-foreground">
      共 {{ total }} 条
    </span>
  </nav>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
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
  /** 每页行数选择器(开启时单页也渲染,否则改不了行数)。 */
  showPageSize?: boolean
  /** 选择器候选(升序);当前值不在候选里时补一项,避免 select 显示错位。 */
  pageSizes?: number[]
  /** 跳转输入(仅多页时有意义)。 */
  showJump?: boolean
}>(), {
  siblingCount: 1,
  disabled: false,
  showTotal: true,
  showPageSize: false,
  pageSizes: () => [10, 20, 50, 100],
  showJump: false,
})

const emit = defineEmits<{
  'update:page': [p: number]
  'update:pageSize': [n: number]
}>()

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

function onSizeChange(n: number): void {
  if (Number.isFinite(n) && n > 0 && n !== props.pageSize) emit('update:pageSize', n)
}

const jumpText = ref('')

function doJump(): void {
  const raw = Number.parseInt(jumpText.value, 10)
  if (Number.isFinite(raw)) go(raw)
  jumpText.value = ''
}
</script>
