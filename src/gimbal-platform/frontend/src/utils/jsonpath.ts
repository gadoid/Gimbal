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
 * 新建步骤初始 body 合成(单来源):IOFieldBinding 的 default(缺省
 * example)按 path 写入。
 * 契约字段(schema 有、binding 无)的 schema default 不再拷贝 —— 该职责
 * 已移交 carry 通道(platform 值表 + materialize 注入,spec §5)。
 */
export function deepDefaults(
  bindings: Array<{ path: string; default: any; example: any }>,
): any {
  const root: any = {}
  for (const f of bindings) {
    const v = f.default !== null && f.default !== undefined ? f.default : f.example
    if (v === null || v === undefined) continue
    setByPath(root, f.path.replace(/^\$\./, ''), v)
  }
  return root
}
