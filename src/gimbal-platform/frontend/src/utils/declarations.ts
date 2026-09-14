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
  DeclarationEntryView, EndpointFullView, FieldState, IOFieldBinding,
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

/** 路径可用性**唯一定义**(spec 架构收敛 §2.3):`/full` 是不可信来源,
 *  真值但非字符串的 path(如 `path: 7`)会让下游 `toTemplatePath` 抛
 *  `path.replace is not a function` —— 在**边界**判一次,消费方不再各自守卫
 *  (与后端 `field_state_resolution.composite_states` 的「守卫一次、下游继承」同款)。 */
export function hasUsablePath(e: DeclarationEntryView | null | undefined): boolean {
  return typeof (e as { path?: unknown } | null | undefined)?.path === 'string'
    && (e as unknown as { path: string }).path !== ''
}

/** children 树先序平铺(**只吐可用路径的条目**);防御:非数组/非对象跳过。
 *  ⚠ 路径不可用的条目**自身剔除但仍遍历其 children** —— 容器条目缺 path 时
 *  若整棵剪掉,其子孙会从树里消失(那是语义丢失,不是消毒)。 */
export function iterFlat(
  decls: DeclarationEntryView[] | undefined | null,
): DeclarationEntryView[] {
  const out: DeclarationEntryView[] = []
  const walk = (entries: DeclarationEntryView[] | undefined) => {
    for (const e of entries ?? []) {
      if (!e || typeof e !== 'object') continue
      if (hasUsablePath(e)) out.push(e)
      walk(e.children)
    }
  }
  walk(decls ?? [])
  return out
}

/**
 * 声明树**入口消毒**(纯函数,不改入参):路径不可用条目(判据 = :func:`hasUsablePath`)
 * **自身剔除、children 提升**到原位置(数组且非空则拼接;非数组则丢弃)——
 * 与 `iterFlat` 逐字同纪律,**绝不整棵剪枝**(容器缺 path 时整棵剪掉会让子孙
 * 从树里消失 = 语义丢失)。
 *
 * 为什么必须在**边界一次**做:`/full` 是不可信来源,真值非串的 path(如 `path: 7`)
 * 会让画布递归 `buildNode → suffixOf` 的 `childPath.startsWith(...)` 在**渲染期
 * 硬抛**(白屏)。逐处点修只会让守卫不断从下一个消费方冒出来 —— 消毒在
 * `getFullEndpoint` **出口**与共享缓存**入口**各做一次(幂等)。
 *
 * **保证的范围(只此一条,勿外推)**:返回树中**任意深度**都不存在
 * `hasUsablePath` 为假的条目 —— 「按构造干净的」指的只是**路径可用性**。
 * **不保证 `children` 的形状**:非数组 children(如 `{"0": {...}}`)在**保留下来
 * 的**条目上原样放行,而 `iterFlat` / `formBindings` 的 `for (const e of entries ?? [])`
 * 对普通对象会硬抛(`TypeError: entries is not iterable`);条目**自身被剔除**时
 * (路径不可用)这一条整份不进返回树,其畸形 children 只能随之消失 —— 那种情形
 * 不是「放行」。该形状是否归一是**待定取舍**(静默丢弃畸形 children = 字段树悄悄
 * 变瘦 vs 保持硬抛 = 白屏但响亮),未在本轮处理 —— 消费方不得据此声称
 * 「声明树已全形式干净」。
 *
 * 递归下钻到**可用条目**的 children(画布递归只认 `entry.children`)。
 * 某层未发生改动时**保留原引用**(条目对象 / 整份 `/full` 原样返回),
 * 对干净入参零扰动 —— 现有身份与浅比较语义不变。
 */
