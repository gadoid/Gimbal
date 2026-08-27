/**
 * service-alias.ts — 服务别名前缀派生(spec 2026-08-27 D5)
 *
 * 别名 = <目录服务名>-<后缀>,"-" 为唯一分隔符;后缀非空不含 "-" 时
 * (spec §1.3 命名约定,创建期拦截),别名内最后一个 "-" 必是分隔符,
 * 最后一切分即命中 — 本函数对一切规整别名与「固定最后 "-" 切分」逐例
 * 等价。目录名自身可含 "-"(如 fin-service、fin-order-service)或
 * "."(如 fin.tidb-test),候选集只取 key 按 "-" 切出的前缀,从最后
 * 一个 "-" 向左逐个尝试(最长候选优先):base 永远是可能的最长目录名
 * 候选(测试:fin-order-service-x-1 → fin-order-service;绝不切成 fin)。
 *
 * 仅做目录名集合的精确成员判定:永远不返回集合外的名字(不猜);不扫描
 * 任意子串前缀 — fin-x 的 fin 不在集合 → null(不搜索前缀)。多段后缀
 * (后缀自身含 "-")的违规键会回落到最长在册前缀而非裸声明。
 *
 * deriveBase 是纯视图函数:目录名集合是唯一外部输入,集合清空 → 全部
 * 返回 null(裸声明降级),执行与导出零影响(酸性测试,spec §1.1)。
 */

/** key ∈ 目录集合 → key(目录名直引);否则按 "-" 切出的前缀从最后一个
 *  "-" 向左(最长优先)找第一个 ∈ 集合的 base;无 → null(裸声明,不猜)。 */
export function deriveBase(key: string, catalogNames: ReadonlySet<string>): string | null {
  if (!key) return null
  if (catalogNames.has(key)) return key
  let i = key.lastIndexOf('-')
  while (i > 0) {
    const base = key.slice(0, i)
    if (catalogNames.has(base)) return base
    i = key.lastIndexOf('-', i - 1)
  }
  return null
}
