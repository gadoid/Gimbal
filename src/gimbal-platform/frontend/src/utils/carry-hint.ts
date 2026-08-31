/**
 * carry-hint.ts — step 卡 carry 只读提示的纯核心(spec §5)。
 *
 * 输入:字段面(face,plate /full 的 request.carry 键集)与两层值表
 * (服务绑定 bound / 全局默认 defaults);输出 path → 来源标签。
 *
 * 语义对齐值表两层模型(spec §3.1):
 * - 键缺席 = 未配置 → 不进 Map(运行时无值可注入,不提示);
 * - null 值 = 显式 null 行 → 算已配置(绑定层显式屏蔽默认,仍是来源);
 * - 服务绑定优先于全局默认(与运行时注入同序:bound 覆盖 defaults)。
 *
 * 纯函数:Canvas 的 carryInjectable 只做数据接线(/full 缓存 + 目录
 * 别名派生),交集与优先级规则全部收敛在此 — 单测不挂 Vue。
 */

/** carry 值表两层通用形状:dict 的 null = 显式 null 行,键缺席 = 未配置。 */
export type CarryValues = Record<string, string | null>

/** 来源标签:绑定层(服务绑定)覆盖默认层(全局默认)。 */
export type CarrySource = '服务绑定' | '全局默认'

/** face ∩ (bound ∪ defaults) → Map<path, 来源>;同键命中两层时绑定优先。 */
export function carryHint(
  face: readonly string[],
  bound: CarryValues,
  defaults: CarryValues,
): Map<string, CarrySource> {
  const out = new Map<string, CarrySource>()
  for (const p of face) {
    if (p in bound) out.set(p, '服务绑定')
    else if (p in defaults) out.set(p, '全局默认')
  }
  return out
}