export function sanitizeDeclarations(
  decls: DeclarationEntryView[] | undefined | null,
): DeclarationEntryView[] {
  const out: DeclarationEntryView[] = []
  for (const e of decls ?? []) {
    if (!e || typeof e !== 'object') continue
    const kids = (e as { children?: unknown }).children
    const cleaned = Array.isArray(kids)
      ? sanitizeDeclarations(kids as DeclarationEntryView[])
      : undefined
    if (!hasUsablePath(e)) {
      // 自身不可用:剔除自身,children 提升到原位置(非数组/空 → 丢弃)
      if (cleaned?.length) out.push(...cleaned)
      continue
    }
    if (!Array.isArray(kids) || isSameRefs(kids, cleaned!)) { out.push(e); continue }
    out.push({ ...e, children: cleaned })
  }
  return out
}

/** cleaned 与 raw 逐位同一引用(消毒对该层无改动)⇒ 保留原条目对象。 */
function isSameRefs(raw: unknown[], cleaned: DeclarationEntryView[]): boolean {
  return cleaned.length === raw.length && cleaned.every((c, i) => c === raw[i])
}

/**
 * `/full` 出口消毒:**request** 与**每个 response** 的 declarations 各一次
 * (裁定 C9 —— 半边留着就是同一形状),外加 **`declared_surface` 的形态归一**
 * (见 :func:`sanitizeDeclaredSurface`)。响应声明今天经 `iterFlat` 系投影
 * (`assertablePaths` / `responseBindings`)不抛,但同一个 `path: 7` 只要
 * 将来换个消费方就会重开一族;在出口一次关死。
 * 保证范围同 :func:`sanitizeDeclarations`(仅路径可用性;`children` 形状未归一)。
 * 无改动 → 原对象(身份保持不变)。
 */
export function sanitizeEndpointFull(full: EndpointFullView): EndpointFullView {
  const request = sanitizeRequestSpec(full?.request)
  const responses = sanitizeResponses(full?.responses)
  const declared = sanitizeDeclaredSurface(full?.declared_surface)
  if (request === full?.request && responses === full?.responses
      && declared === full?.declared_surface) {
    return full
  }
  const out = { ...full, request, responses }
  // 键只在它本身被归一时才重挂:缺席与 null 都原样(消费侧同判降级,不动键 = 不改 wire 形状)
  if (declared !== full?.declared_surface) out.declared_surface = declared
  return out
}

/**
 * `declared_surface` 归一 —— 判定面把这个字段直接 `for...of` 进判定集
 * (`injectablePathSetOf`),故它必须是 `string[] | null`,否则不可信来源的
 * 失效是**静默**的:字符串会被逐字符并成 `'$'` / `'.'` / `'a'` 这类垃圾成员,
 * 路径判定从此悄悄错判而无一处报错;数字等非可迭代值更是渲染期硬抛。
 * (与 `sanitizeDeclarations` 同纪律:在**边界一次**挡掉,别让消费方各自防。)
 *
 * - 数组 → 只留字符串元素(非字符串元素丢弃);
 * - `[]` → 保持 `[]`:真无声明是合法形态,不是降级(§5);
 * - `null` → `null`(降级);非数组的真值 → `null`(降级从严);
 * - 键缺席 → 原样不动(缺省即降级,消费侧同判;不动键 = 身份保持);
 * - 无改动 → 返回**原数组**(身份不变)。
 */
function sanitizeDeclaredSurface(raw: unknown): string[] | null | undefined {
  if (raw === undefined || raw === null) return raw
  if (!Array.isArray(raw)) return null
  const kept = raw.filter((p): p is string => typeof p === 'string')
  return kept.length === raw.length ? (raw as string[]) : kept
}

/** RequestSpecView 的 declarations 消毒(无改动 → 原对象)。 */
function sanitizeRequestSpec(
  spec: EndpointFullView['request'],
): EndpointFullView['request'] {
  const decls = spec?.declarations
  if (!Array.isArray(decls)) return spec
  const clean = sanitizeDeclarations(decls)
  if (isSameRefs(decls, clean)) return spec
  return { ...spec!, declarations: clean }
}

