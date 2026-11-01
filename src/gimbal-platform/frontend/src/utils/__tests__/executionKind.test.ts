import { describe, expect, it } from 'vitest'

import { ORCHESTRATION_KINDS, isOrchestrationKind } from '../executionKind'

describe('utils/executionKind — 执行形态判定(N3 归一)', () => {
  it('suite_graph 是编排类;缺省/单场景不是(与后端口径一致)', () => {
    expect(isOrchestrationKind('suite_graph')).toBe(true)
    expect(isOrchestrationKind('scenario')).toBe(false)
    expect(isOrchestrationKind(undefined)).toBe(false)
    expect(isOrchestrationKind(null)).toBe(false)
    expect(isOrchestrationKind('')).toBe(false)
  })

  it('集合与后端 ORCHESTRATION_KINDS 对齐(新增形态只改此集合)', () => {
    expect([...ORCHESTRATION_KINDS]).toEqual(['suite_graph'])
  })
})
