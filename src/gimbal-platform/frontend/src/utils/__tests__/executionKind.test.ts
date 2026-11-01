import { describe, expect, it } from 'vitest'

import { NON_SCENARIO_KINDS, isScenarioBacked } from '../executionKind'

describe('utils/executionKind — 执行形态判定(N3 归一 + §3.2 拆判定)', () => {
  it('suite_graph 不挂在真实场景上;缺省/单场景挂(与后端口径一致)', () => {
    expect(isScenarioBacked('suite_graph')).toBe(false)
    expect(isScenarioBacked('scenario')).toBe(true)
    expect(isScenarioBacked(undefined)).toBe(true)
    expect(isScenarioBacked(null)).toBe(true)
    expect(isScenarioBacked('')).toBe(true)
  })

  it('集合与后端 NON_SCENARIO_KINDS 对齐(新增形态只改此集合)', () => {
    expect([...NON_SCENARIO_KINDS]).toEqual(['suite_graph'])
  })
})
