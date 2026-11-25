/**
 * 账户组合 API:组合是服务 → 已登记身份条目的映射,运行方案经
 * payload.accountComboId 引用;组合改动对引用方案下次执行生效。
 */
import http from '@/api/http'

export interface ComboEntry {
  service: string
  alias: string
}

export interface AccountComboSchemeRef {
  comboId: number
  schemeId: string
  schemeName: string
  scenarioId: string
  scenarioName: string
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
  referenceCount: number
  schemes: AccountComboSchemeRef[]
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

export interface ComboReadinessEntry {
  service: string
  alias: string
  baseService: string
  system?: string | null
  identityEnvId?: number | null
  refMode: string
  refUsername?: string | null
  poolStatus: 'ok' | 'missing' | 'ambiguous'
  accountId?: number | null
  accountUsername?: string | null
  accountEnvId?: number | null
  envMismatch: boolean
}

export interface ComboAddressRow {
  service: string
  envId: number
  envName: string
  baseUrl: string
  loginUrl: string
  deploymentId?: number | null
  resolved: boolean
}

export interface AccountComboReadiness {
  credentialSource: 'personal' | 'project'
  projectId?: number | null
  poolName: string
  canProbeCredentials: boolean
  environmentId?: number | null
  environmentName?: string | null
  environmentSource?: string | null
  envError?: string | null
  ready: boolean
  entries: ComboReadinessEntry[]
  addresses: ComboAddressRow[]
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
  description?: string
  entries?: ComboEntry[]
}

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

export function getAccountComboReadiness(
  id: number,
  credentialSource: 'personal' | 'project',
): Promise<AccountComboReadiness> {
  return http.get<AccountComboReadiness>(`/account-combos/${id}/readiness`, {
    params: { credential_source: credentialSource },
  }).then(({ data }) => data)
}

export function updateAccountCombo(
  id: number,
  body: AccountComboUpdateInput,
): Promise<AccountComboRow> {
  return http.patch<AccountComboRow>(`/account-combos/${id}`, body)
    .then(({ data }) => data)
}

/** 默认只用于新建/另存方案预选,不参与解析。 */
export function setDefaultAccountCombo(id: number): Promise<AccountComboRow> {
  return http.post<AccountComboRow>(`/account-combos/${id}/set-default`)
    .then(({ data }) => data)
}

/** 被方案引用时返回 409 account_combo_in_use,detail.schemes 带清单。 */
export function deleteAccountCombo(id: number): Promise<void> {
  return http.delete(`/account-combos/${id}`).then(() => undefined)
}
