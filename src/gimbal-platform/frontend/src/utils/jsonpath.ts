/**
 * jsonpath.ts — minimal JSONPath get/set helpers.
 * Used by FieldForm to read/write form values into the step body via
 * the IOFieldBinding's ``path`` (e.g. ``"$.customer_id"``).
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

export function deepDefaults(bindings: Array<{ path: string; default: any; example: any }>): any {
  const root: any = {}
  for (const f of bindings) {
    const v = f.default !== null && f.default !== undefined ? f.default : f.example
    if (v === null || v === undefined) continue
    setByPath(root, f.path.replace(/^\$\./, ''), v)
  }
  return root
}
