/**
 * service-alias.ts — 服务别名前缀派生(spec 2026-08-27 D5)
 *
 * 别名 = <目录服务名>-<后缀>,"-" 为唯一分隔符,后缀非空不含 "-"。
 * 切分点固定在最后一个 "-":不搜索前缀、不按最长匹配 — 目录名自身可含
 * "-"(如 fin-service、fin-order-service)或 "."(如 fin.tidb-test),
 * 最后一切分保证 base 永远是可能的最长目录名候选。
 *
 * deriveBase 是纯视图函数:目录名集合是唯一外部输入,集合清空 → 全部
 * 返回 null(裸声明降级),执行与导出零影响(酸性测试,spec §1.1)。
 */

/** key ∈ 目录集合 → key(目录名直引);否则最后 "-" 切分,base ∈ 集合 → base;
 *  否则 null(裸声明,不猜)。 */
export function deriveBase(key: string, catalogNames: ReadonlySet<string>): string | null {
  if (!key) return null
  if (catalogNames.has(key)) return key
  const i = key.lastIndexOf('-')
  if (i <= 0) return null
  const base = key.slice(0, i)
  return catalogNames.has(base) ? base : null
}
