/**
 * pool-var.ts — 常量池播种 config.vars 的纯函数(快照语义)。
 *
 * 引擎事实: config.vars 在 preprocess Phase 1.5 求值生成器、Phase 3
 * 展开 ${var.x};因此生成器 key 的"插入"除插引用文本外,还要把 spec
 * 快照播种进 config.vars(name 已存在则不覆盖 —— ??= 语义,提示走调用方)。
 * 纯函数与组件解耦,便于单测快照语义。
 */

export interface SeedVarResult<T> {
  definition: T
  /** false = 同名已存在,未播种(调用方提示"使用现有值")。 */
  seeded: boolean
}

export function seedPoolVarIntoDefinition<
  T extends { config?: { vars?: Record<string, unknown> } | null },
>(definition: T, name: string, spec: Record<string, unknown>): SeedVarResult<T> {
  const config = definition.config ?? { vars: {} as Record<string, unknown> }
  const vars = { ...(config.vars ?? {}) }
  let seeded = false
  if (!Object.prototype.hasOwnProperty.call(vars, name)) {
    vars[name] = spec
    seeded = true
  }
  return {
    definition: { ...definition, config: { ...config, vars } },
    seeded,
  }
}