/** responses 逐状态码消毒(无改动 → 原对象)。 */
function sanitizeResponses(
  responses: EndpointFullView['responses'],
): EndpointFullView['responses'] {
  if (!responses || typeof responses !== 'object') return responses
  let changed = false
  const out: EndpointFullView['responses'] = {}
  for (const [status, spec] of Object.entries(responses)) {
    const decls = spec?.declarations
    const clean = Array.isArray(decls) ? sanitizeDeclarations(decls) : undefined
    if (clean && !isSameRefs(decls, clean)) {
      out[status] = { ...spec, declarations: clean }
      changed = true
    } else {
      out[status] = spec
    }
  }
  return changed ? out : responses
}

/** 目录宇宙(§3.4 交集容忍参照):树内全部条目 path(模板形态,无下标)。
 *  `iterFlat` 已按 :func:`hasUsablePath` 在边界消毒 ⇒ 此处零守卫:
 *  真值非串的 path(如 `path: 7`)根本不会进集合,消费侧的
 *  `toTemplatePath`(`path.replace(...)`)不会再收到它。 */
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
      if (!hasUsablePath(e)) continue
      if (resolveState(e.path, e.state, fieldStates) === 'carry') out.push(e.path)
      else walk(e.children)
    }
  }
  walk(decls ?? [])
  return out
}

// ─── 字段找回搜索 + 级联增量(2026-09-07 spec §2)──────────────────────

/** 搜索语料行:全量目录条目(含 carry 与容器)+ 解析态快照(§2.1)。 */
export interface FieldSearchRow {
  path: string
  name: string
  description: string
  type: string
  /** 解析态(resolveState;搜索行徽标用) */
  resolved: FieldState
  /** 有合法显式增量(FieldStateSelect ↺ 重置语义直连) */
  overlay: boolean
  /** 祖先 name 链(» 分隔;顶层为空) */
  breadcrumb: string
}

/**
 * 搜索语料 = iterFlat 全量(children 先序,**不按状态剪** —— carry 正是
 * 搜索语料,09-05 §5.4);容器条目在列(可整树切面)。行携带解析态与
 * overlay 标记,搜索框只做定位与状态上抛,不做添加语义(§2.2)。
 */
export function searchCorpus(
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates?: Record<string, string> | null,
): FieldSearchRow[] {
  const out: FieldSearchRow[] = []
  const walk = (
    entries: DeclarationEntryView[] | undefined,
    ancestors: DeclarationEntryView[],
  ) => {
    for (const e of entries ?? []) {
      if (!hasUsablePath(e)) continue
      out.push({
        path: e.path,
        name: e.name,
        description: e.description ?? '',
        type: e.type ?? 'string',
        resolved: resolveState(e.path, e.state, fieldStates),
        overlay: isValidState(fieldStates?.[e.path]),
        breadcrumb: ancestors.map((a) => a.name).join(' › '),
      })
      walk(e.children, [...ancestors, e])
    }
  }
  walk(decls ?? [], [])
  return out
}

/**
 * 级联增量(§2.3,批量单事务):对 path 切 target 应合并的增量集。
 *
 * - surface(target=form/collapse):path 落 target + 每个**解析态 carry**
 *   的祖先容器落 collapse(不拉起则子树在 buildNode 剪除,切换不可见;
 *   collapse = 最小侵入布局)。子孙增量不动(collapse 容器下局部
 *   carry 合法,已表达意图保留);
 * - sink(target=carry):path 落 carry + 每个**解析态非 carry** 的子孙
 *   压 carry(§3.5 tree_inconsistency 不变式:carry 容器 ⇒ 子孙必 carry);
 * - 同值仍写显式增量(↺ 可回;显式覆盖是漂移保护凭据,§3.3);
 * - 目录外 path / 词表外 target → 空对象(防御,不上抛)。
 *
 * 返回值是"待合并批",由 Canvas 乐观合并 + 整批校验 + 失败整批回滚
 * (§2.4);行尾下拉与搜索行共用此通路(零分叉)。
 */
