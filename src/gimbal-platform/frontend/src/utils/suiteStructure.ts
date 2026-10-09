/**
 * suiteStructure.ts — Suite 结构纯函数(Suite 层重构第 2 步起步,
 * 第 4 步画布在其上补结构推断/环检测/按结构排序)。
 *
 * 单独成模块以便单测(方案「前端模块」:结构推断、环检测、按结构
 * 排序,不掺组件状态)。当前承载:模式元数据(原型 11/20 文案)、
 * 预计 runs、依赖编排分层 DAG、needs 环检测。
 */
import type {
  SuiteMode, SuiteModeConfig, SuiteUnitConfig,
} from '@/api/suites'

export interface ModeMeta {
  key: SuiteMode
  /** 模式条上的短名(含图标字形)。 */
  label: string
  /** 模式条说明(原型 20:一句怎么跑 + 一句留意)。 */
  explain: string
  hint: string
  /** 页头运行按钮副文案的通道说明。 */
  channel: string
}

export const MODES: ModeMeta[] = [
  {
    key: 'aggregate',
    label: '∥ 聚合',
    explain: '各成员独立执行、互不影响,共用一个批次',
    hint: '冒烟集 / 回归集;每个成员用其默认方案跑全部数据行',
    channel: '聚合 · 独立执行 · 一个批次',
  },
  {
    key: 'chain',
    label: '→ 串联',
    explain: '按顺序逐个执行:第 1 步失败即停',
    hint: '可设置「只跑到某一步」;单元间传值自动连线',
    channel: '串联 · 一次编排执行',
  },
  {
    key: 'fanout',
    label: '扇出',
    explain: '第 1 个成员是源:先跑它,其余成员并行、共用它的结果',
    hint: '变体用 ×重复 多跑几遍(如登录一次打多个接口)',
    channel: '扇出 · 一次编排执行',
  },
  {
    key: 'compose',
    label: '⤫ 依赖编排',
    explain: '按依赖并行:needs 决定顺序与传值',
    hint: '连线时同名输入需在单元上改名(map);其他无环结构',
    channel: '依赖编排 · 一次编排执行',
  },
]

export function modeMeta(mode: string): ModeMeta {
  return MODES.find((m) => m.key === mode) ?? MODES[0]
}

export const MODE_LABEL: Record<string, string> = {
  aggregate: '聚合',
  chain: '串联',
  fanout: '扇出',
  compose: '依赖编排',
}

/** 编排模式预计 runs:Σ 单元 repeat × nRuns(第 4 步画布同款口径)。 */
export function estimateOrchRuns(
  members: { scenarioId: string }[],
  config: SuiteModeConfig | null | undefined,
): number {
  const units: Record<string, SuiteUnitConfig> =
    (config?.units as Record<string, SuiteUnitConfig>) || {}
  return members.reduce((sum, m) => {
    const u = units[m.scenarioId] || {}
    return sum + Math.max(1, Number(u.repeat) || 1) * Math.max(1, Number(u.nRuns) || 1)
  }, 0)
}

/** 依赖编排分层:needs 边的拓扑层级(L0 = 无依赖);有环抛错由调用方提示。 */
export function layeredUnits(
  members: { scenarioId: string }[],
  config: SuiteModeConfig | null | undefined,
): { layers: string[][]; hasCycle: boolean } {
  const units: Record<string, SuiteUnitConfig> =
    (config?.units as Record<string, SuiteUnitConfig>) || {}
  const ids = members.map((m) => m.scenarioId)
  const needs: Record<string, string[]> = {}
  for (const id of ids) {
    needs[id] = (units[id]?.needs || []).filter((n) => ids.includes(n))
  }
  const level: Record<string, number> = {}
  const visiting = new Set<string>()
  const hasCycle = { v: false }
  const visit = (id: string): number => {
    if (id in level) return level[id]
    if (visiting.has(id)) { hasCycle.v = true; return 0 }
    visiting.add(id)
    let lv = 0
    for (const n of needs[id]) lv = Math.max(lv, visit(n) + 1)
    visiting.delete(id)
    level[id] = lv
    return lv
  }
  for (const id of ids) visit(id)
  const layers: string[][] = []
  for (const id of ids) {
    const lv = level[id] ?? 0
    ;(layers[lv] ||= []).push(id)
  }
  return { layers: layers.filter(Boolean), hasCycle: hasCycle.v }
}

/** needs 图环检测(保存前本地提示用;服务端校验为唯一闸)。 */
export function needsHasCycle(
  members: { scenarioId: string }[],
  config: SuiteModeConfig | null | undefined,
): boolean {
  return layeredUnits(members, config).hasCycle
}

/** 运行状态 → 展示色(21 页结果条/表格共用)。 */
export function runStatusTone(status: string): 'ok' | 'bad' | 'run' | 'muted' {
  if (status === 'done' || status === 'passed') return 'ok'
  if (status === 'failed' || status === 'error' || status === 'halted') return 'bad'
  if (status === 'running' || status === 'queued') return 'run'
  return 'muted'
}

export const RUN_STATUS_LABEL: Record<string, string> = {
  done: '完成', failed: '失败', error: '错误', halted: '中止',
  running: '运行中', queued: '排队中', canceled: '取消',
  passed: '通过',
}
