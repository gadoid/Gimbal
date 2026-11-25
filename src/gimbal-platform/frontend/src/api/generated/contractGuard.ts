/**
 * contractGuard.ts — B5 治本切片 1:手写类型 ↔ 生成契约的编译期对账。
 *
 * 生成的 openapi.ts 是后端契约快照的直译(Any 字段 → unknown,比手写
 * 宽);手写类型是前端消费面(更窄、带语义注释)。本文件用 assignability
 * 断言钉住「手写声明的每个形状都存在于生成形状」—— 后端改字段名/
 * 可空性而前端手写类型没跟上时,这里在 vue-tsc 编译期变红(而非运行
 * 时 undefined 静默漂移)。
 *
 * 断言方向:`const _x: GeneratedOut = handwrittenValue`(手写 ⊆ 生成)。
 * 手写比生成**多**的字段(前端自加的投影/计算面)不检查 —— 那是合法
 * 的客户端扩展;手写比生成**窄**的类型(union 收窄、null 收紧)是合法
 * 子类型,放行。
 *
 * 逐域接入:本文件先挂 executions 域(示范位);其余域按批次追加
 * 断言块(登记册 B5 切片 2+)。生成物勿手改 —— 重跑
 * `python scripts/gen_frontend_contract.py`。
 */
import type {
  Execution,
  ExecutionListEnvelope,
  ExecutionListItem,
  ExecutionRow,
  ExecutionsSummary,
} from '@/api/executions'
import type {
  SuiteDetail,
  SuiteLookupItem,
  SuiteMemberItem,
  SuitePage,
  SuiteSummary,
} from '@/api/suites'
import type { ProjectMember, ProjectOut } from '@/api/projects'
import type { UserOut, UsersPage } from '@/api/users'
import type { AuthReferences, AuthsPage } from '@/api/auth_sessions'
import type {
  AccountComboCreate,
  AccountComboUpdate,
  AccountComboView,
  AuthListOut,
  AuthReferencesOut,
  ComboEntry as ComboEntryG,
  ExecutionListItemOut,
  ExecutionListOut,
  ExecutionOut,
  ExecutionRowOut,
  ExecutionSummaryOut,
  MemberOut,
  ProjectOut as ProjectOutG,
  SuiteDetailOut,
  SuiteLookupItem as SuiteLookupItemOut,
  SuiteMemberOut,
  SuitePageOut,
  SuiteSummaryOut,
  UserListOut,
  UserPublic,
} from './openapi'
import type {
  AccountComboCreateInput,
  AccountComboRow,
  AccountComboUpdateInput,
  ComboEntry,
} from '@/api/accountCombos'

// ── executions 域 ──────────────────────────────────────────────
declare const _execution: Execution
const _g1: ExecutionOut = _execution

declare const _listItem: ExecutionListItem
const _g2: ExecutionListItemOut = _listItem

declare const _envelope: ExecutionListEnvelope
const _g3: ExecutionListOut = _envelope

declare const _row: ExecutionRow
const _g4: ExecutionRowOut = _row

declare const _summary: ExecutionsSummary
const _g5: ExecutionSummaryOut = _summary

// ── suites 域(切片 2)───────────────────────────────────────────
// 契约面只有这 5 个 response schema(SuiteRunItem/ValidateOut/RevConflict
// 等是前端投影/内联形状,无契约 schema,不适用本断言方向)。
// latestRun 字段 = 后端 Any → Record<string,unknown>,手写 SuiteLatestRun
// 接口无索引签名 —— 对该字段以 Omit 摘除后钉其余字段(known Any 面;
// items 元素经 _s1 覆盖,信封其余分页字段照钉)。
declare const _suiteSummary: SuiteSummary
const _s1: Omit<SuiteSummaryOut, 'latestRun'> = _suiteSummary

declare const _suitePage: SuitePage
const _s2: Omit<SuitePageOut, 'items'> = _suitePage

declare const _suiteDetail: SuiteDetail
const _s3: Omit<SuiteDetailOut, 'latestRun'> = _suiteDetail

declare const _suiteMember: SuiteMemberItem
const _s4: SuiteMemberOut = _suiteMember

declare const _suiteLookup: SuiteLookupItem
const _s5: SuiteLookupItemOut = _suiteLookup

// ── projects / users / auth_sessions 域(切片 3)───────────────────
declare const _project: ProjectOut
const _p1: ProjectOutG = _project

declare const _projectMember: ProjectMember
const _p2: MemberOut = _projectMember

declare const _user: UserOut
const _u1: UserPublic = _user

declare const _usersPage: UsersPage
const _u2: UserListOut = _usersPage

declare const _authRefs: AuthReferences
const _a1: AuthReferencesOut = _authRefs

declare const _authsPage: AuthsPage
const _a2: AuthListOut = _authsPage

// ── account-combos 域(账户组合批 4,2026-11-25)──────────────────
// 手写 AccountComboRow ⊆ 生成 AccountComboView;Create/Update 入参形状
// 与生成 schema 对向钉(ComboEntry 双侧)。绑定端点响应是内联形状
// (无契约 schema),不适用本断言方向。
declare const _comboRow: AccountComboRow
const _c1: AccountComboView = _comboRow

declare const _comboEntry: ComboEntry
const _c2: ComboEntryG = _comboEntry

declare const _comboCreate: AccountComboCreateInput
const _c3: AccountComboCreate = _comboCreate

declare const _comboUpdate: AccountComboUpdateInput
const _c4: AccountComboUpdate = _comboUpdate

// 编译期防未使用告警(guards 是纯类型层,无运行时产物)
export const CONTRACT_GUARD_DOMAINS = [
  'executions', 'suites', 'projects', 'users', 'auth_sessions',
  'account_combos',
] as const
void [_g1, _g2, _g3, _g4, _g5, _s1, _s2, _s3, _s4, _s5,
  _p1, _p2, _u1, _u2, _a1, _a2, _c1, _c2, _c3, _c4]
