/**
 * run-bindings — 绑定纯函数单源(执行设计 §1.5;authz M2a S6 别名瘦身后口径)。
 *
 * 此前 explicitBindingOf / degraded / MAX_TOTAL_RUNS 在 RunDialog 与
 * SchemeRunConfigSection 各持一份镜像(注释互认),抽到 utils/run-bindings
 * 后这里钉住口径:
 * - RB-1 显式绑定:非空 alias 才算显式(url/authAlias 字段已随 M2a S6 退役)
 * - RB-2 降级:选中的别名已不在注册表(被删)
 * - RB-2c 候选:与服务键同基(baseService 相同)的其它别名;svc 自身是
 *   已登记别名名时基取该行的 baseService
 * - RB-3 失效判定:数据集已删 / 注入条目悬空(死集由 useInjectableSurface
 *   派生,这里只消费)
 * - RB-4 概要行数:段带 rowIndexes 按段计,缺省段 = 整库(空库按 1)
 */
import { describe, expect, it } from 'vitest'
import {
  MAX_TOTAL_RUNS, aliasCandidates, assembleExplicitBindings, degradedAlias,
  explicitBindingOf, isSchemeInvalid, liveEntryIdSet, schemeInvalidReason,
  schemeRowsTotal, type ServiceRow,
} from '@/utils/run-bindings'
import type { ServiceAliasRow } from '@/api/service-aliases'
import type { SchemeV2 } from '@/api/scenario-composer'
import type { DataSetSummary } from '@/types/scenario-composer'
import type { AssertionEntry } from '@/types/assertion-registry'

const ROWS: ServiceRow[] = [
  { service: 'svc-decl', declaredUrl: 'http://decl' },
  { service: 'svc-ref', declaredUrl: null },
]

const alias = (aliasName: string, baseService: string, slot: string | null = null): ServiceAliasRow =>
  ({ aliasName, baseService, slot, kind: 'plate', createdAt: '', updatedAt: '' })

describe('run-bindings — 显式绑定口径(D3,M2a S6 别名瘦身)', () => {
  it('RB-1 非空 alias 才算显式;空/缺省 = undefined(键整个移除)', () => {
    expect(explicitBindingOf({ alias: 'fin-maker' })).toEqual({ alias: 'fin-maker' })
    expect(explicitBindingOf({ alias: '  fin-maker  ' })).toEqual({ alias: 'fin-maker' })
    expect(explicitBindingOf({ alias: '' })).toBeUndefined()
    expect(explicitBindingOf({ alias: '   ' })).toBeUndefined()
    expect(explicitBindingOf(undefined)).toBeUndefined()
    expect(explicitBindingOf({})).toBeUndefined()
  })

  it('RB-1b assembleExplicitBindings 只落显式条目(整表装配,confirm/另存同口径)', () => {
    expect(assembleExplicitBindings({
      'svc-decl': { alias: 'svc-decl-uat' },
      'svc-ref': {},                                  // 空 = 用服务键本身 → 不落
      'svc-ghost': { alias: 'ghost-alias' },          // 不在并集行里 → 不落
    }, ROWS)).toEqual({ 'svc-decl': { alias: 'svc-decl-uat' } })
    expect(assembleExplicitBindings({}, ROWS)).toEqual({})
  })
})

