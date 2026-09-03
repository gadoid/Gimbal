/**
 * jsonpath.ts — minimal JSONPath get/set/prune helpers.
 * Used by FieldForm to read/write form values into the step body via
 * the IOFieldBinding's ``path`` (e.g. ``"$.customer_id"``).
 *
 * ⚠ 能力边界:支持 ``$.a.b`` 与 ``$.a[0].b``(FIELD/INDEX);通配/过滤器/
 * 递归仍不支持,与 Python 侧(gimbal/utils/jsonpath.py)写路径边界一致。
 * bracket 仅十进制非负下标;``$['x']`` 引号记法与负下标为已知边界,不解析。
 * 根 list body(Task 10):``$`` 后可直接跟下标(``$[0].b``)—— 请求体直接是
 * JSON 数组的端点寻址;剥离 ``$`` 与可选点后 rel 以 ``[`` 开头即此形态
 * (容器须为数组根;dict 根 + 首段 INDEX 落字符串键是已知边界)。
 */

/** 'a[0].b' → ['a', 0, 'b'](下标转 number;容器按下一 segment 类型创建) */
function parseSegments(rel: string): Array<string | number> {
  const segs: Array<string | number> = []
  for (const m of rel.matchAll(/([^[\].]+)|\[(\d+)\]/g)) {
    segs.push(m[1] !== undefined ? m[1] : Number(m[2]))
  }
  return segs
}

export function getByPath(obj: any, path: string): any {
  if (!obj || !path) return undefined
  let cur = obj
  for (const seg of parseSegments(path.replace(/^\$\.?/, ''))) {
    if (cur === null || cur === undefined) return undefined
    cur = typeof seg === 'number'
      ? (Array.isArray(cur) ? cur[seg] : undefined)
      : cur[seg]
  }
  return cur
}

export function setByPath(obj: any, path: string, value: any): void {
  if (!obj || !path) return
  const segs = parseSegments(path.replace(/^\$\.?/, ''))
  if (!segs.length) return // 裸 `$`(整包)无段可写 — no-op,不落幻影键
  let cur = obj
  for (let i = 0; i < segs.length - 1; i++) {
    const seg = segs[i]
    let child = cur[seg]
    if (child === null || child === undefined || typeof child !== 'object') {
      child = typeof segs[i + 1] === 'number' ? [] : {}
      if (typeof seg === 'number') {
        while (cur.length <= seg) cur.push(null)
      }
      cur[seg] = child
    }
    cur = child
  }
  const last = segs[segs.length - 1]
  if (typeof last === 'number') while (cur.length <= last) cur.push(null)
  cur[last] = value
}

/** D8 容器级剪枝:删叶子(FIELD→delete 键/末段 INDEX→置 null,不 splice 防索引漂移);
 *  祖先链因此全空(空 dict/空 list/全 null)→ 连锁删到根键;中间空元素保留。 */
export function pruneByPath(obj: any, path: string): void {
  if (!obj || !path) return
  const segs = parseSegments(path.replace(/^\$\.?/, ''))
  if (!segs.length) return
  const chain: any[] = [obj]
  for (let i = 0; i < segs.length - 1; i++) chain.push(chain[chain.length - 1]?.[segs[i]])
  const parent = chain[chain.length - 1]
  const last = segs[segs.length - 1]
  if (parent == null || typeof parent !== 'object') return
  if (typeof last === 'number') parent[last] = null
  else delete parent[last]
  const isEmpty = (v: any): boolean =>
    Array.isArray(v) ? v.every((x) => x == null) :
    v && typeof v === 'object' ? Object.keys(v).length === 0 : true
  for (let i = segs.length - 2; i >= 0; i--) {
    if (!isEmpty(chain[i + 1])) break
    const seg = segs[i]
    if (typeof seg === 'number') chain[i][seg] = null
    else delete chain[i][seg]
  }
}

/**
 * 新建步骤初始 body 合成(单来源):IOFieldBinding 的 default(缺省
 * example)按 path 写入。
 * 契约字段(schema 有、binding 无)的 schema default 不再拷贝 —— 该职责
 * 已移交 carry 通道(platform 值表 + materialize 注入,spec §5)。
 * D7:bracket 深层默认只展示不落库(防挡 carry 容器注入),展示由
 * FieldForm getValue 的 default 兜底承担。
 */
export function deepDefaults(
  bindings: Array<{ path: string; default: any; example: any }>,
): any {
  const root: any = {}
  for (const f of bindings) {
    const rel = f.path.replace(/^\$\.?/, '')
    if (/\[/.test(rel)) continue // D7:深层默认只展示不落库
    const v = f.default !== null && f.default !== undefined ? f.default : f.example
    if (v === null || v === undefined) continue
    setByPath(root, rel, v)
  }
  return root
}
