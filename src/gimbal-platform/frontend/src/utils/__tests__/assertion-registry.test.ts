import { describe, expect, it } from 'vitest'
import { bodyPathSetOf, genEntryId, isDeadEntry, pathResolvable, registryIssues } from '../assertion-registry'
import { isLegacyEntry } from '../../types/assertion-registry'
import type { AssertionEntry, LegacyAssertionEntry } from '../../types/assertion-registry'

const E = (over: Partial<AssertionEntry> = {}): AssertionEntry => ({
  id: 'inj-1', name: 'n',
  path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' },
  value: -1,
  asserts: [{ stepIndex: 0, target: '$.response_body.code', operator: 'eq', expected: '400', mode: 'override' }],
  ...over,
})
const LEGACY: LegacyAssertionEntry = {
  id: 'inj-old', name: '旧条目',
  anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount', varName: 'amount' },
  injection: [{ varName: 'amount', value: '-1' }],
  asserts: [],
}
const bodyPaths = (sets: Record<number, string[]>) => (si: number) => new Set(sets[si] ?? [])
const targets = (sets: Record<number, string[]>) => (si: number) => new Set(sets[si] ?? [])
const BODY0 = { 0: ['$.amount', '$.bl_no', '$.items[0].sku'] }

describe('registryIssues — 悬空检测(spec v3 §2)', () => {
  it('RG-1: 全匹配零 issue(path 落在 body 字段树 + override 有匹配)', () => {
    expect(registryIssues(E(), 2, bodyPaths(BODY0), targets({ 0: ['$.response_body.code'] }))).toEqual([])
    expect(isDeadEntry(E(), 2, bodyPaths(BODY0), targets({ 0: ['$.response_body.code'] }))).toBe(false)
  })
  it('RG-2: path/asserts 各自的 stepIndex 越界 → step-oob', () => {
    const e = E({ path: { stepIndex: 5, source: 'body', jsonpath: '$.x' } })
    expect(registryIssues(e, 2, bodyPaths({}), targets({})))
      .toContainEqual({ kind: 'step-oob', stepIndex: 5 })
    const a = E({ asserts: [{ stepIndex: -1, target: '$.y', operator: 'eq', expected: '1', mode: 'append' }] })
    expect(registryIssues(a, 2, bodyPaths(BODY0), targets({})))
      .toContainEqual({ kind: 'step-oob', stepIndex: -1 })
  })
  it('RG-3: jsonpath 不落在该步 body 字段树 → path-unresolvable;容器前缀可解析', () => {
    const e = E({ path: { stepIndex: 0, source: 'body', jsonpath: '$.ghost' } })
    expect(registryIssues(e, 2, bodyPaths(BODY0), targets({ 0: ['$.response_body.code'] })))
      .toContainEqual({ kind: 'path-unresolvable', stepIndex: 0, jsonpath: '$.ghost' })
    // 容器锚点:叶子是它的子路径 → 可解析(Assign 整体覆写该容器)
    const container = E({ path: { stepIndex: 0, source: 'body', jsonpath: '$.items' } })
    expect(registryIssues(container, 2, bodyPaths(BODY0), targets({ 0: ['$.response_body.code'] }))).toEqual([])
    expect(pathResolvable('$.items[0]', new Set(['$.items[0].sku']))).toBe(true)
    expect(pathResolvable('$.amount', new Set(['$.amount']))).toBe(true)
    expect(pathResolvable('$.amoun', new Set(['$.amount']))).toBe(false)   // 前缀字符串不算
  })
  it('RG-4: override 匹配不到既有断言 → override-no-match;append 不查匹配', () => {
    const base = { 0: ['$.response_body.other'] }
    expect(registryIssues(E(), 2, bodyPaths(BODY0), targets(base)))
      .toContainEqual({ kind: 'override-no-match', stepIndex: 0, target: '$.response_body.code' })
    const app = E({ asserts: [{ stepIndex: 0, target: '$.new', operator: 'eq', expected: '1', mode: 'append' }] })
    expect(registryIssues(app, 2, bodyPaths(BODY0), targets(base))).toEqual([])
  })
  it('RG-5: v2 旧条目(无 path)→ legacy-entry;isLegacyEntry 守卫', () => {
    expect(isLegacyEntry(LEGACY)).toBe(true)
    expect(isLegacyEntry(E())).toBe(false)
    expect(registryIssues(LEGACY, 2, bodyPaths(BODY0), targets({}))).toEqual([{ kind: 'legacy-entry' }])
    expect(isDeadEntry(LEGACY, 2, bodyPaths(BODY0), targets({}))).toBe(true)
  })
  it('RG-6: genEntryId 不变;bodyPathSetOf 只收 body 源叶子', () => {
    const a = genEntryId()
    expect(a).toMatch(/^inj-[a-z0-9]{9}$/)
    expect(new Set([a, genEntryId(), genEntryId()]).size).toBe(3)
    expect(bodyPathSetOf([
      { source: 'body', path: '$.a' },
      { source: 'headers', path: '$.h' },
    ])).toEqual(new Set(['$.a']))
  })
})
