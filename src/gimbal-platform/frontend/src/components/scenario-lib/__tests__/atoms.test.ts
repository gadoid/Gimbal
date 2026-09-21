/**
 * 场景库共用小组件:SignalDots / StarToggle / PageHead。
 * (ListPager 已升格为 ui/pagination 全站唯一分页实现,测试随迁。)
 * 三页都靠它们,行为必须钉死(尤其分页的「不满一页不渲染」和首末页禁用)。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import SignalDots from '@/components/scenario-lib/SignalDots.vue'
import StarToggle from '@/components/scenario-lib/StarToggle.vue'
import PageHead from '@/components/scenario-lib/PageHead.vue'

describe('SignalDots — 近 5 次趋势', () => {
  it('无执行记录整体不渲染(而不是画一排灰点)', () => {
    expect(mount(SignalDots, { props: { runs: [] } }).find('.signal-dots').exists()).toBe(false)
  })

  it('状态 → 色调映射,未知状态归入 run;标题报数量', () => {
    const w = mount(SignalDots, { props: { runs: ['done', 'failed', 'queued', 'weird'] } })
    expect(w.findAll('.signal-dots i').map((d) => d.classes().join(' ')))
      .toEqual(['ok', 'bad', 'run', 'run'])
    expect(w.find('.signal-dots').attributes('title')).toBe('近 4 次执行')
  })
})

describe('StarToggle — 关注开关', () => {
  it('已关注 = 实心 + 「取消关注」;未关注 = 描边 + 「关注」', () => {
    const on = mount(StarToggle, { props: { starred: true } })
    expect(on.find('button').attributes('aria-label')).toBe('取消关注')
    expect(on.find('svg').attributes('fill')).toBe('#EAB308')
    const off = mount(StarToggle, { props: { starred: false } })
    expect(off.find('button').attributes('aria-label')).toBe('关注')
    expect(off.find('svg').attributes('fill')).toBe('none')
  })

  it('点击抛 toggle,不自己改状态', async () => {
    const w = mount(StarToggle, { props: { starred: false } })
    await w.find('button').trigger('click')
    expect(w.emitted('toggle')).toHaveLength(1)
  })
})

describe('PageHead — 三页统一页头', () => {
  it('标题 / 计数 / 副标按需渲染', () => {
    const w = mount(PageHead, { props: { icon: 'folder', title: '我的场景', count: '共 8 个', subtitle: 'sub' } })
    expect(w.find('.slib-title').text()).toBe('我的场景')
    expect(w.find('.slib-count').text()).toBe('共 8 个')
    expect(w.find('.slib-sub').text()).toBe('sub')
    const bare = mount(PageHead, { props: { icon: 'star', title: '关注' } })
    expect(bare.find('.slib-count').exists()).toBe(false)
    expect(bare.find('.slib-sub').exists()).toBe(false)
  })

  it('三种图标各自成形状:地球有圆、星形单路径', () => {
    expect(mount(PageHead, { props: { icon: 'globe', title: 't' } }).find('circle').exists()).toBe(true)
    expect(mount(PageHead, { props: { icon: 'folder', title: 't' } }).find('circle').exists()).toBe(false)
    expect(mount(PageHead, { props: { icon: 'star', title: 't' } }).findAll('svg path')).toHaveLength(1)
  })

  it('右侧 slot 落位(页头放动作按钮的口子)', () => {
    const w = mount(PageHead, { props: { icon: 'folder', title: 't' }, slots: { right: '<b class="go">act</b>' } })
    expect(w.find('.slib-head-right .go').text()).toBe('act')
  })
})
