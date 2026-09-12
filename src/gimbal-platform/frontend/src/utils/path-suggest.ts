/**
 * path-suggest — jsonpath 按层提示的纯函数层。
 *
 * 给定某地址域下的**全叶子路径**与用户已输入文本,回答「当前这一层还有哪些段」:
 * 输入 `$.da` → `data`;输入 `$.data.` → 该层的子字段;输入 `$.data.items` →
 * 数组实例 `[0]`。数组实例折叠为首实例(附 `count`),段分 `leaf` / `container`
 * —— 容器可作注入锚点(spec v3 §2:Assign 整体覆写该容器)。
 *
 * 只做提示,不做校验:调用方保留自由手打,无候选时退化为普通输入框。
 */

export interface PathSuggestion {
  /** 本层要补的段(如 `amount` / `[0]`) */
  segment: string
  /** 补全后的完整路径 */
  path: string
  /** leaf = 完整叶子(选中即补全);container = 还有下一层 */
  kind: 'leaf' | 'container'
  /** 仅数组段在场:该层实例总数(提示「共 N 项」,建议只给首实例) */
  count?: number
}

const ARRAY_SEG_RE = /^\[(\d+)\]$/

/** 一条叶子的各级容器前缀(只切在段边界:`.` 之后 / `[` 之前) */
function prefixesOf(path: string): string[] {
  const out: string[] = []
  for (let i = 0; i < path.length; i++) {
    const ch = path[i]
    const next = path[i + 1]
    if (ch === '[' && i > 0) out.push(path.slice(0, i))
    if ((ch === '.' || ch === ']') && next !== undefined) {
      const cut = path.slice(0, i + 1)
      out.push(cut.endsWith('.') ? cut.slice(0, -1) : cut)
    }
  }
  return out
}

/** 叶子路径 → 含各级容器前缀的节点集(去重,保持叶子源的首次出现序) */
export function expandNodePaths(leafPaths: readonly string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  const push = (p: string) => {
    if (p && !seen.has(p)) {
      seen.add(p)
      out.push(p)
    }
  }
  for (const leaf of leafPaths) {
    for (const pre of prefixesOf(leaf)) push(pre)
    push(leaf)
  }
  return out
}

/**
 * 已输入文本 → 当前层的下一段建议。
 * 文本不以 `$` 开头(非法/空域)一律不给建议;叶子已写全则无建议。
 */
export function nextLevelSuggestions(
  leafPaths: readonly string[],
  typed: string,
): PathSuggestion[] {
  if (!leafPaths.length) return []
  const nodes = expandNodePaths(leafPaths)
  const leafSet = new Set(leafPaths)
  const t = typed.trim() || '$'
  if (!t.startsWith('$')) return []

  // 父节点 = 最长的、被 t 以段边界方式前缀命中的节点
  let parent = ''
  for (const n of nodes) {
    const isPrefix = t === n || (t.startsWith(n) && (t[n.length] === '.' || t[n.length] === '['))
    if (isPrefix && n.length > parent.length) parent = n
  }
  if (!parent) return []

  const rest = t.slice(parent.length).replace(/^\./, '')
  const segments: Array<{ segment: string; path: string }> = []
  for (const n of nodes) {
    if (n === parent) continue
    if (!n.startsWith(parent)) continue
    const rel = parent === '$' ? n.slice(1) : n.slice(parent.length)
    const segment = rel.startsWith('.') ? rel.slice(1) : rel
    // 只取下一层:段 = 纯字段名,或恰好一个数组下标(其余含分隔符 = 更深层)
    if (!segment) continue
    if (!ARRAY_SEG_RE.test(segment) && /[.[\]]/.test(segment)) continue
    if (!segment.toLowerCase().startsWith(rest.toLowerCase())) continue
    segments.push({ segment, path: n })
  }

  // 数组段:统计该层实例数后只留首实例(降噪)
  const arrayIdx = new Set<number>()
  for (const n of nodes) {
    if (n === parent || !n.startsWith(parent)) continue
    const rel = parent === '$' ? n.slice(1) : n.slice(parent.length)
    const seg = rel.startsWith('.') ? rel.slice(1) : rel
    const m = ARRAY_SEG_RE.exec(seg)
    if (m) arrayIdx.add(Number(m[1]))
  }

  const out: PathSuggestion[] = []
  const seenSeg = new Set<string>()
  let arrayPushed = false
  for (const s of segments) {
    const m = ARRAY_SEG_RE.exec(s.segment)
    if (m) {
      if (arrayPushed) continue          // 只留首实例
      arrayPushed = true
      out.push({ ...s, kind: leafSet.has(s.path) ? 'leaf' : 'container', count: arrayIdx.size })
      continue
    }
    if (seenSeg.has(s.segment)) continue
    seenSeg.add(s.segment)
    out.push({ ...s, kind: leafSet.has(s.path) ? 'leaf' : 'container' })
  }
  return out
}
