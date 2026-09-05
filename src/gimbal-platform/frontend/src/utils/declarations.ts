/**
 * declarations.ts —— 字段状态目录(2026-09-05 spec)的前端投影单一实现。
 *
 * 与后端 app/services/field_state_resolution.py 同式对称:
 *   - resolveState 公式(§3.2):state(path) = field_states[path] ?? entry.state ?? 'form'
 *   - iterFlat 先序平铺(容器先于子孙,§2.7 次序对齐)
 *   - carry 面祖先吸收(整容器是注入单元,§4 机制依赖注)
 * 改语义双侧同步,禁止消费方各自散写。
 *
 * 本文件之上再承载 §5 渲染模型的纯算法部分:buildTree 值×结构合并树
 * (三输入:目录/意图/值)与「其他字段」区的目录外 body 残留投影
 * (深浅皆收,Type C 继任)。组件(FieldForm/Canvas)只做渲染与回写:
 * 值回写走 body,状态回写走 step.field_states —— 两通路分离(§5.4)。
 */
import type {
  DeclarationEntryView, FieldState, IOFieldBinding,
} from '@/types/plate'
import { getByPath } from './jsonpath'

// ─── 解析链(§3.2,后端 field_state_resolution.resolveState 同式)──────

export const VALID_STATES: readonly FieldState[] = ['form', 'collapse', 'carry']

function isValidState(s: unknown): s is FieldState {
  return VALID_STATES.includes(s as FieldState)
}

/**
 * 解析链单点实现:增量 → 共识默认 → form。
 * 防御(§3.4):field_states 形状不符/值不在词表 → 该条增量视同缺席
 * (读穿);entry.state 缺席或不在词表 → form(fail-closed:零注入)。
 */
export function resolveState(
  path: string,
  entryState: FieldState | null | undefined,
  fieldStates?: Record<string, string> | null,
): FieldState {
  const override = fieldStates?.[path]
  if (isValidState(override)) return override
  if (isValidState(entryState)) return entryState
  return 'form'
}

/** children 树先序平铺(容器先于子孙);防御:非数组/非对象条目跳过。 */
export function iterFlat(
  decls: DeclarationEntryView[] | undefined | null,
): DeclarationEntryView[] {
  const out: DeclarationEntryView[] = []
  const walk = (entries: DeclarationEntryView[] | undefined) => {
    for (const e of entries ?? []) {
      if (!e || typeof e !== 'object') continue
      out.push(e)
      walk(e.children)
    }
  }
  walk(decls ?? [])
  return out
}

/** 目录宇宙(§3.4 交集容忍参照):树内全部条目 path(模板形态,无下标)。 */
export function catalogPaths(
  decls: DeclarationEntryView[] | undefined | null,
): Set<string> {
  return new Set(iterFlat(decls).map((e) => e.path))
}

/**
 * carry 面(祖先吸收):解析态 == 'carry' 的条目 path 集。
 * carry 容器的子孙不单列 —— 整容器是注入单元;仅当祖先解析态非 carry
 * 时下钻(form 容器下的 carry 叶子合法收录)。值表候选面/漂移检测消费
 * 端点级形态(不传 field_states,读共识默认 —— 值表是环境级,§4)。
 */
export function carryPaths(
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates?: Record<string, string> | null,
): string[] {
  const out: string[] = []
  const walk = (entries: DeclarationEntryView[] | undefined) => {
    for (const e of entries ?? []) {
      if (!e || typeof e !== 'object' || !e.path) continue
      if (resolveState(e.path, e.state, fieldStates) === 'carry') out.push(e.path)
      else walk(e.children)
    }
  }
  walk(decls ?? [])
  return out
}

// ─── IOFieldBinding 投影(行形状;掐掉 state/children/type/assertable)──

function toFieldBinding(e: DeclarationEntryView, path: string): IOFieldBinding {
  return {
    name: e.name,
    path,
    required: e.required ?? false,
    default: e.default ?? null,
    example: e.example ?? null,
    description: e.description ?? '',
    enum: e.enum ?? null,
    ui_kind: e.ui_kind,
    source_kind: e.source_kind,
  }
}

