import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ValueSourcePicker from '../ValueSourcePicker.vue'

const rows = [
  { nm: '海运费', id: 1 },
  { nm: '陆运费', id: 2 },
  { nm: '稀疏行' },
]

function mountPicker(over: Record<string, unknown> = {}) {
  return mount(ValueSourcePicker, {
    props: {
      modelValue: true, view: 'cost_list', label: 'nm',
      columns: ['nm', 'id'], rows, truncated: false,
      fetchedAt: '2026-09-08T00:00:00Z', stale: false, loading: false,
      error: null, ...over,
    } as any,
    // RouterLink 无 router 上下文不解析 — 按 TopNav.pool.test.ts 惯例补
    // href 透传 stub(§7.5 认证页直达链接的 a[href] 断言面)。
    global: {
      plugins: [ElementPlus],
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  })
}

describe('ValueSourcePicker(spec §7.3/§7.5)', () => {
  it('渲染行集:label 列 + 绑定列;缺列显示 --', () => {
    const w = mountPicker()
    expect(w.text()).toContain('海运费')
    const cells = w.findAll('td')
    expect(cells[cells.length - 1].text()).toBe('--')   // 稀疏行缺 id 列
  })

  it('本地过滤收窄行集(纯前端,零上游)', async () => {
    const w = mountPicker()
    await w.find('input.vs-filter').setValue('海运')
    expect(w.text()).toContain('海运费')
    expect(w.text()).not.toContain('陆运费')
  })

  it('点击行 → emit select(row)', async () => {
    const w = mountPicker()
    await w.findAll('tr.vsp-row')[0].trigger('click')
    expect(w.emitted('select')![0][0]).toEqual(rows[0])
  })

  it('truncated → 提示条', () => {
    const w = mountPicker({ truncated: true })
    expect(w.text()).toContain('200')
  })

  it('sut_auth_expired → 认证页直达链接', () => {
    const w = mountPicker({ error: { code: 'sut_auth_expired', message: 'x' } })
    expect(w.find('a[href="/auths"]').exists()).toBe(true)
  })

  it('刷新钮 → emit refresh', async () => {
    const w = mountPicker()
    await w.find('button.vs-refresh').trigger('click')
    expect(w.emitted('refresh')).toHaveLength(1)
  })
})
