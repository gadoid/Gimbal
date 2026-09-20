/**
 * run-bindings — 绑定纯函数单源(执行设计 §1.5)。
 *
 * 此前 explicitBindingOf / degraded / MAX_TOTAL_RUNS 在 RunDialog 与
 * SchemeRunConfigSection 各持一份镜像(注释互认),抽到 utils/run-bindings
 * 后这里钉住口径:
 * - RB-1 显式绑定:与声明相同的 URL 不算显式;未声明行任何非空 URL 都是救燃
 * - RB-2 降级:alias 非空且不在凭证选项
 * - RB-3 失效判定:数据集已删 / 注入条目悬空(死集由 useInjectableSurface
 *   派生,这里只消费)
 * - RB-4 概要行数:段带 rowIndexes 按段计,缺省段 = 整库(空库按 1)
 */
import { describe, expect, it } from 'vitest'
import {
  MAX_TOTAL_RUNS, assembleExplicitBindings, degradedAlias, explicitBindingOf,
  isSchemeInvalid, liveEntryIdSet, schemeInvalidReason, schemeRowsTotal,
  type ServiceRow,
} from '@/utils/run-bindings'
import type { SchemeV2 } from '@/api/scenario-composer'
import type { DataSetSummary } from '@/types/scenario-composer'
import type { AssertionEntry } from '@/types/assertion-registry'

const ROWS: ServiceRow[] = [
  { service: 'svc-decl', declaredUrl: 'http://decl' },
  { service: 'svc-ref', declaredUrl: null },
]

describe('run-bindings — 显式绑定口径(D3)', () => {
  it('RB-1 预填未改动的声明 URL 不算显式;未声明行的非空 URL 是救燃绑定', () => {
    expect(explicitBindingOf({ url: 'http://decl' }, 'http://decl')).toBeUndefined()
    expect(explicitBindingOf({ url: 'http://decl  ' }, 'http://decl')).toBeUndefined()
    expect(explicitBindingOf({ url: 'http://override' }, 'http://decl'))
      .toEqual({ url: 'http://override' })
    expect(explicitBindingOf({ authAlias: 'qa1' }, 'http://decl'))
      .toEqual({ authAlias: 'qa1' })
    // 未声明行:空 URL + 无别名 = 仍然非显式;非空 URL 即救燃
    expect(explicitBindingOf({ url: '' }, null)).toBeUndefined()
    expect(explicitBindingOf({ url: 'http://rescue' }, null))
      .toEqual({ url: 'http://rescue' })
    expect(explicitBindingOf(undefined, null)).toBeUndefined()
  })

  it('RB-1b assembleExplicitBindings 只落显式条目(整表装配,confirm/另存同口径)', () => {
    expect(assembleExplicitBindings({
      'svc-decl': { url: 'http://decl' },          // 预填未改 → 不落
      'svc-ref': { url: 'http://rescue', authAlias: 'qa1' },
      'svc-ghost': { url: 'http://x' },            // 不在并集行里 → 不落
    }, ROWS)).toEqual({ 'svc-ref': { url: 'http://rescue', authAlias: 'qa1' } })
  })
})

describe('run-bindings — 降级与总量闸', () => {
  it('RB-2 alias 非空且不在选项 = 降级;空 alias 恒不降级', () => {
    expect(degradedAlias('gone', ['qa1'])).toBe(true)
    expect(degradedAlias('qa1', ['qa1'])).toBe(false)
    expect(degradedAlias(undefined, [])).toBe(false)
    expect(degradedAlias('', [])).toBe(false)
  })

  it('RB-2b MAX_TOTAL_RUNS 与后端 MAX_RUNS_PER_EXECUTION 同值(200)', () => {
    expect(MAX_TOTAL_RUNS).toBe(200)
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
    serviceBindings: {}, stepTo: null, nRuns: 1, parallel: 1,
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
      injectionEntryIds: [], serviceBindings: {}, stepTo: null, nRuns: 1, parallel: 1,
    }, dataSets)).toBe(0 + 2 + 5 + 1 + 1)
  })
})
