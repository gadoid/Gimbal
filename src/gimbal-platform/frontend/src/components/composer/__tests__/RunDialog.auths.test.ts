/**
 * RunDialog v2 — 无环境版 + 并集绑定行(spec 2026-08-27 D2/D3,阶段③ v2 改写)
 *
 * 锁定(断言语义与旧版一致,挂载面换默认方案态):
 * - 无环境语义:模板不含「执行环境」,confirm 无 envId,发起键不再被 env 门控
 * - serviceRows = 声明 ∪ 引用并集:声明行预填 URL、未声明行标红「未声明」
 * - 未声明行现场填 URL = 救燃绑定(confirm 携带该 url)
 * - 预填的声明值未改动时 confirm 不重复上送(非覆盖不进 serviceBindings)
 * - confirm 携带 serviceBindings(空绑定条目剔除)
 * - 另存为方案快照无 envId
 * - 另存为方案快照绑定与 confirm 同口径:预填未改动的声明 URL 不入快照
 *   (防回放/导出钉死旧声明 URL),显式覆盖/救燃/alias 才入
 * - v2 新增:默认方案态绑定初始预填来自默认方案存量(工作台可配),声明 URL 兜底
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RunDialog from '../RunDialog.vue'
import type { SchemeV2 } from '@/api/scenario-composer'

/** 默认方案绑定存量为空 = 纯声明预填态(等价旧「临时手填」的初始绑定) */
const DEFAULT_SCHEME: SchemeV2 = {
  schemeId: 'rs-def', name: '默认方案', isDefault: true,
  dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
  stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
}

const BASE_PROPS = {
  dataSets: [],
  schemes: [DEFAULT_SCHEME],
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
    expect(evt).toHaveLength(2)                       // (dataSetSelection, opts)
  })

  it('另存为方案快照无 envId', async () => {
    const w = mountDlg()
    await w.find('[data-testid="scheme-name-input"]').setValue('冒烟-新方案')
    await w.find('[data-testid="save-as-scheme"]').trigger('click')
    const s = w.emitted('saveAsScheme')![0][0] as Record<string, unknown>
    expect('envId' in s).toBe(false)
    expect(s.dataSetSelection).toEqual([])            // 基线空选择
  })
})

describe('并集绑定行(D3,默认方案态)', () => {
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

  it('另存快照绑定与 confirm 同口径:预填未改动的声明 URL 不入快照,显式覆盖/救燃才入', async () => {
    const w = mountDlg()
    await w.find('[data-testid="scheme-name-input"]').setValue('快照口径')
    await w.find('[data-testid="save-as-scheme"]').trigger('click')
    let s = w.emitted('saveAsScheme')![0][0] as {
      serviceBindings?: Record<string, { url?: string }>
    }
    // fin-service 预填 == 声明值:不算显式覆盖,不入快照(入快照会被
    // 绑定预填的 b?.url ?? declaredUrl 钉死旧地址)
    expect(s.serviceBindings?.['fin-service']).toBeUndefined()
    expect(s.serviceBindings).toEqual({})              // order-svc 未填同略

    // 声明行改 URL = 显式覆盖;未声明行现场填 = 救燃 → 都入快照
    await w.findAll('.rd-bind-url')[0].setValue('https://override.example')
    await w.findAll('.rd-bind-url')[1].setValue('https://rescue.example')
    await w.find('[data-testid="save-as-scheme"]').trigger('click')
    s = w.emitted('saveAsScheme')![1][0] as typeof s
    expect(s.serviceBindings).toEqual({
      'fin-service': { url: 'https://override.example' },
      'order-svc': { url: 'https://rescue.example' },
    })
  })
})

describe('默认方案存量绑定预填(v2)', () => {
  it('工作台配置的默认方案绑定 → alias/覆盖 URL 预填,confirm 下发显式绑定', async () => {
    const w = mountDlg({
      schemes: [{
        ...DEFAULT_SCHEME,
        serviceBindings: {
          'fin-service': { authAlias: 'qa1', url: 'https://pinned.fin' },
        },
      }],
    })
    const urls = w.findAll('.rd-bind-url').map((i) => (i.element as HTMLInputElement).value)
    expect(urls[0]).toBe('https://pinned.fin')         // 方案存量优先于声明值
    await w.find('[data-testid="run-confirm"]').trigger('click')
    const opts = (w.emitted('confirm')![0] as unknown[])[1] as {
      serviceBindings?: Record<string, { authAlias?: string; url?: string }>
    }
    // alias 显式;覆盖 URL ≠ 声明值 → 均下发
    expect(opts.serviceBindings).toEqual({
      'fin-service': { authAlias: 'qa1', url: 'https://pinned.fin' },
    })
  })
})
