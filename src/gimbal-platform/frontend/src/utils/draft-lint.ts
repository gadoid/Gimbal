/**
 * draft-lint.ts — 保存前非阻断 lint(spec §4.3/C10 前端半)
 *
 * ① 步骤缺 endpoint_id —— 不进反向索引,是变更适配的盲区;
 * ② 共享变量声明未引用 —— 死数据。
 * 「引用未声明」不在此判:数据集列运行期才 layer 进 vars,保存期
 * 无法区分合法列名与拼错的变量名,判了必误报。
 */
import { assignVarRefs, deriveVarRegistry, varUsages } from './var-registry'
import { stepEndpointId } from '@/types/plate'

export function lintDraft(
  definition: {
    steps?: any[]
    config?: { vars?: Record<string, unknown> }
  },
  opts: { exemptVars?: ReadonlySet<string> | readonly string[] } = {},
): string[] {
  const warns: string[] = []
  // D6(登记册,2026-11-23 收口):选系统预填(useSystemPrefill)种下的
  // 变量是「待接线素材」而非用户手写死数据 —— 未引用告警对它们纯属
  // 自造噪音;调用方传入豁免集,接线(或删除)前的保存不再逐个提醒。
  const exempt = new Set(opts.exemptVars ?? [])
  const steps = (definition.steps ?? []).map((s: any) => s ?? {})

  steps.forEach((s: any, i: number) => {
    // 无 api 的步骤同样算未索引(与后端 parse_refs 对齐)
    if (!stepEndpointId(s)) {
      warns.push(`步骤 ${i + 1} 未绑定接口目录(endpoint_id 缺失,不进反向索引)`)
    }
  })

  const registry = deriveVarRegistry(steps, definition.config?.vars)
  const used = new Set<string>([
    ...varUsages(steps).keys(),
    ...assignVarRefs(steps).map((r) => r.name),
  ])
  for (const e of registry.entries) {
    if (e.origin === 'config' && !used.has(e.name) && !exempt.has(e.name)) {
      warns.push(`共享变量 ${e.name} 声明了但未被引用(死数据)`)
    }
  }
  return warns
}
