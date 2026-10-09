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

// ── 画布结构推断(第 4 步;原型 11/12,交互规则「模式由结构推断」)──
// 自上而下五条规则,命中第一条即止;「开始」节点的连线不参与。

export interface StructureInference {
  mode: SuiteMode
  /** 状态条的一句理由(原型 12 每步的 why)。 */
  reason: string
  /** 孤立单元数(规则 5 提示漏连;规则 1 时等于单元数、不提示)。 */
  isolated: number
  /** 串联的链路顺序(仅 chain 非空)。 */
  line: string[] | null
  /** 扇出的源(仅 fanout 非空)。 */
  source: string | null
}

/**
 * needsOf[B] = [A, …] 表示画布上有 A → B 的连线(B needs A)。
 * ids 为主体单元的 scenarioId(前置 / 后置不参与)。
 */
export function inferStructure(
  ids: string[], needsOf: Record<string, string[]>,
): StructureInference {
  const n = ids.length
  const needs: Record<string, string[]> = {}
  for (const id of ids) needs[id] = (needsOf[id] || []).filter((x) => ids.includes(x))
  const edgeCount = ids.reduce((s, id) => s + needs[id].length, 0)
  if (n === 0 || edgeCount === 0) {
    return {
      mode: 'aggregate', isolated: n, line: null, source: null,
      reason: n <= 1
        ? (n === 0 ? '拖入第一个场景开始。' : '只有一个单元,等同聚合。继续拖入或拉线。')
        : '单元之间互不相连,各跑各的(聚合)。',
    }
  }
  // 链头:唯一无入边的单元;从它沿唯一出边走,能走完 n 个即一条直线
  const inDeg: Record<string, number> = {}
  const outTo: Record<string, string[]> = {}
  for (const id of ids) { inDeg[id] = 0; outTo[id] = [] }
  for (const id of ids) for (const p of needs[id]) { inDeg[id]++; outTo[p].push(id) }
  const heads = ids.filter((id) => inDeg[id] === 0)
  if (edgeCount === n - 1 && heads.length === 1) {
    const line = [heads[0]]
    let cur = heads[0]
    while (outTo[cur].length === 1) { cur = outTo[cur][0]; line.push(cur) }
    if (line.length === n) {
      return {
        mode: 'chain', isolated: 0, line, source: null,
        reason: '全部单元连成一条直线 → 串联;按链路顺序执行,上游产出自动传给下游。',
      }
    }
  }
  // 扇出:唯一源指向其余全部,其余之间无连线
  if (edgeCount === n - 1 && heads.length === 1 && outTo[heads[0]].length === n - 1) {
    return {
      mode: 'fanout', isolated: 0, line: null, source: heads[0],
      reason: '一个单元指向其余全部、它们之间无连线 → 扇出,该单元是源。',
    }
  }
  const isolated = ids.filter((id) => inDeg[id] === 0 && outTo[id].length === 0).length
  const layers = layeredUnits(
    ids.map((scenarioId) => ({ scenarioId })),
    { units: Object.fromEntries(ids.map((id) => [id, { needs: needs[id] }])) },
  ).layers.length
  return {
    mode: 'compose', isolated, line: null, source: null,
    reason: isolated > 0
      ? `有分叉 / 汇合 → 依赖编排;另有 ${isolated} 个未连线单元按「无依赖」处理,确认不是漏连。`
      : `有分叉 / 汇合(共 ${layers} 层)→ 依赖编排,每条连线即一条 needs。`,
  }
}

/** 保存时按识别结果写成员顺序:串联按链路先后,扇出把源排在第一位。 */
export function orderByStructure(
  inference: StructureInference, currentOrder: string[],
): string[] {
  if (inference.mode === 'chain' && inference.line) return inference.line
  if (inference.mode === 'fanout' && inference.source) {
    return [inference.source, ...currentOrder.filter((id) => id !== inference.source)]
  }
  return currentOrder
}

/** 已存 Suite → 画布连线(反向合成):串联按成员相邻、扇出以第一位为源、
 * 依赖编排取 units.needs;聚合无线。画布加载与回归管理页共用。 */
export function canvasEdgesFromSuite(
  mode: string,
  mainIds: string[],
  units: Record<string, SuiteUnitConfig> | undefined,
): Record<string, string[]> {
  const needsOf: Record<string, string[]> = {}
  const put = (b: string, a: string): void => {
    (needsOf[b] ||= []).push(a)
  }
  if (mode === 'chain') {
    for (let i = 1; i < mainIds.length; i++) put(mainIds[i], mainIds[i - 1])
  } else if (mode === 'fanout' && mainIds.length > 1) {
    for (let i = 1; i < mainIds.length; i++) put(mainIds[i], mainIds[0])
  } else if (mode === 'compose') {
    for (const b of mainIds) {
      for (const a of units?.[b]?.needs || []) {
        if (mainIds.includes(a)) put(b, a)
      }
    }
  }
  return needsOf
}

/** 新连线 producer → consumer 是否成环(本地环拒绝;服务端校验为唯一闸)。 */
export function edgeMakesCycle(
  allIds: string[], needsOf: Record<string, string[]>,
  producer: string, consumer: string,
): boolean {
  // consumer 经既有边能否回到 producer
  const seen = new Set<string>()
  const stack = [consumer]
  while (stack.length) {
    const cur = stack.pop() as string
    if (cur === producer) return true
    if (seen.has(cur)) continue
    seen.add(cur)
    for (const nxt of allIds) {
      if ((needsOf[nxt] || []).includes(cur)) stack.push(nxt)
    }
  }
  return false
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
