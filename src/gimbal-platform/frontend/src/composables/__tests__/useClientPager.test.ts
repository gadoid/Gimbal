/**
 * useClientPager — 客户端列表分页(2026-09-23 分页批次)。
 * 钉住:切片正确、行源收缩越界回落末页、改每页行数回页 1。
 */
import { describe, it, expect } from 'vitest'
import { nextTick, ref } from 'vue'
import { useClientPager } from '@/composables/useClientPager'

describe('useClientPager', () => {
  it('切片:page/pageSize 圈定当前页', () => {
    const rows = ref(Array.from({ length: 45 }, (_, i) => i))
    const p = useClientPager(() => rows.value, 20)
    expect(p.paged.value).toHaveLength(20)
    expect(p.paged.value[0]).toBe(0)
    p.page.value = 3
    expect(p.paged.value).toEqual([40, 41, 42, 43, 44])
    expect(p.total.value).toBe(45)
    expect(p.pageCount.value).toBe(3)
  })

  it('行源收缩(过滤收紧/删除)→ 越界自动回落末页', async () => {
    const rows = ref(Array.from({ length: 45 }, (_, i) => i))
    const p = useClientPager(() => rows.value, 20)
    p.page.value = 3
    rows.value = rows.value.slice(0, 10) // 收缩到 10 条(1 页)
    await nextTick()
    expect(p.page.value).toBe(1)
  })

  it('改每页行数 → 回页 1', async () => {
    const rows = ref(Array.from({ length: 45 }, (_, i) => i))
    const p = useClientPager(() => rows.value, 20)
    p.page.value = 2
    await nextTick()
    p.pageSize.value = 50
    await nextTick()
    expect(p.page.value).toBe(1)
    expect(p.paged.value).toHaveLength(45)
  })

  it('空列表:单页且切片为空,不越界', () => {
    const rows = ref<number[]>([])
    const p = useClientPager(() => rows.value, 20)
    expect(p.page.value).toBe(1)
    expect(p.pageCount.value).toBe(1)
    expect(p.paged.value).toEqual([])
  })
})
