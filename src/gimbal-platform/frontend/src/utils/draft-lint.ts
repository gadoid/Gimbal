/**
 * draft-lint.ts — 保存前非阻断 lint(spec §4.3/C10 前端半)
 *
 * ① 步骤缺 endpoint_id —— 不进反向索引,是变更适配的盲区;
 * ② 共享变量声明未引用 —— 死数据。
 * 「引用未声明」不在此判:数据集列运行期才 layer 进 vars,保存期
 * 无法区分合法列名与拼错的变量名,判了必误报。
 */
import { assignVarRefs, deriveVarRegistry, varUsages } from './var-registry'

export function lintDraft(definition: {
  steps?: any[]
  config?: { vars?: Record<string, unknown> }
}): string[] {
  const warns: string[] = []
  const steps = (definition.steps ?? []).map((s: any) => s ?? {})

  steps.forEach((s: any, i: number) => {
    if (s?.api && !s.api?.view_hints?.endpoint_id) {
      warns.push(`步骤 ${i + 1} 未绑定接口目录(endpoint_id 缺失,不进反向索引)`)
    }
  })

  const registry = deriveVarRegistry(steps, definition.config?.vars)
  const used = new Set<string>([
    ...varUsages(steps).keys(),
    ...assignVarRefs(steps).map((r) => r.name),
  ])
  for (const e of registry.entries) {
    if (e.origin === 'config' && !used.has(e.name)) {
      warns.push(`共享变量 ${e.name} 声明了但未被引用(死数据)`)
    }
  }
  return warns
}