export function cascadeIncrements(
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates: Record<string, string> | null | undefined,
  path: string,
  target: FieldState,
): Record<string, FieldState> {
  const out: Record<string, FieldState> = {}
  if (!isValidState(target)) return out
  // 定位条目并收集祖先链(先序深搜;目录外 path → 空批)
  const locate = (
    entries: DeclarationEntryView[] | undefined,
  ): { entry: DeclarationEntryView; ancestors: DeclarationEntryView[] } | null => {
    for (const e of entries ?? []) {
      if (!hasUsablePath(e)) continue
      if (e.path === path) return { entry: e, ancestors: [] }
      const deep = locate(e.children)
      if (deep) return { entry: deep.entry, ancestors: [e, ...deep.ancestors] }
    }
    return null
  }
  const hit = locate(decls ?? [])
  if (!hit) return out
  const { entry, ancestors } = hit
  out[path] = target
  if (target === 'carry') {
    // sink:整树压平(解析态判,默认 form 与显式 form 增量都压)
    const sink = (entries: DeclarationEntryView[] | undefined) => {
      for (const e of entries ?? []) {
        if (!hasUsablePath(e)) continue
        if (resolveState(e.path, e.state, fieldStates) !== 'carry') {
          out[e.path] = 'carry'
        }
        sink(e.children)
      }
    }
    sink(entry.children)
  } else {
    // surface:拉起 carry 祖先(显式 carry 增量同被覆写 — 最新意图胜)
    for (const a of ancestors) {
      if (resolveState(a.path, a.state, fieldStates) === 'carry') {
        out[a.path] = 'collapse'
      }
    }
  }
  return out
}

// ─── value_source 分组(2026-09-07 spec §3.2/§7.3)─────────────────────

/** value_source 绑定分组:group 是渲染层视角(拆组不拆查询,§7.3)。 */
export interface ValueSourceGroup {
  group: string
  view: string
  fields: Array<{ path: string; name: string; column: string }>
}

/**
 * 目录内 value_source 绑定分组(iterFlat 先序扫描,含 children 深层):
 * - group = value_source.group || value_source.view(缺省组 = view;
 *   同 view 双角色靠显式 group 拆组,§3.2 反例);
 * - column 只透传显式列名(空串 = 消费方按投影行首键补 label 列 —
 *   Canvas 职责,§7.3);
 * - 两组同 view 各自打开选择器:后端 L1/L2 天然共享,前端不复用结果、
 *   不跨组覆写。
 */
export function groupValueSources(
  decls: DeclarationEntryView[] | undefined | null,
): ValueSourceGroup[] {
  const out: ValueSourceGroup[] = []
  const byGroup = new Map<string, ValueSourceGroup>()
  for (const e of iterFlat(decls)) {
    if (!hasUsablePath(e)) continue
    const vs = e.value_source
    if (!vs || !vs.view) continue
    const group = vs.group || vs.view
    let g = byGroup.get(group)
    if (!g) {
      g = { group, view: vs.view, fields: [] }
      byGroup.set(group, g)
      out.push(g)
    }
    g.fields.push({ path: e.path, name: e.name, column: vs.column || '' })
  }
  return out
}

// ─── IOFieldBinding 投影(行形状;掐掉 state/children/assertable;type/value_source 透传)──

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
    type: e.type ?? null,
    value_source: e.value_source ?? null,
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
      if (!hasUsablePath(e)) continue
      if (resolveState(e.path, e.state, fieldStates) === 'carry') continue
      out.push(toFieldBinding(e, e.path))
      walk(e.children)
    }
  }
  walk(decls ?? [])
  return out
}

/** 响应面单脸全量投影(§4:assertable 标记候选,state 不被读取)。
 *  迭代源 `iterFlat` 已消毒 ⇒ 零二次守卫。 */
export function responseBindings(
  decls: DeclarationEntryView[] | undefined | null,
): IOFieldBinding[] {
  return iterFlat(decls).map((e) => toFieldBinding(e, e.path))
}