/**
 * 请求表单面平铺投影:解析态 != carry 的条目(先序,模板路径)。
 * 匹配面/描述索引(useFieldDescriptions 按名查)消费;树渲染走
 * buildTree(值×结构合并,实例路径),勿用本函数渲染请求体。
 */
export function formBindings(
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates?: Record<string, string> | null,
): IOFieldBinding[] {
  const out: IOFieldBinding[] = []
  const walk = (entries: DeclarationEntryView[] | undefined) => {
    for (const e of entries ?? []) {
      if (!e || typeof e !== 'object' || !e.path) continue
      if (resolveState(e.path, e.state, fieldStates) === 'carry') continue
      out.push(toFieldBinding(e, e.path))
      walk(e.children)
    }
  }
  walk(decls ?? [])
  return out
}

/** 响应面单脸全量投影(§4:assertable 标记候选,state 不被读取)。 */
export function responseBindings(
  decls: DeclarationEntryView[] | undefined | null,
): IOFieldBinding[] {
  return iterFlat(decls).filter((e) => !!e.path).map((e) => toFieldBinding(e, e.path))
}

/** 断言候选面:assertable=True 条目 path 集(响应单脸 ✓ 标 / 策略候选)。 */
export function assertablePaths(
  decls: DeclarationEntryView[] | undefined | null,
): string[] {
  return iterFlat(decls).filter((e) => e.assertable && !!e.path).map((e) => e.path)
}

// ─── §5.2 buildNode 值×结构合并树(三输入:目录/意图/值)──────────────

/** 叶子节点:目录叶子 × 实例路径(数组行内含 [i])。 */
export interface FieldLeafNode {
  kind: 'leaf'
  /** 实例路径(寻址真源;数组行内含 [i],模板路径无下标) */
  path: string
  /** 模板路径(目录态;字段状态增量 keyed 于模板路径) */
  templatePath: string
  /** 解析态(form/collapse;carry 不进树) */
  state: FieldState
  /** 行渲染形状(FieldForm 叶子行/菜单消费) */
  binding: IOFieldBinding
  /** 合成行(数组标量行等无目录条目;控件按值类型推断) */
  synthetic?: boolean
}

/** 对象节点:折叠面板,子节点 = children 递归。 */
export interface FieldObjectNode {
  kind: 'object'
  path: string
  templatePath: string
  state: FieldState
  entry: DeclarationEntryView
  children: FieldTreeNode[]
}

/** 开放字典节点:object 无 children(additionalProperties 字典)→ KV 编辑器。 */
export interface FieldDictNode {
  kind: 'dict'
  path: string
  templatePath: string
  state: FieldState
  entry: DeclarationEntryView
  /** body 实有键(顺序保持);值为标量或结构,行内按值渲染 */
  entries: Array<{ key: string; value: unknown }>
}

/** 数组节点:动态行组 —— 行数跟 body、结构跟目录。 */
export interface FieldArrayNode {
  kind: 'array'
  path: string
  templatePath: string
  state: FieldState
  entry: DeclarationEntryView
  /** 每行 = 模板 children 的实例化节点组(标量模板 → 单合成叶) */
  rows: FieldTreeNode[][]
  /** 行模板(加行 = 模板实例化空壳 [len]) */
  templates: DeclarationEntryView[]
}

export type FieldTreeNode =
  | FieldLeafNode | FieldObjectNode | FieldDictNode | FieldArrayNode

/**
 * §5.2 buildNode 递归算法(纯函数):
 * - 模板路径与实例路径分离(`[i]` 只在 array 分支出现);
 * - 行数跟 body、结构跟目录(children 是唯一结构真源);
 * - carry 不进树(祖先吸收:carry 容器整棵剪除);
 * - 实例值经 getByPath 读取,仅用于数组行数与字典键枚举。
 */
