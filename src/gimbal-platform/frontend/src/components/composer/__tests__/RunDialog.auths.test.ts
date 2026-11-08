/**
 * RunDialog v2 — 别名绑定(authz M2a S6「别名瘦身」后的默认方案态绑定行)
 *
 * 锁定(旧 URL/凭证绑定口径已退役,本文件按 {svc:{alias}} 语义重写):
 * - 绑定行 = 声明 ∪ 引用并集,一行一个别名 select(候选 = 与服务键同基
 *   的注册表别名;槽位在选项文案里带出,如 fin-maker(槽位 maker))
 * - 无同基候选 → 静默说明代替下拉(用服务键本身),不再有 URL 输入
 * - confirm 携带 serviceBindings = {svc:{alias}}(空绑定条目剔除)
 * - 选中的别名已从注册表删除 → 行标红警示(degraded),不阻塞运行
 * - 另存为方案快照绑定与 confirm 同口径
 * - 默认方案态绑定初始预填来自默认方案存量(工作台可配)
 */
import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import RunDialog from '../RunDialog.vue'
import type { SchemeV2 } from '@/api/scenario-composer'
import type { ServiceAliasRow } from '@/api/service-aliases'

/** 注册表 mock(listAllAliases;RunConfigPanel 挂载自取)。fin 家族两个
 *  候选(一个带槽位)、order 一个候选、bare 无候选。 */
const listAllAliasesMock = vi.hoisted(() => vi.fn())
vi.mock('@/api/service-aliases', async (importOriginal) => {
  const real = await importOriginal<typeof import('@/api/service-aliases')>()
  return { ...real, listAllAliases: listAllAliasesMock }
})

const aliasRow = (aliasName: string, baseService: string, slot: string | null = null): ServiceAliasRow =>
  ({ aliasName, baseService, slot, kind: 'plate', createdAt: '', updatedAt: '' })

function seedAliases(rows: ServiceAliasRow[]) {
  listAllAliasesMock.mockReset().mockResolvedValue(rows)
}

/** 默认方案绑定存量为空 = 纯「用服务键本身」初始态 */
const DEFAULT_SCHEME: SchemeV2 = {
  schemeId: 'rs-def', name: '默认方案', isDefault: true,
  dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
  options: { step_from: null, step_to: null, n_runs: 1, parallel: 1, subscribe: null },
}

const BASE_PROPS = {
  dataSets: [],
  schemes: [DEFAULT_SCHEME],
  serviceRows: [
    { service: 'fin', declaredUrl: 'https://authored.fin' },
    { service: 'order', declaredUrl: null },
    { service: 'bare', declaredUrl: null },
  ],
}

function mountDlg(props: Partial<typeof BASE_PROPS> & { initialSchemeId?: string | null } = {}) {
  return mount(RunDialog, {
    props: { visible: true, ...BASE_PROPS, ...props },
    global: { stubs: { teleport: true } },
  })
}

describe('别名候选按同基渲染(M2a S6)', () => {
  it('select 只列与服务键同基的别名;槽位在选项文案带出;无候选 → 静默说明代替下拉', async () => {
    seedAliases([
      aliasRow('fin', 'fin'),
      aliasRow('fin-maker', 'fin', 'maker'),
      aliasRow('fin-uat', 'fin'),
      aliasRow('order-ro', 'order', 'ro'),
      aliasRow('other', 'other-sys'),
    ])
    const w = mountDlg()
    await flushPromises()
    const selects = w.findAll('[data-testid="binding-alias"]')
    expect(selects).toHaveLength(2)                     // fin + order;bare 无候选 → 无 select
    const finOpts = selects[0].findAll('option').map((o) => o.text())
    expect(finOpts[0]).toContain('用服务键本身')
    expect(finOpts).toContain('fin-maker(槽位 maker)')
    expect(finOpts.some((t) => t === 'fin-uat')).toBe(true)
    expect(finOpts.some((t) => t.includes('order-ro'))).toBe(false)   // 跨基不列
    const orderOpts = selects[1].findAll('option').map((o) => o.text())
    expect(orderOpts.some((t) => t.includes('order-ro(槽位 ro)'))).toBe(true)
    // bare:静默说明行,没有 select
    expect(w.text()).toContain('该服务暂无同基别名')
  })

  it('URL 输入 / 凭证下拉不再存在(M2a S6 退役口径)', async () => {
    seedAliases([aliasRow('fin-maker', 'fin', 'maker')])
    const w = mountDlg()
    await flushPromises()
    expect(w.find('.rd-bind-url').exists()).toBe(false)
    expect(w.find('.rd-bind-user option[value="qa1"]').exists()).toBe(false)
    expect(w.text()).not.toContain('未声明')
    expect(w.text()).not.toContain('别名默认')
  })
})

