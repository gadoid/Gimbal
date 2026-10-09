/** suiteStructure.ts 纯函数测试(重构方案「前端模块」:单独单测)。 */
import { describe, it, expect } from 'vitest'
import {
  MODES, modeMeta, estimateOrchRuns, layeredUnits, needsHasCycle,
  runStatusTone, MODE_LABEL,
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
