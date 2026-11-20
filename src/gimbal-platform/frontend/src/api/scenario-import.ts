// scenario-import.ts — 场景导入流水线 API(v2.3 方案 §3,W5)。
// precheck(纯读演练)→ import(单事务落库);导出侧补「可导入」入口。
import http from '@/api/http'
import type { IdentityBaseRef } from '@/api/scenario-composer'

/** 预检的按服务键析出分析行(v2.3 §3.1)。 */
export interface ImportServiceRow {
  serviceKey: string
  suggestion: 'reuse' | 'map' | 'create'
  localAlias: string | null
  /** 建议决策下的计数(顶层便捷位);界面按当前决策优先读 countsByDecision。 */
  fieldsToAlias: number
  fieldsKeptLiteral: number
  /** 三种决策各自的接管计数(切换决策后接管面不同,确认内容=实际执行)。 */
  countsByDecision?: Partial<Record<'create' | 'map' | 'reuse', {
    fieldsToAlias: number
    fieldsKeptLiteral: number
  }>>
  /** 各步骤取值不一致的路径(Codfish 规则):不交别名接管,保留文件原值。 */
  inconsistentPaths: string[]
  createNameAvailable: boolean
  sensitivePaths: string[]
}

/** 认证引用栏数据(P7-③:config.users 清空后的 ${auth.*} 可解析性)。 */
export interface ImportAuthRef {
  tag: string
  inMyPool: boolean
}

/** S7.5 预检栏:文件内置凭证键(明文不落库,按条目口径落地)。 */
export interface ImportBuiltinUser {
  tag: string
  /** 经 call.user 使用该键的服务键 */
  services: string[]
  /** 被 ${auth.<tag>.*} 模板引用(本就进注入清单,按同名条目装载) */
  templated: boolean
  /** 导入人同名条目已装载账户 */
  bound: boolean
}

/** S7.5(ref 重做)落库回报:需要装载的身份条目 × 导入人装载状态
 *  (按落库形态重算)。 */
export interface ImportAuthEntry {
  entry: string
  bound: boolean
  /** 源文件内置凭证转来(含改写目标) */
  fromBuiltin: boolean
  /** 条目自主档派生的登记坐标(悬空条目为 null,深链退普通入口) */
  system: string | null
  envId: number | null
}

export interface ImportResult {
  scenarioId: string
  idMode: string
  authEntries?: ImportAuthEntry[]
  /** 映射/新建到条目:步骤 call.user 已改写为本机条目名 */
  authRenames?: { service: string; from: string; to: string }[]
  /** call.user 标签不在注入清单 —— 该步执行会报错 */
  undeclaredUsers?: {
    tag: string
    services: string[]
    reason: 'no_identity' | 'multi_user'
  }[]
  /** 没有任何步骤用到的内置凭证键(仅丢明文) */
  droppedUsers?: string[]
  /** 决策 1 登记闸 audit 态(阶段 0 载体):改写后最终形态里仍未登记的
   *  引用名 —— 保存已放行,前端黄条提示(2c 收口;enforce 态直接 422)。 */
  identityWarnings?: string[]
  /** 声明侧同 base 闸 audit 态(阶段 3):已登记条目与所在步骤服务跨
   *  base 的引用行 —— 保存已放行,前端黄条提示;enforce 态直接 422。 */
  identityBaseWarnings?: IdentityBaseRef[]
}

/** 重锚定报告条目(#323):reason 为 null 才是已锚。not_in_revision 等
 *  未锚原因时 endpoint 携带被拒的命中候选,仅供排查,不代表已锚。 */
export interface ImportAnchorEntry {
  index: number
  service: string | null
  method: string | null
  path: string | null
  endpoint: string | null
  reason: 'not_in_catalog' | 'ambiguous' | 'not_in_revision'
    | 'catalog_unavailable' | null
}

export interface ImportPrecheck {
  blocking: boolean
  formatError: { code: string } | null
  convert: { ok: boolean; errors: string[] }
  metaPlate: Record<string, string>
  availableRevisions: Record<string, string[]>
  idConflict: boolean
  suggestedId: string | null
  services: ImportServiceRow[]
  authRefs: ImportAuthRef[]
  /** S7.5;旧负载/阻断路径可能缺省 */
  builtinUsers?: ImportBuiltinUser[]
  workingDeclarations: string[]
  /** 步骤锚定(可执行形态反查);旧负载/阻断路径可能缺省。 */
  anchoring?: { anchored: ImportAnchorEntry[]; unresolved: ImportAnchorEntry[] }
}

/** 落库映射项(P7-⑥:无值覆盖字段 —— 敏感值无输入口;旧
 *  credentialAlias/slot 键随挂认证下拉退役,ref 重做后不再发送)。 */
export interface ImportMapping {
  serviceKey: string
  decision: 'reuse' | 'map' | 'create'
  createName?: string
}

export function importPrecheck(bundle: unknown): Promise<ImportPrecheck> {
  return http
    .post<ImportPrecheck>('/scenarios/import/precheck', { bundle })
    .then((r) => r.data)
}

export function importScenario(payload: {
  bundle: unknown
  mappings?: ImportMapping[]
  idMode?: 'keep' | 'new'
  newId?: string
}): Promise<ImportResult> {
  return http
    .post('/scenarios/import', payload)
    .then((r) => r.data)
}
