/**
 * HubDetailPage 壳 — meta slot + 容器双档(样式归一第一批)。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import HubDetailPage from '@/layouts/HubDetailPage.vue'

describe('HubDetailPage — 容器与分区', () => {
  it('默认 standard 1200;wide prop 1480', () => {
    const a = mount(HubDetailPage, { props: { title: '执行详情' } })
    expect(a.find('div').classes()).toContain('max-w-[min(1200px,100%)]')
    a.unmount()

    const b = mount(HubDetailPage, { props: { title: '批次', width: 'wide' } })
    expect(b.find('div').classes()).toContain('max-w-[min(1480px,100%)]')
    b.unmount()
  })

  it('meta slot:缺席不渲染,出席渲染在粗线 summary 之前', () => {
    const bare = mount(HubDetailPage, { props: { title: 't' } })
    expect(bare.find('.text-caption').exists()).toBe(false)
    expect(bare.find('.summary').exists()).toBe(true) // summary 粗线常驻
    bare.unmount()

    const w = mount(HubDetailPage, {
      props: { title: 't' },
      slots: {
        meta: '<span data-testid="meta-line">endpoint · v1 → v2</span>',
        summary: '<p data-testid="sum-p"/>',
      },
    })
    expect(w.find('[data-testid="meta-line"]').exists()).toBe(true)
    // DOM 顺序:meta 在 summary 粗线之前
    const meta = w.find('[data-testid="meta-line"]').element
    const summary = w.find('.summary').element
    expect(meta.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    w.unmount()
  })
})