describe('run-bindings — 降级与候选(M2a S6)', () => {
  it('RB-2 alias 非空且不在注册表 = 降级;空 alias 恒不降级', () => {
    expect(degradedAlias('gone', ['fin-maker'])).toBe(true)
    expect(degradedAlias('fin-maker', ['fin-maker'])).toBe(false)
    expect(degradedAlias(undefined, [])).toBe(false)
    expect(degradedAlias('', [])).toBe(false)
  })

  it('RB-2b MAX_TOTAL_RUNS 与后端 MAX_RUNS_PER_EXECUTION 同值(200)', () => {
    expect(MAX_TOTAL_RUNS).toBe(200)
  })

  it('RB-2c aliasCandidates:与同基服务的别名;排除服务键本身;svc 是别名名时基取其 baseService', () => {
    const registry = [
      alias('fin', 'fin'),
      alias('fin-maker', 'fin', 'maker'),
      alias('fin-uat', 'fin'),
      alias('order', 'order'),
      alias('order-ro', 'order', 'ro'),
    ]
    // 裸服务键 fin:同基候选 = fin 之外 baseService=fin 的别名
    expect(aliasCandidates('fin', registry).map((a) => a.aliasName))
      .toEqual(['fin-maker', 'fin-uat'])
    // svc 本身是已登记别名名:基 = 该行的 baseService(fin)→ 同上候选
    expect(aliasCandidates('fin-uat', registry).map((a) => a.aliasName))
      .toEqual(['fin', 'fin-maker'])
    // 无同基候选 → 空(面板显示静默说明)
    expect(aliasCandidates('order', registry).map((a) => a.aliasName))
      .toEqual(['order-ro'])
    expect(aliasCandidates('unknown-svc', registry)).toEqual([])
    // 注册表空 → 恒空
    expect(aliasCandidates('fin', [])).toEqual([])
  })
})

describe('run-bindings — 自建方案失效判定', () => {
  const entries: AssertionEntry[] = [
    { id: 'inj-live', name: 'a', path: { stepIndex: 0, source: 'body', jsonpath: '$.a' }, value: 1, asserts: [] },
    { id: 'inj-dead', name: 'b', path: { stepIndex: 0, source: 'body', jsonpath: '$.b' }, value: 1, asserts: [] },
  ]
  const dataSets: DataSetSummary[] = [
    { datasetId: 'ds-1', scenarioId: 'sc', name: 'A', rowCount: 2, preview: [] },
  ]
  const scheme: SchemeV2 = {
    schemeId: 'rs-1', name: 'S', isDefault: false,
    dataSetSelection: [{ datasetId: 'ds-1' }],
    injectionEntryIds: ['inj-live', 'inj-dead'],
    serviceBindings: {}, options: { step_from: null, step_to: null, n_runs: 1, parallel: 1, subscribe: null },
  }

  it('RB-3 活集 = registry 全集 − 宿主门控死集;悬空 → 失效', () => {
    const live = liveEntryIdSet(entries, ['inj-dead'])
    expect([...live]).toEqual(['inj-live'])
    expect(isSchemeInvalid(scheme, dataSets, live)).toBe(true)
    expect(schemeInvalidReason(scheme, dataSets)).toBe('注入条目已悬空或删除')
    // 死集被宿主掩空(契约在途)→ 活 → 不失效(不误报)
    const allLive = liveEntryIdSet(entries, [])
    expect(isSchemeInvalid(scheme, dataSets, allLive)).toBe(false)
  })

  it('RB-3b 引用数据集已删 → 失效,原因指向数据集(换方案可解)', () => {
    const live = liveEntryIdSet(entries, ['inj-dead'])
    const broken: SchemeV2 = { ...scheme, dataSetSelection: [{ datasetId: 'ds-gone' }] }
    expect(isSchemeInvalid(broken, dataSets, live)).toBe(true)
    expect(schemeInvalidReason(broken, dataSets)).toBe('数据集 ds-gone 已删除')
  })
})

describe('run-bindings — 概要行数', () => {
  it('RB-4 段带 rowIndexes 按段计;缺省段 = 整库;空库按 1 隐式行', () => {
    const dataSets: DataSetSummary[] = [
      { datasetId: 'ds-1', scenarioId: 'sc', name: 'A', rowCount: 5, preview: [] },
      { datasetId: 'ds-empty', scenarioId: 'sc', name: 'E', rowCount: 0, preview: [] },
    ]
    expect(schemeRowsTotal({
      schemeId: 'r', name: 's', isDefault: false,
      dataSetSelection: [
        { datasetId: 'ds-1', rowIndexes: [0, 2] },
        { datasetId: 'ds-1' },                       // 整库 5
        { datasetId: 'ds-empty' },                   // 空库 → 1
        { datasetId: 'ds-gone' },                    // 已删 → rowCount 0 → 1
      ],
      injectionEntryIds: [], serviceBindings: {}, options: { step_from: null, step_to: null, n_runs: 1, parallel: 1, subscribe: null },
    }, dataSets)).toBe(0 + 2 + 5 + 1 + 1)
  })
})
