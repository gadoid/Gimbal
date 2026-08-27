/**
 * jsonpath.ts — minimal JSONPath get/set helpers.
 * Used by FieldForm to read/write form values into the step body via
 * the IOFieldBinding's ``path`` (e.g. ``"$.customer_id"``).
 *
 * ⚠ 能力边界:仅支持 ``$.a.b`` 形式的平铺字段路径。与 Python 侧
 * (gimbal/utils/jsonpath.py)不同,这里不支持数组下标(``$.items[0]``)、
 * 通配符(``[*]``)、过滤器与递归(``$..f``)。plate 当前的绑定路径均为
 * 平铺字段;若未来契约出现下标路径,需补齐 bracket 解析。
 */

export function getByPath(obj: any, path: string): any {
  if (!obj || !path) return undefined
  const parts = path.replace(/^\$\./, '').split('.')
  let cur = obj
  for (const p of parts) {
    if (cur === null || cur === undefined) return undefined
    cur = cur[p]
  }
  return cur
}

export function setByPath(obj: any, path: string, value: any): void {
  if (!obj || !path) return
  const parts = path.replace(/^\$\./, '').split('.')
  let cur = obj
  for (let i = 0; i < parts.length - 1; i++) {
    const p = parts[i]
    if (cur[p] === null || cur[p] === undefined) {
      cur[p] = typeof parts[i + 1] === 'string' && /^\d+$/.test(parts[i + 1]) ? [] : {}
    }
    cur = cur[p]
  }
  cur[parts[parts.length - 1]] = value
}

/**
 * 新建步骤初始 body 合成,两个来源:
 * ① IOFieldBinding 的 default(缺省 example)按 path 写入;
 * ② plate 契约字段(schema 有、binding 无)配了 schema default 的写入顶层键
 *    — 默认随请求发送;没配 default 不造空值,同名绑定已写的值优先。
 */
export function deepDefaults(
  bindings: Array<{ path: string; default: any; example: any }>,
  unbound?: Array<{ name: string; default?: unknown }>,
): any {
  const root: any = {}
  for (const f of bindings) {
    const v = f.default !== null && f.default !== undefined ? f.default : f.example
    if (v === null || v === undefined) continue
    setByPath(root, f.path.replace(/^\$\./, ''), v)
  }
  for (const f of unbound ?? []) {
    if (f.default === undefined || f.default === null) continue
    if (root[f.name] !== undefined) continue
    root[f.name] = f.default
  }
  return root
}