function buildNode(
  entry: DeclarationEntryView,
  instancePath: string,
  body: unknown,
  fieldStates?: Record<string, string> | null,
): FieldTreeNode | null {
  const state = resolveState(entry.path, entry.state, fieldStates)
  if (state === 'carry') return null // carry 不进树(搜索语料,§5.4)
  const children = Array.isArray(entry.children) ? entry.children : []
  if (!children.length) {
    if (entry.type === 'object') {
      const v = getByPath(body, instancePath)
      const obj = v && typeof v === 'object' && !Array.isArray(v)
        ? v as Record<string, unknown>
        : {}
      return {
        kind: 'dict', path: instancePath, templatePath: entry.path,
        state, entry,
        entries: Object.entries(obj).map(([key, value]) => ({ key, value })),
      }
    }
    if (entry.type === 'array') {
      return {
        kind: 'array', path: instancePath, templatePath: entry.path,
        state, entry, templates: [],
        rows: scalarRows(instancePath, entry, state, body),
      }
    }
    return {
      kind: 'leaf', path: instancePath, templatePath: entry.path,
      state, binding: toFieldBinding(entry, instancePath),
    }
  }
  if (entry.type === 'array') {
    const value = getByPath(body, instancePath)
    const items = Array.isArray(value) ? value : []
    return {
      kind: 'array', path: instancePath, templatePath: entry.path,
      state, entry, templates: children,
      rows: items.map((_, i) =>
        children
          .map((c) => buildNode(
            c, instancePath + `[${i}]` + suffixOf(c.path, entry.path),
            body, fieldStates,
          ))
          .filter((n): n is FieldTreeNode => n !== null),
      ),
    }
  }
  // object(默认):折叠面板,子节点递归 —— 实例路径 = 容器实例路径 +
  // 子模板后缀(容器自身在数组行内时,子实例随之携带 [i])
  return {
    kind: 'object', path: instancePath, templatePath: entry.path,
    state, entry,
    children: children
      .map((c) => buildNode(
        c, instancePath + suffixOf(c.path, entry.path),
        body, fieldStates,
      ))
      .filter((n): n is FieldTreeNode => n !== null),
  }
}

/** 子模板相对容器模板的后缀($.supplier.x − $.supplier = '.x')。 */
function suffixOf(childPath: string, containerPath: string): string {
  return childPath.startsWith(containerPath)
    ? childPath.slice(containerPath.length)
    : `.${childPath}`
}

/** 无 children 模板的数组合成行(§5.3):按值类型分形 —— 标量 → 叶子;
 *  对象 → 开放字典行(KV 编辑。此前对象值落 text 输入,显示成
 *  [object Object] 且编辑会用字符串整洗行对象);数组 → 递归合成数组。
 *  templatePath 归容器模板(行内无独立声明),状态随容器解析态。 */
function scalarRows(
  instancePath: string, entry: DeclarationEntryView,
  state: FieldState, body: unknown,
): FieldTreeNode[][] {
  const value = getByPath(body, instancePath)
  const items = Array.isArray(value) ? value : []
  return items.map((item, i) => [
    synthRowNode(item, `${instancePath}[${i}]`, `${entry.name}[${i}]`, entry, state, body),
  ])
}

/** 单个合成行节点(name 携带下标,多行可辨;行内 entry 用拷贝不污染模板)。 */
function synthRowNode(
  item: unknown, path: string, name: string,
  entry: DeclarationEntryView, state: FieldState, body: unknown,
): FieldTreeNode {
  if (Array.isArray(item)) {
    const rowEntry = { ...entry, name }
    return {
      kind: 'array', path, templatePath: entry.path, state,
      entry: rowEntry, templates: [],
      rows: scalarRows(path, rowEntry, state, body),
    }
  }
  if (item !== null && typeof item === 'object') {
    return {
      kind: 'dict', path, templatePath: entry.path, state,
      entry: { ...entry, name },
      entries: Object.entries(item as Record<string, unknown>)
        .map(([key, value]) => ({ key, value })),
    }
  }
  return {
    kind: 'leaf', path, templatePath: entry.path, state,
    synthetic: true,
    binding: {
      name, path,
      required: false,
      default: null,
      example: null,
      description: '',
      enum: null,
      ui_kind: typeof item === 'number' ? 'number'
        : typeof item === 'boolean' ? 'boolean' : 'text',
      source_kind: 'independent',
    },
  }
}

/** §5.1 三输入合一:目录 + 意图(field_states)+ 值(body)→ 渲染树。 */
export function buildTree(
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates?: Record<string, string> | null,
  body?: unknown,
): FieldTreeNode[] {
  return (decls ?? [])
    .map((e) => (e && typeof e === 'object' && e.path
      ? buildNode(e, e.path, body, fieldStates) : null))
    .filter((n): n is FieldTreeNode => n !== null)
}

