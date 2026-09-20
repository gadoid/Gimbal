/**
 * run-bindings.ts — 运行绑定的**纯函数**单源(执行设计 §1.5)。
 *
 * RunDialog / SchemeRunConfigSection 此前各自持有一份
 * `explicitBindingOf` / `degraded` / `MAX_TOTAL_RUNS` 镜像(注释互认"口径
 * 镜像");这些函数不依赖 scenarioId、不取数,抽到这里与两个消费方共用,
 * 不再有第三份。装配逻辑(取数/派生/dispatch)在 useRunAssembly,不在这里
 * —— 别让本文件变成既装配又判定的混合体。
 *
 * 失效判定的**死集**输入来自 useInjectableSurface.deadIds(唯一派生,
 * 视图不得复刻);本文件只做"方案 × 死集 × 数据集清单"的纯组装。
 */
import type { ServiceBinding, SchemeV2 } from '@/api/scenario-composer'
import type { DataSetSummary } from '@/types/scenario-composer'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'

/** 绑定行(spec D3):声明 ∪ 引用并集的固定行;declaredUrl null = 未声明引用行 */
export interface ServiceRow { service: string; declaredUrl: string | null }

/** 总量闸(行数 × 每行重复):对齐后端 dispatch 侧
 * MAX_RUNS_PER_EXECUTION(app/core/config.py)的 409 too_many_runs。
 * 后端已按 rows × injection_entries × n_runs 聚合拦截(§1.7 复核);
 * 这里的常量只是它的前端镜像,用于提前拦 + 预览告警。 */
export const MAX_TOTAL_RUNS = 200

/** 行级显式绑定(D3,confirm 下发与另存快照同口径):预填未改动的
 * 声明 URL 不算显式绑定(否则 confirm 重送成覆盖、快照钉死旧声明
 * URL);未声明行任何非空 URL 都是救燃绑定。非显式行返回 undefined。 */
export function explicitBindingOf(
  b: ServiceBinding | undefined,
  declared: string | null,
): ServiceBinding | undefined {
  const url = b?.url?.trim()
  const effectiveUrl = url && url !== declared ? url : undefined
  const authAlias = b?.authAlias || undefined
  if (!authAlias && !effectiveUrl) return undefined
  return {
    ...(authAlias ? { authAlias } : {}),
    ...(effectiveUrl ? { url: effectiveUrl } : {}),
  }
}

/** 装配显式绑定记录:空绑定条目不落(confirm 下发与另存快照共用;
 * 后端注入清单 = 模板扫描(steps 里 ${auth.*} 引用)∪ 绑定 authAlias)。 */
export function assembleExplicitBindings(
  bindings: Record<string, ServiceBinding>,
  serviceRows: ServiceRow[],
): Record<string, ServiceBinding> {
  const out: Record<string, ServiceBinding> = {}
  for (const row of serviceRows) {
    const eb = explicitBindingOf(bindings[row.service], row.declaredUrl)
    if (eb) out[row.service] = eb
  }
  return out
}

/** 降级口径(spec §9):alias 非空且已不在凭证选项(凭证被删)。
 * 两态共用 — 编辑中的 bindings 与方案存量 serviceBindings 都传 alias 进来;
 * 标红警示,不阻塞运行。 */
export function degradedAlias(
  alias: string | undefined,
  authOptions: readonly string[],
): boolean {
  return !!alias && !authOptions.includes(alias)
}

/** 概要行数:段带 rowIndexes 按段计,缺省段 = 整库(空库按 1 隐式行) */
export function schemeRowsTotal(
  s: SchemeV2,
  dataSets: readonly DataSetSummary[],
): number {
  return s.dataSetSelection.reduce((n, x) =>
    n + (x.rowIndexes?.length
      ?? Math.max(dataSets.find((d) => d.datasetId === x.datasetId)?.rowCount ?? 0, 1)), 0)
}

export function datasetLabel(
  x: { datasetId: string },
  dataSets: readonly DataSetSummary[],
): string {
  return dataSets.find((d) => d.datasetId === x.datasetId)?.name ?? x.datasetId
}

/** 活条目集:registry 全集 − 宿主门控后的死集(deadEntryIds 来自
 * useInjectableSurface.deadIds —— 契约在途时「尚未判定」≠「判死」,
 * 掩空决策没有第二个落点)。legacy 旧形状条目恒不活。 */
export function liveEntryIdSet(
  assertionEntries: readonly (AssertionEntry | LegacyAssertionEntry)[],
  deadEntryIds: readonly string[],
): Set<string> {
  const dead = new Set(deadEntryIds)
  return new Set(assertionEntries
    .filter((e) => !isLegacyEntry(e) && !dead.has(e.id))
    .map((e) => e.id))
}

/** 自建方案失效判定(spec §9):引用数据集已删 or 注入条目不在活集。 */
export function isSchemeInvalid(
  s: SchemeV2,
  dataSets: readonly DataSetSummary[],
  liveEntries: ReadonlySet<string>,
): boolean {
  return s.dataSetSelection.some((x) => !dataSets.some((d) => d.datasetId === x.datasetId))
    || s.injectionEntryIds.some((id) => !liveEntries.has(id))
}

/** 失效原因(只报第一因,横幅一行放得下) */
export function schemeInvalidReason(
  s: SchemeV2,
  dataSets: readonly DataSetSummary[],
): string {
  const deadDs = s.dataSetSelection.filter((x) => !dataSets.some((d) => d.datasetId === x.datasetId))
  if (deadDs.length) return `数据集 ${deadDs.map((x) => x.datasetId).join('、')} 已删除`
  return '注入条目已悬空或删除'
}
