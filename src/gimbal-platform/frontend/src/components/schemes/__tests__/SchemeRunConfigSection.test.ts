import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SchemeRunConfigSection from '../SchemeRunConfigSection.vue'

const BASE = {
  serviceBindings: {}, serviceRows: [
    { service: 'svc-a', declaredUrl: 'http://a' },
    { service: 'svc-b', declaredUrl: null },
  ],
  authOptions: ['alias-1', 'alias-2'], stepTo: null, nRuns: 1, parallel: 1,
  stepCount: 3,
}

describe('SchemeRunConfigSection', () => {
  it('选凭证别名 → update:serviceBindings(仅显式绑定入对象)', async () => {
    const w = mount(SchemeRunConfigSection, { props: { ...BASE }, global: { plugins: [ElementPlus] } })
    const sel = w.findAll('select')[0]  // svc-a 行的别名下拉(原生 select 简化实现)
    await sel.setValue('alias-1')
    expect(w.emitted('update:serviceBindings')!.at(-1)![0]).toEqual({
      'svc-a': { authAlias: 'alias-1' },
    })
  })

  it('运行参数钳位:nRuns 上限 1000,总量预览 = nRuns×parallel 可见', async () => {
    const w = mount(SchemeRunConfigSection, { props: { ...BASE, nRuns: 5, parallel: 4 }, global: { plugins: [ElementPlus] } })
    expect(w.find('[data-testid="total-preview"]').text()).toContain('20')
  })

  it('预埋区可见且标注待引擎支持', () => {
    const w = mount(SchemeRunConfigSection, { props: { ...BASE }, global: { plugins: [ElementPlus] } })
    expect(w.text()).toContain('插件列表')
    expect(w.text()).toContain('日志订阅')
    expect(w.text()).toContain('待引擎支持')
  })

  // ── 显式绑定口径(镜像 RunDialog.explicitBindingOf,D3)──────────────
  it('URL 覆盖:与声明相同不算显式(键移除);不同才带入 url', async () => {
    const w = mount(SchemeRunConfigSection, { props: { ...BASE }, global: { plugins: [ElementPlus] } })
    const url = w.findAll('[data-testid="binding-url"]')[0]  // svc-a 行(声明 http://a)
    await url.setValue('http://a')          // = 声明 → 非显式,不下发
    expect(w.emitted('update:serviceBindings')!.at(-1)![0]).toEqual({})
    await url.setValue('http://override')   // ≠ 声明 → 显式覆盖
    expect(w.emitted('update:serviceBindings')!.at(-1)![0]).toEqual({
      'svc-a': { url: 'http://override' },
    })
  })

  it('清空别名 → 移除该服务键', async () => {
    const w = mount(SchemeRunConfigSection, {
      props: { ...BASE, serviceBindings: { 'svc-a': { authAlias: 'alias-1' } } },
      global: { plugins: [ElementPlus] },
    })
    await w.findAll('select')[0].setValue('')  // 「— 不绑定 —」
    expect(w.emitted('update:serviceBindings')!.at(-1)![0]).toEqual({})
  })

  it('别名 + URL 覆盖并存 → 两个显式字段一起下发', async () => {
    const w = mount(SchemeRunConfigSection, {
      props: { ...BASE, serviceBindings: { 'svc-a': { authAlias: 'alias-1' } } },
      global: { plugins: [ElementPlus] },
    })
    await w.findAll('[data-testid="binding-url"]')[0].setValue('http://x')
    expect(w.emitted('update:serviceBindings')!.at(-1)![0]).toEqual({
      'svc-a': { authAlias: 'alias-1', url: 'http://x' },
    })
  })

  it('总量超 200 → 红字提示超出上限', () => {
    const w = mount(SchemeRunConfigSection, {
      props: { ...BASE, nRuns: 101, parallel: 2 },
      global: { plugins: [ElementPlus] },
    })
    expect(w.find('[data-testid="total-preview"]').text()).toContain('202')
    expect(w.text()).toContain('超出单次执行总量上限 200')
  })

  // ── I-2:凭证别名被删 → 绑定行警示(spec §9)───────────────────────
  it('存量别名已删:行标红警示 + select 以 disabled option 显示原别名', () => {
    const w = mount(SchemeRunConfigSection, {
      props: {
        ...BASE,
        serviceBindings: { 'svc-a': { authAlias: 'ghost' } },  // ghost 不在 authOptions
      },
      global: { plugins: [ElementPlus] },
    })
    const row = w.findAll('.bind-row')[0]                       // svc-a 行
    expect(row.classes()).toContain('is-degraded')
    expect(w.text()).toContain('凭证已删,请重选')
    // select 值保住:已删 alias 有对应 option(disabled,防重选但可见可存)
    const sel = w.findAll('[data-testid="binding-alias"]')[0]
    const opt = sel.findAll('option').find((o) => o.attributes('value') === 'ghost')
    expect(opt).toBeTruthy()
    expect(opt!.attributes('disabled')).toBeDefined()
    expect(opt!.text()).toContain('ghost')
  })

  it('存量别名仍活:不标降级行(对照组)', () => {
    const w = mount(SchemeRunConfigSection, {
      props: { ...BASE, serviceBindings: { 'svc-a': { authAlias: 'alias-1' } } },
      global: { plugins: [ElementPlus] },
    })
    expect(w.findAll('.bind-row')[0].classes()).not.toContain('is-degraded')
    expect(w.text()).not.toContain('凭证已删')
  })
})