/**
 * 树叶平铺(匹配面):叶子/数组标量行/字典 KV 合成行 → IOFieldBinding[]。
 * Canvas 的注入只读态/请求侧策略角标匹配面消费(实例路径,含 [i])—
 * deriveDeepRows(D9)的继任:body 实例现在由树本体承载,目录外残留
 * 由 extraBodyPaths 承载,两处相加即完整匹配面。
 */
export function leafSurface(nodes: FieldTreeNode[]): IOFieldBinding[] {
  const out: IOFieldBinding[] = []
  const walk = (list: FieldTreeNode[]) => {
    for (const n of list) {
      if (n.kind === 'leaf') out.push(n.binding)
      else if (n.kind === 'object') walk(n.children)
      else if (n.kind === 'array') n.rows.forEach((row) => walk(row))
      else if (n.kind === 'dict') {
        n.entries.forEach(({ key }) => out.push({
          name: key,
          path: `${n.path}.${key}`,
          required: false, default: null, example: null,
          description: '', enum: null,
          ui_kind: 'text', source_kind: 'independent',
        }))
      }
    }
  }
  walk(nodes)
  return out
}

/** 容器节点 → 合成载体(FieldForm.nodeBinding 同形;path 用实例路径)。 */
function containerBinding(
  n: FieldObjectNode | FieldArrayNode | FieldDictNode,
): IOFieldBinding {
  return {
    name: n.entry.name,
    path: n.path,
    required: n.entry.required,
    default: n.entry.default ?? null,
    example: n.entry.example ?? null,
    description: n.entry.description,
    enum: n.entry.enum ?? null,
    ui_kind: n.entry.ui_kind,
    source_kind: n.entry.source_kind,
  }
}

/**
 * 树容器平摊(匹配面,2026-09-05 注入粒度 P6):object/array/dict 节点
 * → IOFieldBinding[](实例路径,行内嵌套容器如 $.container[0].box_no、
 * 无模板数组的合成字典行 $.misc[0] 亦收)。整容器 assign(target 命中
 * $.request_body<容器实例路径>)与叶子同式匹配 — P3 容器快捷策略的
 * 提示态/角标继任(此前匹配面只含叶子,整容器注入零提示)。根容器
 * ('$')排除:快捷菜单即排除(P3,根无 rel 路径,target 派生畸形)。
 */
export function containerSurface(nodes: FieldTreeNode[]): IOFieldBinding[] {
  const out: IOFieldBinding[] = []
  const walk = (list: FieldTreeNode[]) => {
    for (const n of list) {
      if (n.kind === 'object') {
        if (n.path !== '$') out.push(containerBinding(n))
        walk(n.children)
      } else if (n.kind === 'array') {
        if (n.path !== '$') out.push(containerBinding(n))
        n.rows.forEach((row) => walk(row))
      } else if (n.kind === 'dict' && n.path !== '$') {
        out.push(containerBinding(n))
      }
    }
  }
  walk(nodes)
  return out
}

// ─── 「其他字段」区(§4:目录外 body 残留,深浅皆收,Type C 继任)──────

export interface ExtraBodyRow {
  /** 实例路径($.-形态;深层残留含 . 与 [i]) */
  path: string
  /** 顶层结构残留(JSON 整体编辑);深层残留为叶子行 */
  top: boolean
}

/** 实例路径 → 模板形态(剥 [i] 下标:$.a[0].b → $.a.b)。 */
function toTemplate(path: string): string {
  return path.replace(/\[\d+\]/g, '')
}

/**
 * 目录外 body 残留投影:body(深浅皆收)中不被目录覆盖的键。
 * 覆盖判定:模板化 path ∈ 目录宇宙;声明了 children 的已覆盖容器
 * 只渲染声明面,继续下钻找内部残留叶子(E1);无 children 声明的
 * 结构容器(开放字典 / 无模板数组合成行)在树内自渲染全部内容,
 * 子树不再重复成行(防双重展示)。carry 根下整棵剪除(容器值归
 * 值表,D9 排除面继任)。未覆盖节点整块成行:顶层平铺键维持旧
 * extras 语义,结构键 JSON 整行(top),标量叶子行 ——
 * deriveDeepRows 的深浅皆收继任。
 */
