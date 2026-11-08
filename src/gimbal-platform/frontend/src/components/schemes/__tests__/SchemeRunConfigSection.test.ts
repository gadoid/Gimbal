/**
 * SchemeRunConfigSection — 运行配置区(authz M2a S6「别名瘦身」后口径)
 *
 * 绑定语义 = 「服务键 → 用哪个别名」({svc:{alias}}),URL/凭证字段退役:
 * - 别名 select 只列与服务键同基的注册表别名(槽位带在选项文案里)
 * - 选中 → update:serviceBindings 只落显式条目;清空 → 键移除
 * - binding-url 输入已退役,不再渲染
 * - 存量别名已删 → 行标红(binding-degraded-warn)+ disabled option 保值
 * - 运行参数钳位/总量预览/stepTo 原生 select 行为保持
 */
import { describe, it, expect, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SchemeRunConfigSection from '../SchemeRunConfigSection.vue'
import type { ServiceAliasRow } from '@/api/service-aliases'

const listAllAliasesMock = vi.hoisted(() => vi.fn())
vi.mock('@/api/service-aliases', async (importOriginal) => {
  const real = await importOriginal<typeof import('@/api/service-aliases')>()
  return { ...real, listAllAliases: listAllAliasesMock }
})

const aliasRow = (aliasName: string, baseService: string, slot: string | null = null): ServiceAliasRow =>
  ({ aliasName, baseService, slot, kind: 'plate', createdAt: '', updatedAt: '' })

const BASE = {
  serviceBindings: {}, serviceRows: [
    { service: 'svc-a', declaredUrl: 'http://a' },
    { service: 'svc-b', declaredUrl: null },
    { service: 'svc-bare', declaredUrl: null },
  ],
  stepTo: null as number | null, nRuns: 1, parallel: 1,
  stepCount: 3,
}

function mountSection(
  props: Partial<typeof BASE> & { stepNames?: string[] } = {},
) {
  const w = mount(SchemeRunConfigSection, {
    props: { ...BASE, ...props }, global: { plugins: [] },
  })
  return w
}

describe('SchemeRunConfigSection', () => {
  it('选别名 → update:serviceBindings(仅显式绑定入对象)', async () => {
    listAllAliasesMock.mockResolvedValue([
      aliasRow('svc-a', 'svc-a'),
      aliasRow('svc-a-uat', 'svc-a'),
      aliasRow('svc-b', 'svc-b'),
      aliasRow('svc-b-ro', 'svc-b', 'ro'),
    ])
    const w = mountSection()
    await flushPromises()
    const sel = w.findAll('[data-testid="binding-alias"]')[0]   // svc-a 行
    await sel.setValue('svc-a-uat')
    expect(w.emitted('update:serviceBindings')!.at(-1)![0]).toEqual({
      'svc-a': { alias: 'svc-a-uat' },
    })
  })

  it('清空别名 → 移除该服务键', async () => {
    listAllAliasesMock.mockResolvedValue([aliasRow('svc-a', 'svc-a'), aliasRow('svc-a-uat', 'svc-a')])
    const w = mountSection({ serviceBindings: { 'svc-a': { alias: 'svc-a-uat' } } })
    await flushPromises()
    await w.findAll('[data-testid="binding-alias"]')[0].setValue('')   // 「— 用服务键本身 —」
    expect(w.emitted('update:serviceBindings')!.at(-1)![0]).toEqual({})
  })

  it('binding-url 输入已退役(M2a S6);无同基候选行显示静默说明代替下拉', async () => {
    listAllAliasesMock.mockResolvedValue([aliasRow('svc-a-uat', 'svc-a')])
    const w = mountSection()
    await flushPromises()
    expect(w.find('[data-testid="binding-url"]').exists()).toBe(false)
    expect(w.findAll('input.bind-url').length).toBe(0)
    // svc-a 有候选 → select;svc-b / svc-bare 无候选 → 静默说明
    expect(w.findAll('[data-testid="binding-alias"]')).toHaveLength(1)
    expect(w.text()).toContain('该服务暂无同基别名')
  })

  it('候选按同基过滤;槽位在选项文案带出', async () => {
    listAllAliasesMock.mockResolvedValue([
      aliasRow('svc-a', 'svc-a'),
      aliasRow('svc-a-uat', 'svc-a'),
      aliasRow('svc-a-maker', 'svc-a', 'maker'),
      aliasRow('other', 'other-sys'),
    ])
    const w = mountSection()
    await flushPromises()
    const sel = w.findAll('[data-testid="binding-alias"]')[0]
    const opts = sel.findAll('option').map((o) => o.text())
    expect(opts[0]).toContain('用服务键本身')
    expect(opts.some((t) => t === 'svc-a-uat')).toBe(true)
    expect(opts.some((t) => t.includes('svc-a-maker(槽位 maker)'))).toBe(true)
    expect(opts.some((t) => t.includes('other'))).toBe(false)   // 跨基不列
  })

  it('运行参数钳位:nRuns/parallel 上限 64(Q4 对齐),总量预览 = nRuns×parallel 可见', async () => {
    listAllAliasesMock.mockResolvedValue([])
    const w = mountSection({ nRuns: 5, parallel: 4 })
    await flushPromises()
    expect(w.find('[data-testid="total-preview"]').text()).toContain('20')
  })

  it('总量超 200 → 红字提示超出上限(64 上限内即可触发:64×4=256)', async () => {
    listAllAliasesMock.mockResolvedValue([])
    const w = mountSection({ nRuns: 64, parallel: 4 })
    await flushPromises()
    expect(w.find('[data-testid="total-preview"]').text()).toContain('256')
    expect(w.text()).toContain('超出单次执行总量上限 200')
  })

  // ── I-2:选中的别名被删 → 绑定行警示(spec §9;M2a S6 注册表口径)─────
  it('存量别名已删:行标红警示 + select 以 disabled option 显示原别名', async () => {
    listAllAliasesMock.mockResolvedValue([aliasRow('svc-a', 'svc-a')])
    const w = mountSection({
      serviceBindings: { 'svc-a': { alias: 'ghost' } },       // ghost 不在注册表
    })
    await flushPromises()
    const row = w.findAll('.bind-row')[0]                       // svc-a 行
    expect(row.classes()).toContain('is-degraded')
    expect(w.find('[data-testid="binding-degraded-warn"]').text()).toContain('别名已删')
    // select 值保住:已删 alias 有对应 option(disabled,防重选但可见可存)
    const sel = w.findAll('[data-testid="binding-alias"]')[0]
    const opt = sel.findAll('option').find((o) => o.attributes('value') === 'ghost')
    expect(opt).toBeTruthy()
    expect(opt!.attributes('disabled')).toBeDefined()
    expect(opt!.text()).toContain('ghost')
  })

  it('存量别名仍活:不标降级行(对照组)', async () => {
    listAllAliasesMock.mockResolvedValue([aliasRow('svc-a', 'svc-a'), aliasRow('svc-a-uat', 'svc-a')])
    const w = mountSection({ serviceBindings: { 'svc-a': { alias: 'svc-a-uat' } } })
    await flushPromises()
    expect(w.findAll('.bind-row')[0].classes()).not.toContain('is-degraded')
    expect(w.text()).not.toContain('别名已删')
  })

  // ── stepTo 原生 select(替换 el-input-number:spinner 对空值发射 min(0)
  //    会把「全量」静默写成「第1步后停止」;下拉里 0 只能显式选)──────────
  it('stepTo=null → 选中「运行全部步骤」;选停步索引 → 发射数字', async () => {
    listAllAliasesMock.mockResolvedValue([])
    const w = mountSection()
    await flushPromises()
    const sel = w.find('[data-testid="param-stepto"]')
    expect((sel.element as HTMLSelectElement).value).toBe('')   // null → 空串哨兵
    await sel.setValue('2')
    expect(w.emitted('update:stepTo')!.at(-1)![0]).toBe(2)
    await sel.setValue('0')                                     // 0 合法(首步后停),显式选才可达
    expect(w.emitted('update:stepTo')!.at(-1)![0]).toBe(0)
    await sel.setValue('')
    expect(w.emitted('update:stepTo')!.at(-1)![0]).toBe(null)  // 回到全量
  })

  it('stepTo 存量 0 → select 回显第1步后停止;选项带编排步骤名', async () => {
    listAllAliasesMock.mockResolvedValue([])
    const w = mountSection({ stepTo: 0, stepNames: ['下单', '支付', '发货'] })
    await flushPromises()
    const sel = w.find('[data-testid="param-stepto"]')
    expect((sel.element as HTMLSelectElement).value).toBe('0')
    const opts = sel.findAll('option')
    expect(opts[0].text()).toContain('运行全部步骤')
    expect(opts[1].text()).toContain('第 1 步后停止 · 下单')
    expect(opts[3].text()).toContain('第 3 步后停止 · 发货')
  })
})
