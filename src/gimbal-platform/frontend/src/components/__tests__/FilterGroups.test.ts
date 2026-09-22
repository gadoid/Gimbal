/**
 * FilterGroups.vue — 场景库筛选分组条的形态契约。
 *
 * 一个分组 chip 里并排两个热区(点名字还原 / 点 × 删除),写反或互相
 * 冒泡是这里最容易犯的错;其余是"什么时候该给用户入口"的四条判定:
 * 空条件不许存、空白名不许交、读失败给重试而不是假装没有分组、
 * 高亮态挂 .on(基座 chip 族的选中态,不是自造的第二套样式)。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FilterGroups from '@/components/scenario-lib/FilterGroups.vue'
import type { FilterGroup } from '@/api/scenario-filter-groups'

const G: FilterGroup = {
  id: 'g-1', name: '大促回归', q: '订单',
  filters: {
    modules: ['支付'], tags: [], authors: [], priorities: [],
    systems: ['fin'], updatedWithin: '7d',
  },
  createdAt: '2026-09-22T10:00:00+00:00',
}

function mountBox(over: Record<string, unknown> = {}) {
  return mount(FilterGroups, {
    props: {
      groups: [G], state: 'ready', activeId: '', canSave: true, ...over,
    },
  })
}

describe('FilterGroups — 分组条', () => {
  it('点名字只还原,点 × 只删除(两个热区不互串)', async () => {
    const w = mountBox()
    await w.find('[data-testid="group-apply-g-1"]').trigger('click')
    expect(w.emitted('apply')?.[0]).toEqual([G])
    expect(w.emitted('remove')).toBeFalsy()

    await w.find('[data-testid="group-del-g-1"]').trigger('click')
    expect(w.emitted('remove')?.[0]).toEqual(['g-1'])
    expect(w.emitted('apply')).toHaveLength(1)
  })

  it('当前条件与分组一致才亮 .on;一致与否由 composable 判漂移', () => {
    expect(mountBox().find('[data-testid="group-g-1"]').classes()).not.toContain('on')
    expect(
      mountBox({ activeId: 'g-1' }).find('[data-testid="group-g-1"]').classes(),
    ).toContain('on')
  })

  it('没有搜索也没有筛选时不许存分组,也不给引导文案占位', async () => {
    const w = mountBox({ canSave: false, groups: [] })
    const save = w.find('[data-testid="group-save"]')
    expect(save.attributes('disabled')).toBeDefined()
    await save.trigger('click')
    expect(w.find('[data-testid="group-name"]').exists()).toBe(false)
    // 空列表 + ready = 一句人话说明这行是干什么的
    expect(w.text()).toContain('存下常用条件')
  })

  it('分组名留白不提交;回车才落 save', async () => {
    const w = mountBox()
    await w.find('[data-testid="group-save"]').trigger('click')
    const input = w.find('[data-testid="group-name"]')
    expect(input.exists()).toBe(true)

    await input.setValue('   ')
    await input.trigger('keyup.enter')
    expect(w.emitted('save')).toBeFalsy()

    await input.setValue('  大促回归  ')
    await input.trigger('keyup.enter')
    expect(w.emitted('save')?.[0]).toEqual(['大促回归'])
    // 提交即收起:结果由 toast 说话,这里不挂等待态
    expect(w.find('[data-testid="group-name"]').exists()).toBe(false)
  })

  it('读失败 → 说明 + 重试入口,不与「一个分组都没有」混成一句', async () => {
    const w = mountBox({ groups: [], state: 'error' })
    expect(w.text()).toContain('分组没读到')
    expect(w.text()).not.toContain('存下常用条件')
    await w.find('[data-testid="group-retry"]').trigger('click')
    expect(w.emitted('retry')).toHaveLength(1)
  })
})
