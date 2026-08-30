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
 *
 * deriveSystem 是系统不匹配黄警(spec §5.1/§9)的 step 系统派生:
 * 服务名 ≠ 系统名(fin-service 是服务,系统是 fin),按权威源优先 —
 * ① step 自带 view_hints.endpoint_id 首段(点语法 `{system}.*`);
 * ② 目录 service→system 映射(endpoint 条目自带 system 字段);
 * ③ 降级为原点前缀启发式(目录不可达时维持现状黄警,不猜新值)。
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

/** deriveSystem 的 step.api 最小结构(StepView.api 的结构性子集)。 */
interface ApiLike {
  service?: string
  view_hints?: { endpoint_id?: string }
}

/** step.api → 系统名;无 service 返回 null(调用方跳过该 step)。 */
export function deriveSystem(
  api: ApiLike | null | undefined,
  catalogNames: ReadonlySet<string>,
  systemByService: ReadonlyMap<string, string>,
): string | null {
  const svc = api?.service || ''
  if (!svc) return null
  // ① endpoint_id 首段 — step 自带,最权威(点语法 `{system}.{service}.{name}`)
  const eid = api?.view_hints?.endpoint_id
  if (eid && eid.includes('.')) return eid.split('.')[0]
  // ② 别名归 base 后查目录权威映射(fin-service → fin)
  const base = deriveBase(svc, catalogNames)
  const mapped = (base !== null && systemByService.get(base))
    ?? systemByService.get(svc)
  if (mapped) return mapped
  // ③ 降级:原点前缀启发式(点名取首段;中划线名原样 — 黄警仍在)
  return svc.includes('.') ? svc.split('.')[0] : svc
}
