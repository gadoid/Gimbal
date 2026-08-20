/**
 * tpl-refs.ts — ${...} 模板引用的解析与悬空判定
 *
 * 服务的 UI 场景:headers value / 字段值中出现的
 *   ${auth.<alias>.<field>}   认证引用(选不手打)
 *   ${var.<name>}             变量引用(#3 变量全局化复用)
 * 悬空判定 = 引用指向的 alias/变量在已知集合里不存在。
 * 本模块纯函数,无 IO;known 集合由调用方 fetch 后传入。
 */

/** 一个 ${...} 引用的结构化拆解 */
export interface TplRef {
  /** 原文,如 "${auth.qa1.token}" */
  raw: string
  /** 引用域:auth / var / 其它前缀段 */
  domain: string
  /** auth 域的 alias;非 auth 域为 null */
  alias: string | null
  /** auth 域的字段名(token/username/password);非 auth 域为 null */
  field: string | null
}

const TPL_RE = /\$\{([^}]+)\}/g

/** 拆出文本里的全部 ${...} 引用(重复出现会重复列出) */
export function parseTplRefs(text: string): TplRef[] {
  if (!text) return []
  const out: TplRef[] = []
  for (const m of text.matchAll(TPL_RE)) {
    const expr = m[1].trim()
    const raw = m[0]
    if (expr.startsWith('auth.')) {
      // ${auth.<alias>.<field>} — alias 不含点,field 为余下段
      const rest = expr.slice('auth.'.length)
      const dot = rest.indexOf('.')
      out.push(dot >= 0
        ? { raw, domain: 'auth', alias: rest.slice(0, dot), field: rest.slice(dot + 1) }
        : { raw, domain: 'auth', alias: rest, field: null })
    } else if (expr.startsWith('var.')) {
      out.push({ raw, domain: 'var', alias: restOf(expr, 'var.'), field: null })
    } else {
      out.push({ raw, domain: expr.split('.')[0] || '?', alias: null, field: null })
    }
  }
  return out
}

function restOf(expr: string, prefix: string): string | null {
  const rest = expr.slice(prefix.length)
  return rest || null
}

export type RefStatus = 'ok' | 'dangling'

/** 徽章渲染需要的状态:auth 域对 knownAliases 判,其它域一律 ok(#3 再细分) */
export function refStatus(ref: TplRef, knownAliases: string[] = []): RefStatus {
  if (ref.domain === 'auth' && ref.alias && !knownAliases.includes(ref.alias)) {
    return 'dangling'
  }
  return 'ok'
}
