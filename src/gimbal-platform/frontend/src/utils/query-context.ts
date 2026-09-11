/**
 * query-context.ts — 编辑期查询上下文解析(数据集单变量面板取数,spec v2 §6)
 *
 * 与 CaseComposerCanvas.resolveQueryContext 同源语义(修订 10/11,不 import
 * Canvas 是因为那边绑定 draftStore;本模块纯函数化供数据集侧复用):
 *   serviceUrl = 声明服务表(definition.config.services,svc → URL 平表)
 *   queryAlias = step headers `${auth.<tag>.…}` 引用首命中(该步执行身份声明)
 *                ▸ 与服务 URL 同域(origin)的 config.users 首键
 *                ▸ 服务 URL 未知时全表首键
 * 零 IO;悬空照发由后端诚实 422(Canvas 同款裁定,不前端猜测回退)。
 */
import { parseTplRefs } from './tpl-refs'

export interface QueryCtxConfig {
  /** svc → URL 平表(definition.config.services) */
  services?: Record<string, unknown>
  /** 凭证条目(definition.config.users;键 = 凭证别名,值含登录域 url) */
  users?: Record<string, { url?: unknown }>
}

/** 取数步骤上下文的最小形状(编辑器从 draft 步骤投影) */
export interface QueryCtxStep {
  /** step.api.service(空 = 未声明服务) */
  service?: string | null
  headers?: Record<string, unknown> | null
}

/** 单变量面板取数的步骤上下文投影(编辑器从 draft 步骤投影,面板消费;
 *  index/label 供选择器展示,bodyTop 供参数面同名约定预填) */
export interface PanelStepContext extends QueryCtxStep {
  /** 步骤序(0-based) */
  index: number
  /** 展示名(orchestration 步骤名,缺名降级 Step N) */
  label: string
  /** request.body 顶层平对象(数组/非对象 → 空) */
  bodyTop: Record<string, unknown>
}

/** url → origin(scheme+host+port 归一);空/非串/解析失败 → null。 */
function urlOriginOf(u: unknown): string | null {
  if (typeof u !== 'string' || !u) return null
  try { return new URL(u).origin } catch { return null }
}

/** headers `${auth.<tag>.…}` 引用首命中 → tag(修订 11:headers 引用即执行身份)。 */
export function headerAuthTagOf(step: QueryCtxStep): string | null {
  for (const v of Object.values(step.headers ?? {})) {
    const ref = parseTplRefs(String(v ?? '')).find(r => r.domain === 'auth' && r.alias)
    if (ref?.alias) return ref.alias
  }
  return null
}

/**
 * 查询上下文:服务 URL + 查询别名。别名解析序 = headers auth 首命中 ▸
 * 同域 users 首键(修订 10:查询身份 = 执行身份;不回退异域首键 — 错域
 * token 必被 SUT 拒)▸ 服务 URL 未知时全表首键(服务侧 422 先炸)。
 * 零命中(该域没配用户)→ null,后端诚实 422「未找到查询凭证」。
 */
export function resolveQueryCtx(
  step: QueryCtxStep,
  config: QueryCtxConfig,
): { serviceUrl?: string; queryAlias: string | null } {
  const svc = step.service || ''
  const svcUrl = typeof config.services?.[svc] === 'string' ? (config.services[svc] as string) : ''
  const users = config.users ?? {}
  const keys = Object.keys(users)
  const first = keys[0]?.trim() || null
  const origin = urlOriginOf(svcUrl)
  const alias = origin
    ? keys.find(k => urlOriginOf(users[k]?.url) === origin) ?? null
    : first
  return { serviceUrl: svcUrl || undefined, queryAlias: headerAuthTagOf(step) ?? alias }
}
