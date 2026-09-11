import { describe, expect, it } from 'vitest'
import { genEntryId, isDeadEntry, registryIssues } from '../assertion-registry'
import type { AssertionEntry } from '../../types/assertion-registry'

const E = (over: Partial<AssertionEntry> = {}): AssertionEntry => ({
  id: 'inj-1', name: 'n',
  anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount', varName: 'amount' },
  injection: [{ varName: 'amount', value: '-1' }],
  asserts: [{ stepIndex: 0, target: '$.response_body.code', operator: 'eq', expected: '400', mode: 'override' }],
  ...over,
})
const VARS = new Set(['amount', 'bl_no'])
const targets = (sets: Record<number, string[]>) => (si: number) => new Set(sets[si] ?? [])

describe('registryIssues — 悬空检测(spec §3)', () => {
  it('RG-1: 全匹配零 issue', () => {
    expect(registryIssues(E(), 2, VARS, targets({ 0: ['$.response_body.code'] }))).toEqual([])
    expect(isDeadEntry(E(), 2, VARS, targets({ 0: ['$.response_body.code'] }))).toBe(false)
  })
  it('RG-2: stepIndex 越界(anchor + asserts 都查)', () => {
    const e = E({ anchor: { stepIndex: 5, source: 'body', jsonpath: '$.x' } })
    const issues = registryIssues(e, 2, VARS, targets({}))
    expect(issues).toContainEqual({ kind: 'step-oob', stepIndex: 5 })
  })
  it('RG-3: injection.varName ∉ config.vars → var-unknown', () => {
    const e = E({ injection: [{ varName: 'ghost', value: '1' }] })
    expect(registryIssues(e, 2, VARS, targets({ 0: ['$.response_body.code'] })))
      .toContainEqual({ kind: 'var-unknown', varName: 'ghost' })
  })
  it('RG-4: override 匹配不到既有断言 → override-no-match;append 不查匹配', () => {
    const base = { 0: ['$.response_body.other'] }
    expect(registryIssues(E(), 2, VARS, targets(base)))
      .toContainEqual({ kind: 'override-no-match', stepIndex: 0, target: '$.response_body.code' })
    const app = E({ asserts: [{ stepIndex: 0, target: '$.new', operator: 'eq', expected: '1', mode: 'append' }] })
    expect(registryIssues(app, 2, VARS, targets(base))).toEqual([])
  })
  it('RG-5: genEntryId 前缀 inj- 且同毫秒不撞', () => {
    const a = genEntryId()
    expect(a).toMatch(/^inj-[a-z0-9]{9}$/)
    expect(new Set([a, genEntryId(), genEntryId()]).size).toBe(3)
  })
})
