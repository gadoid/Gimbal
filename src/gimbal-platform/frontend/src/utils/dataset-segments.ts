/**
 * dataset-segments — 步骤请求面叶子路径扫描器(spec v2 §4,纯函数零 IO)。
 *
 * fieldPathsOf 报告 step 的 body(深扫)/ headers(浅扫)全叶子路径,
 * 模板(${var.x})与直填一视同仁 —— anchor 候选与「未模板化字段」兜底
 * 报告的数据源(§4 新增能力;消费方 useInjectableSurface、断言注册表)。
 * 与 dataset-palette 的 deriveBaselineColumns(traversal 有 endpoint_id
 * 纪律,服务直填列基线显示)互不依赖:叶子扫描与端点契约无关,
 * 不设 endpoint_id 门。
 */
import { stepHeaders } from '@/types/plate'
export const TPL_FULL_RE = /^\$\{var\.([A-Za-z0-9_.]+)\}$/

export interface SegmentStepShape {
  request?: { body?: unknown } | null
  call?: { headers?: Record<string, unknown> | null } | null
  strategy?: unknown[]
}

// ── 全叶子路径扫描(spec v2 §4)──────────────────────────────
export interface FieldLeaf {
  source: 'body' | 'headers'
  /** jsonpath 风格,$. 前缀;数组带 [i] 实例下标 */
  path: string
  /** 值整串 ${var.x} 模板时在场;未模板化叶无此键 */
  varName?: string
}

function leafOf(source: 'body' | 'headers', path: string, v: unknown): FieldLeaf {
  const leaf: FieldLeaf = { source, path }
  if (typeof v === 'string') {
    const m = TPL_FULL_RE.exec(v)
    if (m) leaf.varName = m[1]
  }
  return leaf
}

/** 报告 step 请求面(body 深扫 / headers 浅扫)的全叶子路径 — 模板与直填一视同仁;
 *  anchor 候选与「未模板化字段」兜底报告的数据源(§4 新增能力)。 */
export function fieldPathsOf(step: SegmentStepShape | null | undefined): FieldLeaf[] {
  const out: FieldLeaf[] = []
  if (!step) return out
  const walk = (v: unknown, path: string) => {
    if (v === undefined) return   // undefined = 无此叶(absent);null 是显式叶(报路径)
    if (Array.isArray(v)) { v.forEach((it, i) => walk(it, `${path || '$'}[${i}]`)); return }
    if (v && typeof v === 'object') {
      for (const [k, val] of Object.entries(v)) walk(val, path ? `${path}.${k}` : `$.${k}`)
      return
    }
    out.push(leafOf('body', path || '$', v))
  }
  walk(step?.request?.body, '')
  for (const [k, val] of Object.entries(stepHeaders(step) ?? {})) {
    if (val === undefined) continue   // JSON 不产 undefined;与 walk 的 undefined 守卫对称
    out.push(leafOf('headers', `$.${k}`, val))
  }
  return out
}
