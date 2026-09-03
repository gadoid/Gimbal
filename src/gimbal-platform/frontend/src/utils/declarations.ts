/**
 * declarations.ts —— plate /full 统一声明清单的前端投影工具。
 *
 * plate 侧 declarations 为唯一承重存储(旧 fields/carry/assertable_fields
 * 线上键已清除);IOFieldBinding 仍是字段元信息的 UI 形状(FieldForm/
 * Catalog 字段表),本文件把声明条目按通道投影回该形状 —— 前端唯一的
 * 投影入口,各消费点(Canvas/Catalog/useFieldDescriptions)不再自行展开。
 */
import type { DeclarationEntryView, IOFieldBinding } from '@/types/plate'

/**
 * D12 祖先判定(字符串前缀,归一化形态下可靠):
 * `$.a` 是 `$.a.b` / `$.a[0].c` 的祖先;`$.ab` 不是 `$.a` 的后代
 * (前缀后必须紧跟 `.` 或 `[`,不吃假前缀)。
 */
function isAncestor(anc: string, desc: string): boolean {
  if (anc === desc || !desc.startsWith(anc)) return false
  const next = desc[anc.length]
  return next === '.' || next === '['
}

/**
 * D12:最长已声明祖先(无 → null);parentChannel 随源条目。
 * 扫描跨通道 — carry 容器是 binding 深字段的合法上级(值表打底语义)。
 * O(n²),声明清单量级无忧。
 */
function deriveParent(
  e: DeclarationEntryView,
  all: DeclarationEntryView[],
): { parentPath: string | null; parentChannel: DeclarationEntryView['channel'] | null } {
  let best: DeclarationEntryView | null = null
  for (const o of all) {
    if (o.path !== e.path && isAncestor(o.path, e.path) &&
        (best === null || o.path.length > best.path.length)) best = o
  }
  return best
    ? { parentPath: best.path, parentChannel: best.channel }
    : { parentPath: null, parentChannel: null }
}

/** 声明条目 → IOFieldBinding 形状(掐掉 channel/type/assertable 三个声明轴,派生 parent 投影) */
function toFieldBinding(e: DeclarationEntryView, all: DeclarationEntryView[]): IOFieldBinding {
  const { parentPath, parentChannel } = deriveParent(e, all)
  return {
    name: e.name,
    path: e.path,
    required: e.required,
    default: e.default ?? null,
    example: e.example ?? null,
    description: e.description,
    enum: e.enum ?? null,
    ui_kind: e.ui_kind,
    source_kind: e.source_kind,
    parentPath,
    parentChannel,
  }
}

/** 表单/展示字段面:binding(请求)或 view_only(响应)通道条目按序投影(parent 派生吃全量清单) */
export function channelFields(
  decls: DeclarationEntryView[] | undefined | null,
  channel: 'binding' | 'view_only',
): IOFieldBinding[] {
  const all = decls ?? []
  return all.filter((e) => e.channel === channel).map((e) => toFieldBinding(e, all))
}

/** 传递字段面:carry 通道条目的 path 集(carry 徽章 / Type C 过滤用) */
export function carryPaths(decls: DeclarationEntryView[] | undefined | null): string[] {
  return (decls ?? []).filter((e) => e.channel === 'carry').map((e) => e.path)
}

/** 断言候选面:view_only 且 assertable=True 的 paths(响应契约 ✓ 标 / 策略候选) */
export function assertablePaths(decls: DeclarationEntryView[] | undefined | null): string[] {
  return (decls ?? []).filter((e) => e.channel === 'view_only' && e.assertable).map((e) => e.path)
}

/**
 * D9 深层派生行(body 纯投影):body 容器根下未被 binding 精确覆盖的深层
 * 叶子,经 FIELD/INDEX walk 合成 IOFieldBinding — 不新增存储,读写走
 * FieldForm 既有 setValue/getValue(深层清空自动 D8 剪枝)。
 *
 * 单一真源:FieldForm 渲染与 Canvas 匹配面(requestInjected 只读态 /
 * 请求侧策略角标)共用本函数 — 派生行 name 键控两侧同源,防键漂移。
 *
 * 排除面:① 任一 binding path 精确覆盖的叶子(已是声明行);② carry 根下
 * 叶子(容器值归值表,D9 明文);③ 顶层平铺键(归「其他字段」区,互不侵占)。
 * name=相对路径安全形态(`supplier[1].x` → `supplier_1_x`,下标 [i]→_i、
 * 点 .→_;与声明 name 撞车加 _2/_3 后缀),path=完整 $. 路径(角标/assign
 * target 派生);ui_kind 按 typeof 值推断(number/boolean,其余含 null→text)。
 *
 * 根 list body(Task 10):body 直接是 JSON 数组时同样进 walk(rel 从
 * `[i]` 起);完整路径拼接按 rel 形态分流 — `[` 开头 → `$`+rel 直拼
 * (无点,`$[1].sku`),否则 `$.`+rel。根级标量元素(`$[0]`)rel 含 `[`
 * 同成派生行(extras 区不吃数组根,无数字键垃圾行)。carry 根 `''`
 * (整包 `$` 的根键)命中 → 数组根整包跳过(容器值归值表)。
 */
export function deriveDeepRows(
  body: unknown,
  bindings: Array<Pick<IOFieldBinding, 'name' | 'path'>>,
  carryRoots: string[],
): IOFieldBinding[] {
  if (!body || typeof body !== 'object') return []
  const bodyArr = Array.isArray(body) ? (body as unknown[]) : null
  const covered = new Set(bindings.map((b) => b.path))
  const carry = new Set(carryRoots)
  const taken = new Set(bindings.map((b) => b.name))
  const rows: IOFieldBinding[] = []
  // 完整路径拼接:rel 以 '[' 开头(根 list)→ $+rel 直拼;否则 $.+rel
  const full = (rel: string) => (rel.startsWith('[') ? `$${rel}` : `$.${rel}`)
  const leaf = (rel: string, v: unknown) => {
    if (covered.has(full(rel))) return
    const base = rel.replace(/\[(\d+)\]/g, '_$1').replace(/\./g, '_')
    let name = base
    let n = 2
    while (taken.has(name)) name = `${base}_${n++}`
    taken.add(name)
    rows.push({
      name,
      path: full(rel),
      ui_kind: typeof v === 'number' ? 'number' : typeof v === 'boolean' ? 'boolean' : 'text',
      source_kind: 'independent',
      required: false,
      description: '',
      example: null,
      default: null,
      enum: null,
    })
  }
  const walk = (val: unknown, rel: string) => {
    if (val === null || typeof val !== 'object') {
      // 深层叶子才成行(rel 含 `.`/`[`);顶层平铺叶子归「其他字段」区
      if (/[.\[]/.test(rel)) leaf(rel, val)
      return
    }
    if (Array.isArray(val)) val.forEach((x, i) => walk(x, `${rel}[${i}]`))
    else for (const [k, v] of Object.entries(val)) walk(v, `${rel}.${k}`)
  }
  if (bodyArr) {
    if (carry.has('')) return [] // 整包 carry($ → 根键 '')→ 数组根整包跳过
    bodyArr.forEach((x, i) => walk(x, `[${i}]`))
    return rows
  }
  for (const [k, v] of Object.entries(body as Record<string, unknown>)) {
    if (carry.has(k)) continue
    walk(v, k)
  }
  return rows
}
