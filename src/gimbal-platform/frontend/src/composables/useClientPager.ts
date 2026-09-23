/**
 * useClientPager.ts — 客户端列表分页(2026-09-23 分页批次)。
 *
 * 服务端分页走 useServerList(Page 信封);这里给「一次性全量拉回、
 * 前端过滤/前端持有」的页面(ServiceAdmin 别名表 / 常量池 / 传递
 * 默认值 / 批次明细 ops)补同一套分页语义:
 *  - 行源收缩(过滤收紧/删除)→ 越界自动回落末页;
 *  - 改每页行数 → 回页 1;
 *  - Pagination 组件 v-model:page / v-model:page-size 直接对接返回值。
 */
import { computed, ref, watch } from 'vue'
import { usePagerSize } from './usePagerSize'

export function useClientPager<T>(rows: () => T[], initialSize = 20, pagerKey?: string) {
  const page = ref(1)
  const pageSize = pagerKey
    ? usePagerSize(pagerKey, initialSize).pageSize
    : ref(initialSize)
  const total = computed(() => rows().length)
  const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
  const paged = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return rows().slice(start, start + pageSize.value)
  })
  watch(total, () => {
    if (page.value > pageCount.value) page.value = pageCount.value
  })
  watch(pageSize, () => {
    page.value = 1
  })
  return { page, pageSize, paged, total, pageCount }
}
