/**
 * RunDialog — 无环境版 + 并集绑定行(spec 2026-08-27 D2/D3)
 *
 * 锁死:
 * - 无环境语义:模板不含「执行环境」,confirm 无 envId,发起键不再被 env 门控
 * - serviceRows = 声明 ∪ 引用并集:声明行预填 URL、未声明行标红「未声明」
 * - 未声明行现场填 URL = 救燃绑定(confirm 携带该 url)
 * - 预填的声明值未改动时 confirm 不重复上送(非覆盖不进 serviceBindings)
 * - confirm 携带 serviceBindings(空绑定条目剔除)
 * - 存为方案快照无 envId
 * - 存为方案快照绑定与 confirm 同口径:预填未改动的声明 URL 不入快照
 *   (防回放/导出钉死旧声明 URL),显式覆盖/救燃/alias 才入
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RunDialog from '../RunDialog.vue'

const BASE_PROPS = {
  dataSets: [],
  schemes: [{ name: '冒烟-qa1', dataSetIds: [],
              serviceBindings: { 'fin-service': { authAlias: 'qa1' } } }],
  lastRunOverlay: null,
  serviceRows: [
    { service: 'fin-service', declaredUrl: 'https://authored.fin' },
    { service: 'order-svc', declaredUrl: null },          // 引用未声明 → 红
  ],
  authOptions: ['qa1', 'qa2'],
}

function mountDlg(props: Partial<typeof BASE_PROPS> = {}) {
  return mount(RunDialog, {
    props: { visible: true, ...BASE_PROPS, ...props },
    global: { stubs: { teleport: true } },
  })
}

describe('执行环境退役(D2)', () => {
  it('模板无环境区/无环境文案;confirm 无 envId', async () => {
    const w = mountDlg()
    expect(w.find('.env-grid').exists()).toBe(false)
    expect(w.text()).not.toContain('执行环境')
    await w.find('[data-testid="run-confirm"]').trigger('click')
    const evt = w.emitted('confirm')![0] as unknown[]
    expect(evt).toHaveLength(2)                       // (dataSetIds, opts)
  })

  it('存为方案快照无 envId', async () => {
    const w = mountDlg()
    await w.find('.rd-scheme-name').setValue('冒烟-新方案')
    await w.find('[data-testid="save-scheme"]').trigger('click')
    const s = w.emitted('saveScheme')![0][0] as any
    expect('envId' in s).toBe(false)
    expect(s.dataSetIds).toEqual([])
  })
})

describe('方案删除', () => {
  it('临时手填/上次运行无删除按钮;选中已存方案 → 点击 emit deleteScheme(名字)', async () => {
    const w = mountDlg()
    expect(w.find('[data-testid="delete-scheme"]').exists()).toBe(false)

    await w.find('.rd-scheme-select').setValue('冒烟-qa1')
    expect(w.find('[data-testid="delete-scheme"]').exists()).toBe(true)
    await w.find('[data-testid="delete-scheme"]').trigger('click')
    expect(w.emitted('deleteScheme')![0]).toEqual(['冒烟-qa1'])
    w.unmount()
  })

  it('方案从 schemes 消失(父级删后回填)→ 选择器自动回「临时手填」', async () => {
    const w = mountDlg()
    await w.find('.rd-scheme-select').setValue('冒烟-qa1')
    await w.setProps({ schemes: [] })
    expect((w.find('.rd-scheme-select').element as HTMLSelectElement).value).toBe('__adhoc__')
    w.unmount()
  })
})

describe('并集绑定行(D3)', () => {
  it('声明 ∪ 引用各一行;声明行 URL 预填、未声明行标红', () => {
    const w = mountDlg()
    expect(w.findAll('.rd-bind-row')).toHaveLength(2)
    expect(w.find('.rd-bind-row.is-undeclared').exists()).toBe(true)
    const urls = w.findAll('.rd-bind-url').map((i) => (i.element as HTMLInputElement).value)
    expect(urls[0]).toBe('https://authored.fin')      // 预填声明值
    expect(urls[1]).toBe('')                          // 未声明空,待救燃
  })

  it('未声明行现场填 URL → confirm 携带救燃绑定', async () => {
    const w = mountDlg()
    await w.findAll('.rd-bind-url')[1].setValue('https://rescue.example')
    await w.find('[data-testid="run-confirm"]').trigger('click')
    const opts = (w.emitted('confirm')![0] as unknown[])[1] as {
      serviceBindings?: Record<string, { url?: string }>
    }
    expect(opts.serviceBindings).toEqual({ 'order-svc': { url: 'https://rescue.example' } })
  })

  it('声明值未改动不重复上送;改了才算覆盖绑定', async () => {
    const w = mountDlg()
    await w.find('[data-testid="run-confirm"]').trigger('click')
    let opts = (w.emitted('confirm')![0] as unknown[])[1] as {
      serviceBindings?: Record<string, unknown>
    }
    expect(opts.serviceBindings).toBeUndefined()       // 预填值 == 声明值
    await w.find('.rd-bind-url').setValue('https://override.example')
    await w.find('[data-testid="run-confirm"]').trigger('click')
    opts = (w.emitted('confirm')![1] as unknown[])[1] as {
      serviceBindings?: Record<string, unknown>
    }
    expect(opts.serviceBindings).toEqual({ 'fin-service': { url: 'https://override.example' } })
  })

  it('方案快照绑定与 confirm 同口径:预填未改动的声明 URL 不入快照,显式覆盖/救燃才入', async () => {
    const w = mountDlg()
    await w.find('.rd-scheme-name').setValue('快照口径')
    await w.find('[data-testid="save-scheme"]').trigger('click')
    let s = w.emitted('saveScheme')![0][0] as {
      serviceBindings?: Record<string, { url?: string }>
    }
    // fin-service 预填 == 声明值:不算显式覆盖,不入快照
    // (入快照会被 watch(selectedScheme) 的 b?.url ?? declaredUrl 钉死旧地址)
    expect(s.serviceBindings?.['fin-service']).toBeUndefined()
    expect(s.serviceBindings).toEqual({})              // order-svc 未填同略

    // 声明行改 URL = 显式覆盖;未声明行现场填 = 救燃 → 都入快照
    await w.findAll('.rd-bind-url')[0].setValue('https://override.example')
    await w.findAll('.rd-bind-url')[1].setValue('https://rescue.example')
    await w.find('[data-testid="save-scheme"]').trigger('click')
    s = w.emitted('saveScheme')![1][0] as typeof s
    expect(s.serviceBindings).toEqual({
      'fin-service': { url: 'https://override.example' },
      'order-svc': { url: 'https://rescue.example' },
    })
  })
})