describe('confirm 下发 {svc:{alias}}(M2a S6)', () => {
  it('选别名 → confirm 只携带该服务的显式绑定;未选行不落键', async () => {
    seedAliases([
      aliasRow('fin', 'fin'),
      aliasRow('fin-maker', 'fin', 'maker'),
      aliasRow('order', 'order'),
      aliasRow('order-ro', 'order'),
    ])
    const w = mountDlg()
    await flushPromises()
    await w.findAll('[data-testid="binding-alias"]')[0].setValue('fin-maker')
    await w.find('[data-testid="run-confirm"]').trigger('click')
    const evt = w.emitted('confirm')![0] as unknown[]
    const opts = evt[1] as { serviceBindings?: Record<string, { alias?: string }> }
    expect(opts.serviceBindings).toEqual({ fin: { alias: 'fin-maker' } })
  })

  it('另存快照绑定与 confirm 同口径:空选择不入快照,显式选择才入', async () => {
    seedAliases([aliasRow('fin', 'fin'), aliasRow('fin-maker', 'fin', 'maker')])
    const w = mountDlg()
    await flushPromises()
    await w.find('[data-testid="scheme-name-input"]').setValue('快照口径')
    await w.find('[data-testid="save-as-scheme"]').trigger('click')
    let s = w.emitted('saveAsScheme')![0][0] as {
      serviceBindings?: Record<string, { alias?: string }>
    }
    expect(s.serviceBindings).toEqual({})               // 全部「用服务键本身」→ 空快照

    await w.find('[data-testid="binding-alias"]').setValue('fin-maker')
    await w.find('[data-testid="save-as-scheme"]').trigger('click')
    s = w.emitted('saveAsScheme')![1][0] as typeof s
    expect(s.serviceBindings).toEqual({ fin: { alias: 'fin-maker' } })
  })
})

describe('默认方案存量绑定预填 + 降级(M2a S6)', () => {
  it('工作台配置的默认方案绑定 → alias 预填回显,confirm 原样下发', async () => {
    seedAliases([aliasRow('fin', 'fin'), aliasRow('fin-maker', 'fin', 'maker')])
    const w = mountDlg({
      schemes: [{
        ...DEFAULT_SCHEME,
        serviceBindings: { fin: { alias: 'fin-maker' } },
      }],
    })
    await flushPromises()
    const sel = w.find('[data-testid="binding-alias"]')
    expect((sel.element as HTMLSelectElement).value).toBe('fin-maker')
    await w.find('[data-testid="run-confirm"]').trigger('click')
    const opts = (w.emitted('confirm')![0] as unknown[])[1] as {
      serviceBindings?: Record<string, { alias?: string }>
    }
    expect(opts.serviceBindings).toEqual({ fin: { alias: 'fin-maker' } })
  })

  it('选中别名已删 → 行标红警示;select 以 disabled option 保住原值', async () => {
    seedAliases([aliasRow('fin', 'fin')])               // fin-maker 不在注册表
    const w = mountDlg({
      schemes: [{
        ...DEFAULT_SCHEME,
        serviceBindings: { fin: { alias: 'fin-maker' } },
      }],
    })
    await flushPromises()
    const row = w.findAll('.rd-bind-row')[0]
    expect(row.classes()).toContain('is-degraded')
    expect(w.text()).toContain('别名已删')
    const sel = w.find('[data-testid="binding-alias"]')
    const opt = sel.findAll('option').find((o) => o.attributes('value') === 'fin-maker')
    expect(opt).toBeTruthy()
    expect(opt!.attributes('disabled')).toBeDefined()
    // 重选 → 降级解除(「— 用服务键本身 —」= 清空别名)
    await sel.setValue('')
    expect(row.classes()).not.toContain('is-degraded')
  })

  it('自建方案概要行展示 svc → alias;存量别名已删标红', async () => {
    seedAliases([aliasRow('fin', 'fin')])
    const w = mountDlg({
      schemes: [
        DEFAULT_SCHEME,
        {
          ...DEFAULT_SCHEME, schemeId: 'rs-1', name: '冒烟', isDefault: false,
          serviceBindings: { fin: { alias: 'fin-maker' } },
        },
      ],
      initialSchemeId: 'rs-1',
    })
    await flushPromises()
    const bind = w.find('.rd-sum-bind')
    expect(bind.text()).toContain('fin → fin-maker')
    expect(bind.classes()).toContain('is-degraded')
    expect(w.text()).toContain('别名已删,去工作台重选')
  })
})
