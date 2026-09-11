// utils/assertion-registry.ts
import type { AssertionEntry } from '@/types/assertion-registry'

export type RegistryIssue =
  | { kind: 'step-oob'; stepIndex: number }
  | { kind: 'var-unknown'; varName: string }
  | { kind: 'override-no-match'; stepIndex: number; target: string }

/** 悬空检测(spec §3):stepIndex 越界 / injection.varName ∉ config.vars /
 *  override 匹配不到既有断言。assertTargetsOf 由调用方从 steps[si].strategy
 *  的 assertion 条目投影(target 集合)。 */
export function registryIssues(
  entry: AssertionEntry,
  stepCount: number,
  varNames: ReadonlySet<string>,
  assertTargetsOf: (stepIndex: number) => ReadonlySet<string>,
): RegistryIssue[] {
  const issues: RegistryIssue[] = []
  const idxs = new Set<number>()
  if (entry.anchor) idxs.add(entry.anchor.stepIndex)
  for (const a of entry.asserts) idxs.add(a.stepIndex)
  for (const si of idxs) {
    if (si < 0 || si >= stepCount) issues.push({ kind: 'step-oob', stepIndex: si })
  }
  for (const inj of entry.injection) {
    if (!varNames.has(inj.varName)) issues.push({ kind: 'var-unknown', varName: inj.varName })
  }
  for (const a of entry.asserts) {
    if (a.mode === 'override' && a.stepIndex >= 0 && a.stepIndex < stepCount
      && !assertTargetsOf(a.stepIndex).has(a.target)) {
      issues.push({ kind: 'override-no-match', stepIndex: a.stepIndex, target: a.target })
    }
  }
  return issues
}

export function isDeadEntry(
  entry: AssertionEntry,
  stepCount: number,
  varNames: ReadonlySet<string>,
  assertTargetsOf: (stepIndex: number) => ReadonlySet<string>,
): boolean {
  return registryIssues(entry, stepCount, varNames, assertTargetsOf).length > 0
}

/** 条目 id:inj-<6位base36时间戳><3位随机>(genScenarioId 同款纪律,无依赖) */
export function genEntryId(): string {
  const ts = Date.now().toString(36).slice(-6)
  const rnd = Math.floor(Math.random() * 36 ** 3).toString(36).padStart(3, '0')
  return `inj-${ts}${rnd}`
}
