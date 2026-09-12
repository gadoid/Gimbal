import { describe, expect, it } from 'vitest'
import { bodyPathSetOf, genEntryId, injectablePathSetOf, isDeadEntry, normalizeRegistry, pathResolvable, registryIssues } from '../assertion-registry'
import { fieldPathsOf } from '../../utils/dataset-segments'
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

// ── 形状容忍(sidecar 是服务端/手改 JSON;与后端 entry_issues 同构)──

describe('registryIssues/normalizeRegistry — 残缺条目不再炸渲染', () => {
  it('RG-7: path 非对象(null/标量/数组)→ legacy-entry(后端 isinstance(path, dict) 同判)', () => {
    const forms = [null, 0, 'body', [], ['$.amount']]
    for (const p of forms) {
      const e = { ...E(), path: p } as unknown as AssertionEntry
      expect(isLegacyEntry(e)).toBe(true)
      expect(registryIssues(e, 2, bodyPaths(BODY0), targets({}))).toEqual([{ kind: 'legacy-entry' }])
    }
    // 非对象**条目**同样按旧形状处理(不解引用 e.path)
    expect(isLegacyEntry('junk' as unknown as AssertionEntry)).toBe(true)
    expect(isLegacyEntry(null as unknown as AssertionEntry)).toBe(true)
  })

  it('RG-8: stepIndex 非整数("0"/null/1.5)→ step-oob(不再当活条目)', () => {
    for (const si of ['0', null, 1.5, undefined]) {
      const e = { ...E(), path: { stepIndex: si, source: 'body', jsonpath: '$.amount' } } as unknown as AssertionEntry
      expect(isLegacyEntry(e)).toBe(false)
      expect(registryIssues(e, 2, bodyPaths(BODY0), targets({})))
        .toContainEqual({ kind: 'step-oob', stepIndex: si })
      expect(isDeadEntry(e, 2, bodyPaths(BODY0), targets({}))).toBe(true)
    }
  })

  it('RG-9: asserts 缺键 / 非数组 → 视作空(不抛);单条非对象或 stepIndex 非整数 → 跳过', () => {
    for (const asserts of [undefined, null, 'x', 0]) {
      const e = { ...E(), asserts } as unknown as AssertionEntry
      expect(registryIssues(e, 2, bodyPaths(BODY0), targets({}))).toEqual([])
    }
    const mixed = {
      ...E(),
      asserts: ['junk', null, { stepIndex: '0', target: '$.x', mode: 'override' },
        { stepIndex: 9, target: '$.y', mode: 'append' }],
    } as unknown as AssertionEntry
    expect(registryIssues(mixed, 2, bodyPaths(BODY0), targets({})))
      .toEqual([{ kind: 'step-oob', stepIndex: 9 }])
  })

  it('RG-10: normalizeRegistry 丢弃非对象条目 + 补 asserts;合法条目零改动', () => {
    const live = E()
    const legacy = LEGACY
    const out = normalizeRegistry({ entries: ['junk', null, 7, [], live, legacy, { id: 'x' }] })
    expect(out.entries[0]).toBe(live)                       // 合法条目原样(浅引用不变)
    expect(out.entries[1]).toBe(legacy)
    expect(out.entries[2]).toEqual({ id: 'x', asserts: [] })  // 缺 asserts → 补空
    expect(out.entries.length).toBe(3)
    // 非数组 / 缺键 / null 三种垃圾容器 → 空注册表(原行为)
    expect(normalizeRegistry(undefined).entries).toEqual([])
    expect(normalizeRegistry({}).entries).toEqual([])
    expect(normalizeRegistry({ entries: null }).entries).toEqual([])
  })
})

// ── 可注入面(spec v3.1 §2.1):body 现存 ∪ 契约声明(全状态)──────────
const DECLS = [
  { name: 'bl_no', path: '$.bl_no', state: 'form', required: true, description: '' },
  { name: 'customer_id', path: '$.customer_id', state: 'carry', required: true, description: '' },
  { name: 'items', path: '$.items', state: 'form', required: false, description: '',
    children: [{ name: 'sku', path: '$.items.sku', state: 'form', required: true, description: '' }] },
] as any
const STEP_FORM_ONLY = { request: { body: { bl_no: '${var.bl_no}' } } }

describe('可注入面 — 契约声明字段地址化(spec v3.1 §2.1)', () => {
  it('IS-1: 声明面进集合(含 carry 与容器条目,模板形态)', () => {
    const s = injectablePathSetOf(fieldPathsOf(STEP_FORM_ONLY as any), DECLS)
    expect(s.has('$')).toBe(true)
    expect(s.has('$.bl_no')).toBe(true)          // form
    expect(s.has('$.customer_id')).toBe(true)    // carry —— 本次放宽的核心对象
    expect(s.has('$.items')).toBe(true)          // 容器条目自身也是合法地址
    expect(s.has('$.items.sku')).toBe(true)      // children 平铺
  })

  it('IS-2: body 现存路径进集合(实例形态)', () => {
    const step = { request: { body: { items: [{ sku: 'x' }] } } }
    const s = injectablePathSetOf(fieldPathsOf(step as any), [])
    expect(s.has('$.items[0].sku')).toBe(true)
  })

  it('IS-3: 声明命中即可解析 —— 实例与模板两种形态都试', () => {
    const s = injectablePathSetOf(fieldPathsOf(STEP_FORM_ONLY as any), DECLS)
    expect(pathResolvable('$.customer_id', s)).toBe(true)   // carry:放宽后可用
    expect(pathResolvable('$.items[0].sku', s)).toBe(true)  // 实例形态对齐模板声明
    expect(pathResolvable('$.items[1]', s)).toBe(true)      // 容器前缀
    expect(pathResolvable('$.nope', s)).toBe(false)         // 两边都没有 → 仍判死(拼写错误仍被抓)
  })

  it('IS-4: 无声明面(降级)→ 判定等于旧的 body 面(从严)', () => {
    const s = injectablePathSetOf(fieldPathsOf(STEP_FORM_ONLY as any), undefined)
    expect(pathResolvable('$.bl_no', s)).toBe(true)
    expect(pathResolvable('$.customer_id', s)).toBe(false)
  })

  it('IS-5: body 实例路径不因下标归一被吃掉(旧行为不回退)', () => {
    const step = { request: { body: { items: [{ sku: 'x' }, { sku: 'y' }] } } }
    const s = injectablePathSetOf(fieldPathsOf(step as any), [])
    expect(pathResolvable('$.items[1].sku', s)).toBe(true)
    expect(pathResolvable('$.items[0]', s)).toBe(true)
    expect(pathResolvable('$.items', s)).toBe(true)
  })

  it('IS-6: 模板形态 + 容器前缀分支(声明面只有深层 child,无容器条目)', () => {
    // 声明面没有 $.items 容器条目 — 命中只能经 form2(模板化)+ 前缀判定
    const s = injectablePathSetOf([], [{ name: 'sku', path: '$.items.sku' } as any])
    expect(s.has('$.items')).toBe(false)                  // 前提:容器条目确实缺席
    expect(pathResolvable('$.items[0]', s)).toBe(true)    // form2 前缀:$.items. 命中
    expect(pathResolvable('$.items[0].nope', s)).toBe(false)  // 深层不存在的段仍判死
  })
})
