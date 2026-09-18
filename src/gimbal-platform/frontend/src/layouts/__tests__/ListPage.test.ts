/**
 * ListPage 壳 — 容器双档 + slot 条件渲染(样式归一第一批)。
 * 默认档必须与旧 max-w-[1200px] 等价(Auths/UsersAdmin 零变化)。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ListPage from '@/layouts/ListPage.vue'

describe('ListPage — 容器双档', () => {
  it('默认 standard:1200 档 min() 钳制(等价旧 max-w-[1200px])', () => {
    const w = mount(ListPage, { props: { title: '列表' } })
    expect(w.find('div').classes()).toContain('max-w-[min(1200px,100%)]')
    expect(w.find('h1').text()).toBe('列表')
    w.unmount()
  })

  it('wide prop:1480 档(宽表格页)', () => {
    const w = mount(ListPage, { props: { title: '场景库', width: 'wide' } })
    expect(w.find('div').classes()).toContain('max-w-[min(1480px,100%)]')
    w.unmount()
  })
})

describe('ListPage — slot 条件渲染', () => {
  it('lead slot:缺席不渲染容器,出席渲染', () => {
    const bare = mount(ListPage, { props: { title: 't' } })
    expect(bare.find('header .mt-3').exists()).toBe(false)
    bare.unmount()

    const w = mount(ListPage, {
      props: { title: 't' },
      slots: { lead: '<p data-testid="lead-p">导语</p>' },
    })
    expect(w.find('[data-testid="lead-p"]').exists()).toBe(true)
    w.unmount()
  })

  it('tabs / toolbar 缺席时不渲染分区容器,出席时渲染', () => {
    const bare = mount(ListPage, { props: { title: 't' } })
    expect(bare.find('div.mt-4').exists()).toBe(false)             // tabs 容器
    expect(bare.find('div.mt-3.flex-wrap').exists()).toBe(false)   // toolbar 容器(页头行也有 flex-wrap,须叠加 mt-3 区分)
    bare.unmount()

    const w = mount(ListPage, {
      props: { title: 't' },
      slots: {
        tabs: '<nav data-testid="tabs-nav"/>',
        toolbar: '<input data-testid="tb-input"/>',
        actions: '<button data-testid="act-btn"/>',
      },
    })
    expect(w.find('[data-testid="tabs-nav"]').exists()).toBe(true)
    expect(w.find('[data-testid="tb-input"]').exists()).toBe(true)
    // toolbar 容器自带 flex-wrap(窄屏换行铺满的流式基础)
    const tb = w.find('[data-testid="tb-input"]').element.parentElement!
    expect(tb.className).toContain('flex-wrap')
    w.unmount()
  })

  it('subtitle:prop 与 slot 共存时 slot 优先(具名插槽回退语义)', () => {
    const w = mount(ListPage, {
      props: { title: 't', subtitle: 'prop 版' },
      slots: { subtitle: 'slot 版' },
    })
    expect(w.find('header p').text()).toBe('slot 版')
    w.unmount()
  })
})
