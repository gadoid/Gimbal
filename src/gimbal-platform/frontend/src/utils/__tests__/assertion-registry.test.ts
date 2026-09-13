import { describe, expect, it } from 'vitest'
import { bodyPathSetOf, containerPrefixes, genEntryId, injectablePathSetOf, normalizeRegistry, pathResolvable, registryIssues } from '../assertion-registry'
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
/** registryIssues 的入参是**已物化容器前缀**的可注入面 —— 调用方
 *  (`injectablePathSetOf` / `bodyPathSetOf`)造的就是这种集合,测试照同一构造造,
 *  不手写裸叶子集(裸集不是判定输入,见 RG-3)。 */
const bodyPaths = (sets: Record<number, string[]>) => (si: number) =>
  bodyPathSetOf((sets[si] ?? []).map((path) => ({ source: 'body', path })))
const targets = (sets: Record<number, string[]>) => (si: number) => new Set(sets[si] ?? [])
const BODY0 = { 0: ['$.amount', '$.bl_no', '$.items[0].sku'] }

describe('registryIssues — 悬空检测(spec v3 §2)', () => {
  it('RG-1: 全匹配零 issue(path 落在 body 字段树 + override 有匹配)', () => {
    expect(registryIssues(E(), 2, bodyPaths(BODY0), targets({ 0: ['$.response_body.code'] }))).toEqual([])
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
    // 容器路径靠集合里的**前缀成员**命中(该成员由集合构造侧物化)
    expect(pathResolvable('$.items[0]', bodyPaths(BODY0)(0))).toBe(true)
    expect(pathResolvable('$.amount', new Set(['$.amount']))).toBe(true)
    expect(pathResolvable('$.amoun', new Set(['$.amount']))).toBe(false)   // 前缀字符串不算
    // 反向钉住责任边界:未物化前缀的裸集合不是判定输入 ⇒ 前缀是**造集合**的活
    expect(pathResolvable('$.items[0]', new Set(['$.items[0].sku']))).toBe(false)
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
  })
  it('RG-6: genEntryId 不变;bodyPathSetOf 只收 body 源叶子(并物化其容器前缀)', () => {
    const a = genEntryId()
    expect(a).toMatch(/^inj-[a-z0-9]{9}$/)
    expect(new Set([a, genEntryId(), genEntryId()]).size).toBe(3)
    expect(bodyPathSetOf([
      { source: 'body', path: '$.a' },
      { source: 'headers', path: '$.h' },
    ])).toEqual(new Set(['$.a', '$']))          // headers 源不进面;$ 是 $.a 的容器前缀
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

// ── 容器前缀(run_injection._container_prefixes 的前端同构件)────────

describe('containerPrefixes 与后端 _container_prefixes 同构', () => {
  // 后端语义(run_injection.py:112):段边界 —— `.` 之后 / `[` 之前
  it.each([
    ['$.a.b', ['$', '$.a']],
    ['$.tags[0]', ['$', '$.tags']],
    ['$.a.b.c', ['$', '$.a', '$.a.b']],
    ['$', []],
    ['$.a.b[0].c', ['$', '$.a', '$.a.b', '$.a.b[0]']],
  ])('%s → %j', (path, expected) => {
    expect(containerPrefixes(path)).toEqual(expected)
  })
})

// ── 可注入面(spec v3.1 §2.1):body 现存 ∪ 契约声明(全状态)──────────
// 声明面由后端算好、随 /full 送达(扁平面:归一化 / 容器前缀 / 模板形态全展开,
// spec §2.2)。对应目录条目:bl_no(form) / customer_id(carry) /
// items(容器条目,child sku)—— 候选树 UI 仍读这棵树,判定面只读这个面。
const DECLS_SURFACE = ['$', '$.bl_no', '$.customer_id', '$.items', '$.items.sku']
const STEP_FORM_ONLY = { request: { body: { bl_no: '${var.bl_no}' } } }

describe('可注入面 — 契约声明字段地址化(spec v3.1 §2.1)', () => {
  it('IS-1: 声明面进集合(含 carry 与容器条目)', () => {
    const s = injectablePathSetOf(fieldPathsOf(STEP_FORM_ONLY as any), DECLS_SURFACE)
    expect(s.has('$')).toBe(true)
    expect(s.has('$.bl_no')).toBe(true)          // form
    expect(s.has('$.customer_id')).toBe(true)    // carry —— 放宽的核心对象
    expect(s.has('$.items')).toBe(true)          // 容器条目自身也是合法地址
    expect(s.has('$.items.sku')).toBe(true)      // children 平铺
  })

  it('IS-2: body 现存路径进集合(实例形态)', () => {
    const step = { request: { body: { items: [{ sku: 'x' }] } } }
    const s = injectablePathSetOf(fieldPathsOf(step as any), [])
    expect(s.has('$.items[0].sku')).toBe(true)
  })

  it('IS-3: 声明命中即可解析 —— 实例与模板两种形态都试', () => {
    const s = injectablePathSetOf(fieldPathsOf(STEP_FORM_ONLY as any), DECLS_SURFACE)
    expect(pathResolvable('$.customer_id', s)).toBe(true)   // carry:可用
    expect(pathResolvable('$.items[0].sku', s)).toBe(true)  // 实例形态对齐模板声明
    expect(pathResolvable('$.items[1]', s)).toBe(true)      // 模板形态精确命中声明容器条目 $.items
    expect(pathResolvable('$.nope', s)).toBe(false)         // 两边都没有 → 仍判死(拼写错误仍被抓)
  })

  it('IS-4: 无声明面(降级)→ 判定从严,只剩 body 面', () => {
    // null = 契约在、声明面不可解析(后端给 null);undefined = 面字段缺席;
    // [] = 真无声明。三者的声明半都添不进成员,判定一律只剩 body 面 ——
    // 「降级 vs 真无声明」的区别由后端保留(§5),前端这里没有可并的语义
    for (const surface of [null, undefined, [] as string[]]) {
      const s = injectablePathSetOf(fieldPathsOf(STEP_FORM_ONLY as any), surface)
      expect(pathResolvable('$.bl_no', s)).toBe(true)
      expect(pathResolvable('$.customer_id', s)).toBe(false)
    }
  })

  it('IS-5: body 实例路径不因下标归一被吃掉(旧行为不回退)', () => {
    const step = { request: { body: { items: [{ sku: 'x' }, { sku: 'y' }] } } }
    const s = injectablePathSetOf(fieldPathsOf(step as any), [])
    expect(pathResolvable('$.items[1].sku', s)).toBe(true)
    expect(pathResolvable('$.items[0]', s)).toBe(true)
    expect(pathResolvable('$.items', s)).toBe(true)
  })

  it('IS-6: 声明面只有深层 child 时,容器锚点仍可寻址(前缀由后端物化)', () => {
    // 深层声明的各级容器前缀是声明面的成员(spec §2.2)⇒ 容器路径靠成员命中
    const s = injectablePathSetOf([], ['$', '$.items', '$.items.sku'])
    expect(pathResolvable('$.items[0]', s)).toBe(true)        // 模板形态 $.items 命中
    expect(pathResolvable('$.items', s)).toBe(true)           // 容器锚点自身也可寻址
    expect(pathResolvable('$.items[0].nope', s)).toBe(false)  // 深层不存在的段仍判死
  })

  it('IS-7: body 面的容器前缀物化 — 与后端同两条反例(parity 锚)', () => {
    // body 半同样物化容器前缀(`bodyPathSetOf`),与后端 universe 的
    // `prefixes(body)` 同形;下列两例与后端
    // tests/test_run_injection.py::test_body_face_covers_container_prefixes_like_frontend
    // 逐一对应(此处声明面为空 = 降级态,前缀照样来自 body 半)。
    // 方向一:数组越界 —— toTemplatePath('$.tags[9]') = '$.tags' 命中前缀成员
    const arr = injectablePathSetOf(
      fieldPathsOf({ request: { body: { tags: ['a', 'b'] } } } as any), [])
    expect(pathResolvable('$.tags[9]', arr)).toBe(true)
    expect(pathResolvable('$.tags', arr)).toBe(true)       // 容器前缀本身也可寻址
    // 方向二:键含点 —— 叶子 $.a.b.c 的容器前缀含 '$.a.b'(段边界字面比)
    const dotted = injectablePathSetOf(
      fieldPathsOf({ request: { body: { a: { 'b.c': 1 } } } } as any), [])
    expect(pathResolvable('$.a.b', dotted)).toBe(true)
    // 仍判死:越界段之后又拼了一段(两形态都不在前缀面上)
    expect(pathResolvable('$.tags[9].nope', arr)).toBe(false)
  })
})
