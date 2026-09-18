/**
 * ComposePage 壳 — 页头(title/actions)条件渲染 + 容器双档(样式归一第一批)。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ComposePage from '@/layouts/ComposePage.vue'

describe('ComposePage — 页头与容器', () => {
  it('无 title 时整页头不渲染(纯步骤流页兼容)', () => {
    const w = mount(ComposePage, { slots: { default: '<p>主体</p>' } })
    expect(w.find('header').exists()).toBe(false)
    expect(w.find('footer').exists()).toBe(false)
    w.unmount()
  })

  it('title + actions 渲染页头;容器默认 1200,wide 1480', () => {
    const w = mount(ComposePage, {
      props: { title: '断言注册表' },
      slots: { actions: '<button data-testid="cp-act"/>' },
    })
    expect(w.find('h1').text()).toBe('断言注册表')
    expect(w.find('[data-testid="cp-act"]').exists()).toBe(true)
    expect(w.find('div').classes()).toContain('max-w-[min(1200px,100%)]')
    w.unmount()

    const wide = mount(ComposePage, { props: { title: 't', width: 'wide' } })
    expect(wide.find('div').classes()).toContain('max-w-[min(1480px,100%)]')
    wide.unmount()
  })
})