export function extraBodyPaths(
  body: unknown,
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates?: Record<string, string> | null,
): ExtraBodyRow[] {
  if (!body || typeof body !== 'object') return []
  const universe = catalogPaths(decls)
  const carry = new Set(carryPaths(decls, fieldStates))
  // 自渲染容器:无 children 声明的结构条目(dict KV / 合成行承载全文)
  const selfRendered = new Set(
    iterFlat(decls).filter((e) =>
      (e.type === 'object' || e.type === 'array')
      && !(Array.isArray(e.children) && e.children.length),
    ).map((e) => e.path),
  )
  const rows: ExtraBodyRow[] = []
  const full = (rel: string) => (rel.startsWith('[') ? `$${rel}` : `$.${rel}`)
  /** 前缀段是否落 carry 容器(模板化前缀逐段收敛到 '.' 边界;$ = 整包)。 */
  const underCarry = (path: string): boolean => {
    let t = toTemplate(path)
    while (t.includes('.')) {
      t = t.slice(0, t.lastIndexOf('.'))
      if (carry.has(t)) return true
    }
    return carry.has('$')
  }
  const walk = (val: unknown, rel: string) => {
    const isArr = Array.isArray(val)
    const children: Array<[string, unknown]> = isArr
      ? (val as unknown[]).map((x, i) => [String(i), x])
      : Object.entries(val as Record<string, unknown>)
    for (const [k, v] of children) {
      const childRel = isArr ? `${rel}[${k}]` : rel ? `${rel}.${k}` : k
      const p = full(childRel)
      if (universe.has(toTemplate(p)) || underCarry(p)) {
        // 已覆盖(或 carry 吸收):声明了 children 的结构容器只渲染
        // 声明面,下钻找内部残留叶子;自渲染容器子树不重复成行;
        // 已覆盖叶子/标量由渲染树本体承载,不成行
        if (v !== null && typeof v === 'object'
          && !selfRendered.has(toTemplate(p))) walk(v, childRel)
        continue
      }
      rows.push({ path: p, top: v !== null && typeof v === 'object' })
    }
  }
  walk(body, '')
  return rows
}

/**
 * 目录外残留的匹配面形状(Canvas 注入只读态/策略角标消费):
 * extraBodyPaths 行 → IOFieldBinding 合成(name = 相对路径安全形态,
 * `supplier[1].x` → `supplier_1_x`,旧 deriveDeepRows 同款;ui_kind 按
 * 值类型推断)。与 leafSurface 相加即完整请求匹配面。
 */
export function extraSurfaceBindings(
  body: unknown,
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates?: Record<string, string> | null,
): IOFieldBinding[] {
  return extraBodyPaths(body, decls, fieldStates).map((r) => {
    const rel = r.path.replace(/^\$\.?/, '')
    const v = getByPath(body, rel)
    return {
      name: rel.replace(/\[(\d+)\]/g, '_$1').replace(/\./g, '_'),
      path: r.path,
      ui_kind: typeof v === 'number' ? 'number'
        : typeof v === 'boolean' ? 'boolean' : 'text',
      source_kind: 'independent' as const,
      required: false,
      description: '',
      example: null,
      default: null,
      enum: null,
    }
  })
}

/**
 * 新建步骤初始 body 预填面(§4 field_defaults 消费的前端侧):
 * 解析态 != carry 的浅层叶子 default/example —— 容器(带 children)
 * 与深层/数组子孙不落库(D7 语义保持:深层默认只展示,防挡 carry
 * 整包注入;模板路径落数组子孙会物化 dict 顶替 array 的错误形态)。
 */
export function prefillBindings(
  decls: DeclarationEntryView[] | undefined | null,
): IOFieldBinding[] {
  const out: IOFieldBinding[] = []
  for (const e of decls ?? []) {
    if (!e || typeof e !== 'object' || !e.path) continue
    if (Array.isArray(e.children) && e.children.length) continue // 容器不预填
    if (resolveState(e.path, e.state, undefined) === 'carry') continue
    const rel = e.path.replace(/^\$\.?/, '')
    if (/[.\[]/.test(rel)) continue // 深层/数组子孙不落库(D7)
    out.push(toFieldBinding(e, e.path))
  }
  return out
}
