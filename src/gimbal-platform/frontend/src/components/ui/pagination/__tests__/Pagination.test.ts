/**
 * ui/pagination — 全站唯一分页实现(M1 三件套之一)。
 * 钉住:单页整体不渲染、首末页边界禁用、翻页 emit 钳位、当前页
 * aria-current、总数回显、7 页以上出省略号。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { Pagination } from '@/components/ui/pagination'

describe('Pagination — 分页条', () => {
  it('总数不超过一页时整体不渲染', () => {
    expect(mount(Pagination, { page: 1, total: 20, pageSize: 20 }).find('nav').exists()).toBe(false)
    expect(mount(Pagination, { page: 1, total: 0, pageSize: 20 }).find('nav').exists()).toBe(false)
  })

  it('首页禁「上一页」,末页禁「下一页」;页码点击 emit 目标页', async () => {
    const first = mount(Pagination, { props: { page: 1, total: 45, pageSize: 20 } })
    expect((first.find('button[aria-label="上一页"]').element as HTMLButtonElement).disabled).toBe(true)
    const nums = first.findAll('button[aria-label^="第"]')
    expect(nums).toHaveLength(3) // 3 页
    await nums[2]!.trigger('click')
    expect(first.emitted('update:page')?.[0]).toEqual([3])

    const last = mount(Pagination, { props: { page: 3, total: 45, pageSize: 20 } })
    expect((last.find('button[aria-label="下一页"]').element as HTMLButtonElement).disabled).toBe(true)
    await last.find('button[aria-label="上一页"]').trigger('click')
    expect(last.emitted('update:page')?.[0]).toEqual([2])
  })

  it('越界点击被钳位(不给负页/超尾页)', async () => {
    const w = mount(Pagination, { props: { page: 1, total: 45, pageSize: 20 } })
    await w.find('button[aria-label="上一页"]').trigger('click')
    expect(w.emitted('update:page')).toBeUndefined() // 已在第 1 页,钳位后无事件
  })

  it('当前页高亮并带 aria-current;总数回显', () => {
    const w = mount(Pagination, { props: { page: 2, total: 41, pageSize: 20 } })
    const active = w.findAll('button[aria-current="page"]')
    expect(active).toHaveLength(1)
    expect(active[0]!.text()).toBe('2')
    expect(w.text()).toContain('共 41 条')
  })

  it('页数多时出省略号(7+sibling×2 以上)', () => {
    const w = mount(Pagination, { props: { page: 5, total: 400, pageSize: 20 } })
    expect(w.text()).toContain('…')
    const nums = w.findAll('button[aria-label^="第"]').map((b) => b.text())
    expect(nums).toEqual(['1', '4', '5', '6', '20'])
  })
})
