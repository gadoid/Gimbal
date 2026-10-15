// scenario-import.ts — 场景导入流水线 API(v2.3 方案 §3,W5)。
// precheck(纯读演练)→ import(单事务落库);导出侧补「可导入」入口。
import http from '@/api/http'

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
  workingDeclarations: string[]
}

/** 落库映射项(P7-⑥:无值覆盖字段 —— 敏感值无输入口)。 */
export interface ImportMapping {
  serviceKey: string
  decision: 'reuse' | 'map' | 'create'
  createName?: string
  credentialAlias?: string | null
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
}): Promise<{ scenarioId: string; idMode: string }> {
  return http
    .post('/scenarios/import', payload)
    .then((r) => r.data)
}
