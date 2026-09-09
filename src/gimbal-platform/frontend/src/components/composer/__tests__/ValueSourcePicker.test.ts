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

// ── §13.5 参数段(stage: params → rows)────────────────────────

describe('ValueSourcePicker — 参数段(spec §13.5)', () => {
  it('paramFields 非空:先渲染参数行,预填自 paramPrefill,查询钮 emit query', async () => {
    const wrapper = mountPicker({
      paramFields: ['customer_id'],
      paramPrefill: { customer_id: 'C1' },
      rows: [],
    })
    // 打开 → 参数段
    const input = wrapper.find('.vsp-param-row input')
    expect((input.element as HTMLInputElement).value).toBe('C1')
    await wrapper.find('.vsp-param-query').trigger('click')
    expect(wrapper.emitted('query')?.[0]).toEqual([{ customer_id: 'C1' }])
  })

  it('↩ 改参数回跳:值保留(修改后回跳可见)', async () => {
    const wrapper = mountPicker({
      paramFields: ['customer_id'],
      paramPrefill: { customer_id: 'C1' },
      rows: [{ policy_name: 'P', policy_id: '1' }],
    })
    await wrapper.find('.vsp-param-query').trigger('click')   // → rows 段
    await wrapper.find('.vsp-back-params').trigger('click')   // ↩ 改参数
    const input = wrapper.find('.vsp-param-row input')
    expect((input.element as HTMLInputElement).value).toBe('C1')   // 值未丢
  })

  it('无 paramFields:零参数段,直通行集(现状零变化)', () => {
    const wrapper = mountPicker({ rows: [{ a: '1' }] })
    expect(wrapper.find('.vsp-params').exists()).toBe(false)
    expect(wrapper.find('table').exists()).toBe(true)
  })

  it('错误态也可 ↩ 改参数(参数面不被错误困住)— 回跳上抛 backParams 由父级清错', async () => {
    // 错误块门控整个 template v-else:仅置本组件 stage 是视觉 no-op,
    // 须 emit backParams 让 Canvas 清 error prop → 参数段才可达(R1)
    const wrapper = mountPicker({
      paramFields: ['customer_id'],
      paramPrefill: { customer_id: 'C1' },
      error: { code: 'sut_error', message: 'x' },
    })
    await wrapper.find('.vsp-back-params').trigger('click')
    expect(wrapper.emitted('backParams')).toHaveLength(1)
  })
})
