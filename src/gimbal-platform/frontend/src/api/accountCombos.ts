/**
 * api/accountCombos.ts — 账户组合 API client(账户组合设计方案 §5,定稿 05)。
 *
 * 组合 = 服务 → 已登记身份条目的映射集({service, alias} 一条一服务),
 * 跨场景复用的基础默认身份层;场景经绑定端点**引用**(改动传播),
 * definition.config.accountCombo 为服务端托管键 —— 不进编排器 draft,
 * 整稿 PUT 恒被后端剥除,唯一写通道 = bindScenarioCombo。
 *
 * scope 两型:个人(全员建,属主单判)/ 项目(读=成员任一角色,
 * 写=WRITER_ROLES;公共项目不建)。删除被引用组合 → 409
 * account_combo_in_use(先解绑再删)。
 */
import http from '@/api/http'

/** 组合条目:服务键 → 身份条目名(一条一服务,§2.1) */
export interface ComboEntry {
  service: string
  alias: string
}

export interface AccountComboRow {
  id: number
  scope: 'user' | 'project'
  scopeId: number
  name: string
  description?: string
  isDefault: boolean
  revision: number
  entries: ComboEntry[]
  /** 被引用场景数(编辑/删除前差异确认,§5.1) */
  referenceCount: number
  updatedAt?: string | null
  updatedByName?: string | null
}

export interface AccountComboList {
  personal: AccountComboRow[]
  projects: {
    projectId: number
    projectName: string
    items: AccountComboRow[]
  }[]
}

export interface AccountComboCreateInput {
  name: string
  description?: string
  entries?: ComboEntry[]
  isDefault?: boolean
  scope?: 'user' | 'project'
  projectId?: number
}

export interface AccountComboUpdateInput {
  name?: string
  /** 缺省 = 不改;显式值(含 "")覆盖 */
  description?: string
  /** 缺省 = 不改;整体替换式(仅条目实质变化后端 revision +1) */
  entries?: ComboEntry[]
}

/** 场景侧绑定读取(GET /scenarios/{sid}/account-combo):
 *  未绑 = {comboId: null};组合行被并发删除(删除有 in-use 闸,仅竞态
 *  可达)= {comboId, comboMissing: true} */
export interface ScenarioComboBinding {
  comboId: number | null
  comboMissing?: boolean
  name?: string
  scope?: 'user' | 'project'
  revision?: number
  entries?: ComboEntry[]
}

/** 列表(scope 分组:个人 = 本人;项目 = 我所在的普通项目,成员任一
 *  角色);?projectId 只看该项目(非成员 404 不泄露) */
export function listAccountCombos(
  projectId?: number,
): Promise<AccountComboList> {
  return http.get<AccountComboList>('/account-combos', {
    params: projectId != null ? { projectId } : {},
  }).then(({ data }) => data)
}

export function createAccountCombo(
  body: AccountComboCreateInput,
): Promise<AccountComboRow> {
  return http.post<AccountComboRow>('/account-combos', body)
    .then(({ data }) => data)
}

export function getAccountCombo(id: number): Promise<AccountComboRow> {
  return http.get<AccountComboRow>(`/account-combos/${id}`)
    .then(({ data }) => data)
}

/** 合并式 PATCH:None=不改;条目整体替换(保存面全量校验:
 *  binding_alias_unknown / binding_alias_mismatch / 形状与重复
 *  account_combo_entry_invalid) */
export function updateAccountCombo(
  id: number,
  body: AccountComboUpdateInput,
): Promise<AccountComboRow> {
  return http.patch<AccountComboRow>(`/account-combos/${id}`, body)
    .then(({ data }) => data)
}

/** 置为默认(语义 = 「推荐默认」:新建场景预选,不静默自动写入) */
export function setDefaultAccountCombo(id: number): Promise<AccountComboRow> {
  return http.post<AccountComboRow>(`/account-combos/${id}/set-default`)
    .then(({ data }) => data)
}

/** 删除:被引用 → 409 account_combo_in_use(detail.scenarios 带清单) */
export function deleteAccountCombo(id: number): Promise<void> {
  return http.delete(`/account-combos/${id}`).then(() => undefined)
}

/** 读取通道:当前绑定(comboId + 名称/revision/条目摘要) */
export function getScenarioCombo(
  scenarioId: string,
): Promise<ScenarioComboBinding> {
  return http.get<ScenarioComboBinding>(
    `/scenarios/${encodeURIComponent(scenarioId)}/account-combo`)
    .then(({ data }) => data)
}

/** v1 唯一应用入口 = 编排器:绑定/切换/解除一步改引用,不动方案绑定
 *  与步骤;跨区 → 422 account_combo_scope_mismatch,组合不可读 →
 *  422 account_combo_not_found(场景侧双态) */
export function bindScenarioCombo(
  scenarioId: string,
  comboId: number | null,
): Promise<ScenarioComboBinding> {
  return http.post<ScenarioComboBinding>(
    `/scenarios/${encodeURIComponent(scenarioId)}/account-combo`,
    { comboId },
  ).then(({ data }) => data)
}