/** 断言候选面:assertable=True 条目 path 集(响应单脸 ✓ 标 / 策略候选)。
 *  路径可用性由迭代源 `iterFlat`(§2.3 唯一定义)保证 —— `/full` 的
 *  `responses.200.declarations` 是同一个不可信来源,而消费方
 *  `AssertionRegistryEditor` 的 `targetCandidates`(**渲染期 computed**)
 *  对产出 `.map(toScratchPath)`(后者 `platePath.startsWith(...)`)——
 *  真值非串的 path 在此已不存在,无需再写第二份 `typeof === 'string'`。 */
export function assertablePaths(
  decls: DeclarationEntryView[] | undefined | null,
): string[] {
  return iterFlat(decls)
    .filter((e) => e.assertable)
    .map((e) => e.path)
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
      value_source: entry.value_source ?? null,
    },
  }
}

/** §5.1 三输入合一:目录 + 意图(field_states)+ 值(body)→ 渲染树。
 *  顶层路径可用性走 :func:`hasUsablePath` 唯一定义(§2.3):不可用条目
 *  **自身剔除、其 children 提升为顶层节点**(与 `iterFlat` 同纪律)——
 *  直接整棵丢弃会让子孙从树里消失(语义丢失),而放行会让 `templatePath`
 *  变成真值非串(如 `7`),污染下游按模板路径的键宇宙。 */
