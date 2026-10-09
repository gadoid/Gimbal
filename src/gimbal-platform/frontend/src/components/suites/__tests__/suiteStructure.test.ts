/** suiteStructure.ts 纯函数测试(重构方案「前端模块」:单独单测)。 */
import { describe, it, expect } from 'vitest'
import {
  MODES, modeMeta, estimateOrchRuns, layeredUnits, needsHasCycle,
  runStatusTone, MODE_LABEL, inferStructure, orderByStructure,
  canvasEdgesFromSuite, edgeMakesCycle,
} from '@/utils/suiteStructure'

const members = [
  { scenarioId: 'a' }, { scenarioId: 'b' }, { scenarioId: 'c' },
]

describe('suiteStructure — 模式元数据', () => {
  it('四种模式齐备,键与执行器 mode 一一对应', () => {
    expect(MODES.map((m) => m.key)).toEqual(
      ['aggregate', 'chain', 'fanout', 'compose'])
    expect(modeMeta('chain').label).toContain('串联')
    expect(modeMeta('nope').key).toBe('aggregate')   // 未知回落聚合
    expect(MODE_LABEL.compose).toBe('依赖编排')
  })
})

describe('suiteStructure — 编排预计 runs', () => {
  it('Σ repeat × nRuns;缺省按 1', () => {
    expect(estimateOrchRuns(members, null)).toBe(3)
    expect(estimateOrchRuns(members, {
      units: { a: { repeat: 2 }, b: { nRuns: 3 } },
    })).toBe(2 + 3 + 1)
  })
})

describe('suiteStructure — 依赖编排分层与环检测', () => {
  it('needs 拓扑分层:L0 无依赖,依赖者在其上游上一层', () => {
    const { layers, hasCycle } = layeredUnits(members, {
      units: { b: { needs: ['a'] }, c: { needs: ['a'] } },
    })
    expect(hasCycle).toBe(false)
    expect(layers).toEqual([['a'], ['b', 'c']])
  })

  it('菱形依赖取最长路径层级', () => {
    const { layers } = layeredUnits(members, {
      units: { b: { needs: ['a'] }, c: { needs: ['a', 'b'] } },
    })
    expect(layers).toEqual([['a'], ['b'], ['c']])
  })

  it('needs 指向非成员时被忽略(悬空由服务端校验);环被检出', () => {
    expect(layeredUnits(members, {
      units: { a: { needs: ['ghost'] } },
    }).layers).toEqual([['a', 'b', 'c']])
    expect(needsHasCycle(members, {
      units: { a: { needs: ['c'] }, c: { needs: ['b'] }, b: { needs: ['a'] } },
    })).toBe(true)
  })
})

describe('suiteStructure — 状态色', () => {
  it('done=ok / failed=bad / running=run / 其他 muted', () => {
    expect(runStatusTone('done')).toBe('ok')
    expect(runStatusTone('failed')).toBe('bad')
    expect(runStatusTone('running')).toBe('run')
    expect(runStatusTone('canceled')).toBe('muted')
  })
})

describe('suiteStructure — 画布结构推断(五条规则,自上而下)', () => {
  it('规则 1:没有任何连线(含只有一个单元)→ 聚合', () => {
    expect(inferStructure(['a'], {})).toMatchObject({ mode: 'aggregate', isolated: 1 })
    const r = inferStructure(['a', 'b', 'c'], {})
    expect(r.mode).toBe('aggregate')
    expect(r.isolated).toBe(3)
    expect(r.reason).toContain('互不相连')
  })

  it('规则 2:全部单元连成一条直线 → 串联,给链路顺序', () => {
    const r = inferStructure(
      ['c', 'a', 'b'], { a: [], b: ['a'], c: ['b'] })
    expect(r.mode).toBe('chain')
    expect(r.line).toEqual(['a', 'b', 'c'])
    expect(r.reason).toContain('一条直线')
  })

  it('规则 3:恰有一个单元指向其余全部、其余无连线 → 扇出,该单元为源', () => {
    const r = inferStructure(
      ['a', 'b', 'c'], { b: ['a'], c: ['a'] })
    expect(r.mode).toBe('fanout')
    expect(r.source).toBe('a')
  })

  it('规则 4:其他无环结构(分叉 + 汇合)→ 依赖编排', () => {
    const r = inferStructure(
      ['login', 'order', 'stock', 'pay'],
      { order: ['login'], stock: ['login'], pay: ['order', 'stock'] })
    expect(r.mode).toBe('compose')
    expect(r.isolated).toBe(0)
    expect(r.reason).toContain('依赖编排')
  })

  it('规则 5:部分相连、部分孤立 → 依赖编排并提示孤立单元数', () => {
    const r = inferStructure(
      ['a', 'b', 'c', 'd'], { b: ['a'] })
    expect(r.mode).toBe('compose')
    expect(r.isolated).toBe(2)
    expect(r.reason).toContain('2 个未连线')
  })

  it('直线多于 n-1 条边不是串联(汇合落到依赖编排)', () => {
    const r = inferStructure(
      ['a', 'b', 'c'], { b: ['a'], c: ['a', 'b'] })
    expect(r.mode).toBe('compose')
  })
})

describe('suiteStructure — 按结构排序与画布回归合成', () => {
  it('串联按链路先后写顺序;扇出把源排第一位;其余保持现序', () => {
    const chain = inferStructure(['c', 'a', 'b'], { b: ['a'], c: ['b'] })
    expect(orderByStructure(chain, ['c', 'a', 'b'])).toEqual(['a', 'b', 'c'])
    const fan = inferStructure(['x', 's', 'y'], { x: ['s'], y: ['s'] })
    expect(orderByStructure(fan, ['x', 's', 'y'])).toEqual(['s', 'x', 'y'])
    const agg = inferStructure(['p', 'q'], {})
    expect(orderByStructure(agg, ['q', 'p'])).toEqual(['q', 'p'])
  })

  it('canvasEdgesFromSuite:四种模式反合成画布连线(与推断互逆)', () => {
    expect(canvasEdgesFromSuite('aggregate', ['a', 'b'], {})).toEqual({})
    expect(canvasEdgesFromSuite('chain', ['a', 'b', 'c'], {}))
      .toEqual({ b: ['a'], c: ['b'] })
    expect(canvasEdgesFromSuite('fanout', ['s', 'x', 'y'], {}))
      .toEqual({ x: ['s'], y: ['s'] })
    expect(canvasEdgesFromSuite('compose', ['a', 'b'], { b: { needs: ['a'] } }))
      .toEqual({ b: ['a'] })
    // 往返:直线合成后推断回串联
    const round = canvasEdgesFromSuite('chain', ['a', 'b', 'c'], {})
    expect(inferStructure(['a', 'b', 'c'], round).mode).toBe('chain')
  })

  it('edgeMakesCycle:新连线成环被拒(依赖只能从早的指向晚的)', () => {
    const needs = { b: ['a'], c: ['b'] }   // 既有 a→b→c
    expect(edgeMakesCycle(['a', 'b', 'c'], needs, 'c', 'a')).toBe(true)   // a→b→c 再补 c→a 成环
    expect(edgeMakesCycle(['a', 'b', 'c'], needs, 'a', 'c')).toBe(false)  // c 已是 a 的下游,不成环
    expect(edgeMakesCycle(['a', 'b', 'c'], needs, 'a', 'b')).toBe(false)
  })
})
