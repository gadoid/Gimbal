/**
 * identityResolve.ts — 身份条目 → 本人池账户行的前端解析单源。
 *
 * 语义镜像后端 ``run_prepare._resolve_identities/_pick_one``(redesign
 * §8.3:引用不校验标签):default ref = system 唯一默认账户(0059 起
 * (池, system) 唯一,跨标签共用是正常形态);username ref = 同标签
 * 唯一优先 → system 内唯一回落;多候选且无同标签唯一命中 = 歧义,
 * 返回 undefined(页面按「缺账户/未装载」呈现,与后端
 * account_ambiguous 的执行后果同观感)。
 *
 * 2026-11-19 收敛缘由:此前 ServiceAdmin.accountOf 与
 * ExecConfigsView.accountRowOf 各写一份、且都多绑了
 * 「账户 env == 条目 env」等式 —— 系统默认账户在 A 标签、条目在 B
 * 标签时执行能解析、页面报缺(系统性假缺报)。两页装载判定/拨测
 * 目标/摘要计数统一走本实现;后端推解析端点仍是后续可选增强。
 */
export interface AccountLikeRow {
  /** 各页账户行形状宽进(system/envId 可空 = 旧数据/未加载态,比较按严格等) */
  system?: string | null
  envId?: number | null
  username?: string | null
  isDefault?: boolean | null
}

export interface IdentityRefLike {
  envId?: number | null
  refMode?: string | null
  refUsername?: string | null
}

export function pickAccountLikeBackend<T extends AccountLikeRow>(
  accounts: T[],
  system: string,
  entry: IdentityRefLike,
): T | undefined {
  if (!system) return undefined
  // FE-04(2026-11-20 审计):镜像后端 _pick_one 的边缘值语义 ——
  // refMode=username 但 refUsername 为空(存量旧值;写面已拒新增)
  // 按默认位回落,不再按空名恒 miss 报「缺账户」。
  const usernameRef = entry.refMode === 'username'
    && !!(entry.refUsername ?? '').trim()
  const cands = accounts.filter((a) => a.system === system
    && (usernameRef
      ? a.username === entry.refUsername
      : a.isDefault === true))
  const sameTag = cands.filter((a) => a.envId === entry.envId)
  return sameTag.length === 1 ? sameTag[0]
    : cands.length === 1 ? cands[0] : undefined
}