export function buildTree(
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates?: Record<string, string> | null,
  body?: unknown,
): FieldTreeNode[] {
  const out: FieldTreeNode[] = []
  const walk = (entries: DeclarationEntryView[] | undefined) => {
    for (const e of entries ?? []) {
      if (!e || typeof e !== 'object') continue
      if (!hasUsablePath(e)) { walk(e.children); continue }
      const node = buildNode(e, e.path, body, fieldStates)
      if (node) out.push(node)
    }
  }
  walk(decls ?? [])
  return out
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
          value_source: null,
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
    value_source: n.entry.value_source ?? null,
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

// ─── 响应契约树(P7 渲染一致性,§2.6 响应面无视 state)────────────────

/**
 * formFace:响应面无视 state(spec §2.6)— 全树翻 form(深拷贝,不碰
 * 目录本体)。buildNode 会剪 carry 叶子/容器,契约展示不吃这套语义:
 * 响应契约是"接口会回什么"的全量参考,carry/collapse 是请求侧编排意图。
 */
function formFace(e: DeclarationEntryView): DeclarationEntryView {
  return {
    ...e, state: 'form',
    children: Array.isArray(e.children) ? e.children.map(formFace) : e.children,
  }
}

/**
 * 响应契约树(P7):目录 → 只读模板树,与请求侧 buildTree 同构渲染
 * (FieldForm 树模式复用,容器头角标/☰ 菜单白拿)。与 buildTree 的差异:
 * - 无 body 可跟(响应值运行期才有)→ 数组容器渲染**一行模板集**,
 *   行内路径保持模板态(无 [i])— 与 responseBindings(iterFlat 模板
 *   路径)键宇宙一致,角标/断言候选匹配面零漂移;
 * - 标量数组/开放字典无模板可实例化 → 按 example 合成行/KV(契约
 *   参考值,getValue 走 binding.example 通路,无需 body);
 * - state 全树 form(§2.6):carry 不剪、collapse 不折,契约常展开。
 * 值展示:FieldForm 以 body=null 渲染 → getValue 回落 default/example。
 */
export function contractTree(
  decls: DeclarationEntryView[] | null | undefined,
): FieldTreeNode[] {
  const tree = buildTree((decls ?? []).map(formFace), undefined, undefined)
  fillContractRows(tree)
  return tree
}

/** 契约行填充:空数组容器 → 一行模板集(模板态路径);无模板数组/
 *  开放字典 → 按 example 合成。递归下钻,行内嵌套数组同式填充。 */
function fillContractRows(nodes: FieldTreeNode[]): void {
  for (const n of nodes) {
    if (n.kind === 'object') {
      fillContractRows(n.children)
    } else if (n.kind === 'array') {
      if (!n.rows.length && n.templates.length) {
        n.rows = [
          n.templates
            .map((c) => buildNode(
              formFace(c), n.path + suffixOf(c.path, n.templatePath), undefined, undefined,
            ))
            .filter((rn): rn is FieldTreeNode => rn !== null),
        ]
      } else if (
        !n.rows.length && Array.isArray(n.entry.example)
      ) {
        n.rows = n.entry.example.map((v, i) => [
          synthRowNode(v, `${n.path}[${i}]`, `${n.entry.name}[${i}]`, n.entry, 'form', undefined),
        ])
      }
      n.rows.forEach((row) => fillContractRows(row))
    } else if (n.kind === 'dict') {
      const ex = n.entry.example
      if (!n.entries.length && ex !== null && typeof ex === 'object' && !Array.isArray(ex)) {
        n.entries = Object.entries(ex as Record<string, unknown>).map(([key, value]) => ({ key, value }))
      }
    }
  }
}

// ─── 「其他字段」区(§4:目录外 body 残留,深浅皆收,Type C 继任)──────

export interface ExtraBodyRow {
  /** 实例路径($.-形态;深层残留含 . 与 [i]) */
  path: string
  /** 顶层结构残留(JSON 整体编辑);深层残留为叶子行 */
  top: boolean
}

/** 实例路径 → 模板形态(剥 [i] 下标:$.a[0].b → $.a.b)。导出供
 *  Canvas 扇出组匹配消费(叶子绑定携带实例路径,目录/分组键是模板)。 */
export function toTemplatePath(path: string): string {
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
    let t = toTemplatePath(path)
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
      if (universe.has(toTemplatePath(p)) || underCarry(p)) {
        // 已覆盖(或 carry 吸收):声明了 children 的结构容器只渲染
        // 声明面,下钻找内部残留叶子;自渲染容器子树不重复成行;
        // 已覆盖叶子/标量由渲染树本体承载,不成行
        if (v !== null && typeof v === 'object'
          && !selfRendered.has(toTemplatePath(p))) walk(v, childRel)
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
      value_source: null,
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
    if (!hasUsablePath(e)) continue
    if (Array.isArray(e.children) && e.children.length) continue // 容器不预填
    if (resolveState(e.path, e.state, undefined) === 'carry') continue
    const rel = e.path.replace(/^\$\.?/, '')
    if (/[.\[]/.test(rel)) continue // 深层/数组子孙不落库(D7)
    out.push(toFieldBinding(e, e.path))
  }
  return out
}

// ─── 目录外字段提升(2026-09-14 spec §4.1/§4.2)───────────────────────

/** 条目树全 path 集(含 children 深层)— Canvas 的 noCarry 门禁集合。 */
export function entryPaths(
  entries: DeclarationEntryView[] | undefined | null,
): Set<string> {
  const out = new Set<string>()
  const walk = (es: DeclarationEntryView[] | undefined) => {
    for (const e of es ?? []) {
      if (!hasUsablePath(e)) continue
      out.add(e.path)
      walk(e.children)
    }
  }
  walk(entries ?? [])
  return out
}

/** 合成条目基座(§4.2:required=false/描述空/independent;state 固定
 *  'form' —— 真实意图在 field_states 增量里,resolveState 链正常解析)。 */
function mkPromotedEntry(
  path: string, name: string,
  type: string, ui: DeclarationEntryView['ui_kind'],
): DeclarationEntryView {
  return {
    name, path, state: 'form', type,
    required: false, default: null, example: null,
    description: '', enum: null,
    ui_kind: ui, source_kind: 'independent', value_source: null,
    assertable: false,
  }
}

/**
 * 提升条目合成(spec §4.2):field_states 中值 ∈ {form, collapse} 且
 * 目录外的 path(模板化;精确与祖先/子孙重叠皆让位目录,§9)→ 合成
 * DeclarationEntryView 树。结构折叠:候选按**顶层段**分组 —— 顶层
 * 候选即根;深层候选挂合成父壳(壳链沿 path 逐段合成,同根多候选
 * 折叠进同一父容器)。容器根(候选自身是 object 且 body 值为对象)
 * 的 children 按 body 实际键**递归整子树**展开;纯父壳只含提升子
 * (兄弟键不成子,残留归 extras)。数组候选 children-less(行渲染
 * 交 buildNode 值驱动;有深层候选则作行模板)。值不搬家 —— body 是
 * 唯一真源,这里只产渲染/编辑面的目录形状。
 */
export function promotedDecls(
  decls: DeclarationEntryView[] | undefined | null,
  fieldStates: Record<string, string> | null | undefined,
  body: unknown,
): DeclarationEntryView[] {
  const universe = catalogPaths(decls)
  const overlaps = (p: string, c: string) =>
    p === c || c.startsWith(`${p}.`) || p.startsWith(`${c}.`)
  const candidates = new Set<string>()
  for (const [rawP, s] of Object.entries(fieldStates ?? {})) {
    if (s !== 'form' && s !== 'collapse') continue
    const p = toTemplatePath(rawP)
    if (p === '$' || !p.startsWith('$.')) continue   // '$' 整包无提升语义
    let covered = false
    for (const c of universe) {
      if (overlaps(p, c)) { covered = true; break }
    }
    if (!covered) candidates.add(p)
  }
  if (!candidates.size) return []
  const relOf = (p: string) => p.replace(/^\$\.?/, '')
  const synth = (path: string, value: unknown): DeclarationEntryView => {
    const name = path.slice(path.lastIndexOf('.') + 1)
    if (Array.isArray(value)) return mkPromotedEntry(path, name, 'array', 'json')
    if (value !== null && typeof value === 'object') {
      return mkPromotedEntry(path, name, 'object', 'json')
    }
    if (typeof value === 'number') return mkPromotedEntry(path, name, 'number', 'number')
    if (typeof value === 'boolean') return mkPromotedEntry(path, name, 'boolean', 'boolean')
    return mkPromotedEntry(path, name, 'string', 'text')
  }
  const build = (
    path: string, deeper: Set<string>, expand: boolean,
  ): DeclarationEntryView => {
    const value = getByPath(body, relOf(path))
    const entry = synth(path, value)
    // 容器根提升 → body 整子树进树(zone 内子孙全展开);纯父壳只收
    // 提升子方向(兄弟 body 键不成子,残留归 extras)
    const zone = expand
      || (candidates.has(path) && entry.type === 'object')
    const childPaths = new Set<string>()
    if (zone && entry.type === 'object'
      && value !== null && typeof value === 'object' && !Array.isArray(value)) {
      for (const k of Object.keys(value as Record<string, unknown>)) {
        childPaths.add(`${path}.${k}`)
      }
    }
    // 深层候选折挂:按 path 下一段收敛(Set 去重,同段候选/壳合并)
    for (const d of deeper) {
      childPaths.add(`${path}.${d.slice(path.length + 1).split('.')[0]}`)
    }
    // array:children-less(行渲染交 buildNode 值驱动);有深层候选则
    // 作行模板(children 数组语义,buildNode 按行实例化)
    if (!childPaths.size) return entry
    return {
      ...entry,
      children: [...childPaths].map((cp) => build(
        cp,
        new Set([...deeper].filter((x) => x.startsWith(`${cp}.`))),
        zone,
      )),
    }
  }
  // 根分组:候选顶层段(顶层候选即自身;深层候选的顶段必不在目录
  // 宇宙 —— 祖先若在目录,候选已被 overlaps 让位,无路径冲突)。
  const roots = new Set<string>()
  for (const p of candidates) roots.add(`$.${p.slice(2).split('.')[0]}`)
  return [...roots].map((r) => build(
    r,
    new Set([...candidates].filter((c) => c !== r && c.startsWith(`${r}.`))),
    false,
  ))
}
