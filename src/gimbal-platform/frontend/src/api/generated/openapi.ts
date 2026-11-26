// 由 scripts/gen_frontend_contract.py 从 backend/contract/openapi.json
// 生成 —— 勿手改;单源事实在后端契约快照(gen_api_contract.py)。
// 切换策略:api/*.ts facade re-export,组件 import 面零改动。

export interface ActivityEvent {
  action?: unknown | null
  at: unknown
  batchId?: unknown | null
  clientRef?: unknown | null
  detail?: Record<string, unknown> | null
  endpointId?: unknown | null
  executionId?: number | null
  fromVersion?: unknown | null
  kind: "execution" | "scenario" | "adaptation" | "suite" | "integration" | "inbound"
  module?: unknown | null
  name?: unknown | null
  opCount?: number | null
  scenarioId?: unknown | null
  scenarioName?: unknown | null
  status?: unknown | null
  suiteId?: number | null
  taskId?: number | null
  toVersion?: unknown | null
  tokenId?: number | null
  tokenName?: unknown | null
}

export interface ActivityOut {
  events?: Array<ActivityEvent>
  sources?: Record<string, boolean>
}

export interface AliasCreate {
  aliasName: unknown
  baseService?: unknown | null
  display?: unknown
  envId?: number | null
  kind?: "plate" | "external"
  refUsername?: unknown
  ref_mode?: "default" | "username"
}

// M4 Page 信封(§6.3)。
export interface AliasListOut {
  items: Array<AliasOut>
  page?: number
  pageSize?: number
  total?: number
}

export interface AliasOut {
  aliasName: unknown
  baseService: unknown
  createdAt?: unknown | null
  display?: unknown
  envId?: number | null
  kind?: unknown
  refMode?: unknown
  refUsername?: unknown | null
  slot?: unknown | null
  updatedAt?: unknown | null
}

export interface AliasPatch {
  baseService?: unknown | null
  display?: unknown | null
  kind?: "plate" | "external" | null
  refMode?: "default" | "username" | null
  refUsername?: unknown | null
}

export interface AnalyzeIn {
  kind: "scenario" | "suite"
  sourceId: unknown
}

export interface AnnouncementIn {
  body?: unknown
  hours?: number
  title: unknown
}

export interface ApproveIn {
  decisions?: Array<DecisionIn>
}

export interface AuditLogOut {
  action: unknown
  actorId?: number | null
  actorName?: unknown
  createdAt: unknown
  detail?: Record<string, unknown>
  id: number
  resourceId?: unknown | null
  resourceType?: unknown | null
}

// M4 Page 信封(§6.3)+ 可过滤动作词表。
export interface AuditLogPage {
  actions?: Array<unknown>
  items: Array<AuditLogOut>
  page?: number
  pageSize?: number
  total?: number
}

// 账户登记:system/env 必填(登录打到具体环境实例);登录口不收
// (在实例上)。
export interface AuthAccountCreateIn {
  accountFields?: Record<string, unknown>
  envId: number
  expires_in?: number
  isDefault?: boolean
  password: unknown
  system: unknown
  token_type?: unknown
  username: unknown
}

// 账户行的对外视图(password 恒掩码;解密注入由服务端完成)。
export interface AuthAccountOut {
  accountFields?: Record<string, unknown>
  created_at: unknown
  envId: number
  expires_in?: number
  id: number
  identityRefCount?: number
  isDefault?: boolean
  loginUrl?: unknown
  password_masked?: unknown
  scenarioRefCount?: number
  source?: "personal" | "project"
  system: unknown
  token_type?: unknown
  updated_at: unknown
  username: unknown
}

// username 不可改(账户实体键;换账号 = 删旧建新);system/env 改动
// 即换实体坐标(整账户迁移到另一系统/环境)。
export interface AuthAccountPatchIn {
  accountFields?: Record<string, unknown> | null
  envId?: number | null
  expires_in?: number | null
  isDefault?: boolean | null
  password?: unknown | null
  system?: unknown | null
  token_type?: unknown | null
}

// include_secrets=true 时的详情视图 — 附解密后的明文 password。
// 
// 仅限内网测试环境的策略放宽(2026-08-25 认证改造设计):场景配置页
// "从凭证池导入"需要把明文快照拷进 config.users(导出在前端本地拼装,
// 明文必须过客户端)。列表接口行为不变,不带密。
export interface AuthAccountSecretsOut {
  accountFields?: Record<string, unknown>
  created_at: unknown
  envId: number
  expires_in?: number
  id: number
  identityRefCount?: number
  isDefault?: boolean
  loginUrl?: unknown
  password: unknown
  password_masked?: unknown
  scenarioRefCount?: number
  source?: "personal" | "project"
  system: unknown
  token_type?: unknown
  updated_at: unknown
  username: unknown
}

// 调用身份草稿(保存期通道;架构一致性收窄)。
// 
// 只建 **username-ref 身份条目**,不创建账户、不碰密码 —— 凭证是
// 独立资产,由 ``POST /auths`` 即时写入本人池/项目池;身份是全局
// 声明,Admin 走 ``POST /service-aliases``,非 Admin 随场景保存
// 同事务建 username-ref 条目(本通道)。
export interface AuthDraftIn {
  baseService: unknown
  display?: unknown
  envId: number
  name: unknown
  username: unknown
}

// M4 Page 信封 + 全量类型计数(metaText 的服务端供给)。
export interface AuthListOut {
  items: Array<AuthAccountOut>
  page?: number
  pageSize?: number
  tokenTypeCounts?: Record<string, number>
  total?: number
}

// GET /auths/{id}/references(账户引用反查):ref 条目清单 + 场景
// 引用(经条目名聚合,实时扫,不建反向索引)。
export interface AuthReferencesOut {
  identityRefs?: Array<IdentityRefItem>
  scenarioRefs?: ScenarioRefsOut
}

export interface BatchDetail {
  batchId: unknown
  carryScope?: unknown | null
  carryScopeId?: number | null
  closedAt?: unknown | null
  createdAt: unknown
  endpointId: unknown
  endpointMethod?: unknown
  endpointName?: unknown
  endpointPath?: unknown
  fromVersion: unknown
  opCounts?: Record<string, number>
  operatorId: number
  ops?: Array<OpOut>
  snapshots?: Array<SnapshotRef>
  status: unknown
  toVersion: unknown
}

// M4 Page 信封(§6.3)。
export interface BatchListOut {
  items: Array<BatchOut>
  page?: number
  pageSize?: number
  total?: number
}

export interface BatchOut {
  batchId: unknown
  carryScope?: unknown | null
  carryScopeId?: number | null
  closedAt?: unknown | null
  createdAt: unknown
  endpointId: unknown
  endpointMethod?: unknown
  endpointName?: unknown
  endpointPath?: unknown
  fromVersion: unknown
  opCounts?: Record<string, number>
  operatorId: number
  status: unknown
  toVersion: unknown
}

// 批量提交入参（§5.3 直接切换/字段级的多场景聚合）。
export interface BatchSubmitIn {
  reviewConfirmed?: boolean
  scenarioIds: Array<unknown>
  system?: unknown | null
  targetRevision: unknown
}

// S4 列表行级层标签(flat bindings 之外的可见层明细)。
// ``serviceName`` = config_key(键域三级:条目/服务/系统,字段名沿
// 旧兼容);环境覆盖维已退役(§8.4,2026-11-17)。
export interface BindingRowOut {
  fieldPath: unknown
  scope: unknown
  scopeId: number
  serviceName: unknown
  value?: unknown | null
}

export interface BindingsOut {
  bindings?: Record<string, Record<string, unknown | null>>
  rows?: Array<BindingRowOut>
}

export interface BoardEdge {
  from: unknown
  kind: "contains" | "refs" | "affects" | "ran" | "annotates"
  to: unknown
}

export interface BoardNode {
  id: unknown
  kind: "endpoint" | "table" | "topology" | "reference" | "scenario" | "execution" | "adaptation" | "card"
  label: unknown
  meta?: Record<string, unknown>
  quadrant?: "requirement" | "data" | "test" | "topology" | null
}

export interface BoardResponse {
  edges?: Array<BoardEdge>
  nodes?: Array<BoardNode>
  quadrants?: Record<string, unknown>
  subject: BoardSubject
  trails?: Array<BoardTrail>
}

export interface BoardSubject {
  degraded?: boolean
  fieldCount?: number
  id: unknown
  method?: unknown
  name?: unknown
  path?: unknown
  version?: unknown
}

export interface BoardTrail {
  kind: unknown
  path: Array<unknown>
}

export type Bracket = "before" | "after" | "main"

export interface CallbackIn {
  url?: unknown | null
}

export interface CardCreate {
  annotatesNodeId?: unknown | null
  body: unknown
  quadrant: "requirement" | "data" | "test" | "topology"
  subjectId: unknown
}

export interface CardOut {
  annotatesNodeId?: unknown | null
  authorId: number
  body: unknown
  createdAt?: unknown | null
  id: number
  isRoot?: boolean
  quadrant: "requirement" | "data" | "test" | "topology"
  subjectId: unknown
  subjectKind: unknown
  updatedAt?: unknown | null
}

export interface CardPatch {
  annotatesNodeId?: unknown | null
  body?: unknown | null
  quadrant?: "requirement" | "data" | "test" | "topology" | null
}

export interface CardsIn {
  ids: Array<unknown>
}

// POST /adaptations/carry-batches 请求体(spec §7):service 缺省 = 全局默认表。
// 
// S7.6:scope/projectId = 值表作用域(缺省 = 公共项目层;project 层
// 需 projectId;分权与 carry 写面同口径)。
export interface CarryBatchIn {
  projectId?: number | null
  scope?: unknown | null
  service?: unknown | null
}

// face 行的贡献端点上下文(G6):字段属于服务内哪个接口。
export interface CarryEndpointMini {
  id: unknown
  method?: unknown
  name?: unknown
  path?: unknown
}

export interface CarryFieldFace {
  description?: unknown
  endpoints?: Array<CarryEndpointMini>
  path: unknown
  type?: unknown
}

export interface CarryMapIn {
  bindings?: Record<string, unknown | null>
}

export interface CatalogEndpointRef {
  id: unknown
  service: unknown
}

export interface CatalogServiceRow {
  endpointCount: number
  kind?: unknown
  name: unknown
  system: unknown
}

export interface CatalogServicesOut {
  endpoints: Array<CatalogEndpointRef>
  plateReachable?: boolean
  services: Array<CatalogServiceRow>
}

export interface ChangePasswordIn {
  invalidateTokens?: boolean
  logoutOthers?: boolean
  new_password: unknown
  old_password: unknown
}

export interface CheckDecl {
  on?: CheckSelector
  strategy: Record<string, unknown>
}

export interface CheckSelector {
  bracket?: Bracket | null
  refs?: Array<unknown>
  tags?: Array<unknown>
}

// composition 的成员行:顺序即列表顺序(聚合发起序/串联链路序/
// 扇出源在首位);role 见 suite_members.role。
export interface CompositionMemberIn {
  role?: "main" | "before" | "after"
  scenarioId: unknown
}

export interface ConstantEntryCreateIn {
  description?: unknown
  entry_kind: "literal" | "generator"
  name: unknown
  spec?: Record<string, unknown> | null
  value?: unknown
}

export interface ConstantEntryOut {
  created_at: unknown
  description: unknown
  entry_kind: "literal" | "generator"
  id: number
  name: unknown
  spec?: Record<string, unknown> | null
  updated_at: unknown
  value?: unknown
}

// PATCH 语义: None = 不改(与 auth_sessions 一致);校验依赖行的 entry_kind,在 router 层做。
export interface ConstantEntryPatchIn {
  description?: unknown | null
  spec?: Record<string, unknown> | null
  value?: unknown
}

// M4 Page 信封(§6.3):常量池列表从全量裸数组迁信封。
export interface ConstantListOut {
  items: Array<ConstantEntryOut>
  page?: number
  pageSize?: number
  total?: number
}

export interface CreateIn {
  kind: "scenario" | "suite"
  sourceId: unknown
}

export interface DataSet {
  datasetId: unknown
  description?: unknown
  name: unknown
  rowCount?: number
  rows?: Array<Record<string, unknown>>
  scenarioId: unknown
  varUnlocks?: Array<unknown>
}

// Request body for POST /scenarios/{scenarioId}/data-sets and PUT /data-sets/{id}.
export interface DataSetDraft {
  description?: unknown
  name: unknown
  rows?: Array<Record<string, unknown>>
  varUnlocks?: Array<unknown>
}

// 行级数据集选择(spec v3 §4):datasetId + rowIndexes(0-based,
// 与编辑器行号一致;缺省/空 = 整库)。RunRequest/RunScheme 的权威
// 选择键;旧 dataSetIds 保留为兼容读(两键同发本键优先)。
export interface DataSetSelection {
  datasetId: unknown
  rowIndexes?: Array<number>
}

// Lightweight view used in list endpoints (preview[0:3]).
export interface DataSetSummary {
  datasetId: unknown
  name: unknown
  preview?: Array<Record<string, unknown>>
  rowCount?: number
  scenarioId: unknown
}

// 一条调试会话命令(字段形状生成自执行器;成对红线手写)。
export interface DebugCommand {
  kind: Kind
  path?: unknown | null
  value?: unknown
  variable?: unknown | null
}

export interface DebugCommandOut {
  accepted: boolean
  output?: Array<unknown>
}

export interface DebugSpec {
  breakpoints?: Array<unknown>
  pause?: Pause
  wait_timeout?: number | null
}

export interface DecisionIn {
  path: unknown
  service: unknown
  sourceValue?: unknown | null
  use: "source" | "project"
}

export interface DefaultsIn {
  defaults?: Record<string, unknown | null>
}

export interface DefaultsOut {
  defaults?: Record<string, unknown | null>
  scope?: unknown | null
  scopeId?: number | null
}

export interface DeploymentIn {
  baseService: unknown
  baseUrl: unknown
  envId: number
}

export interface DeploymentOut {
  baseService: unknown
  baseUrl: unknown
  envId: number
  id: number
}

export interface DeploymentPatch {
  baseUrl: unknown
}

export interface DriftReport {
  plateReachable?: boolean
  scope?: unknown | null
  scopeId?: number | null
  services?: Array<ServiceDrift>
}

export interface EnvironmentCreate {
  description?: unknown
  lines?: Record<string, unknown>
  name: unknown
}

// 标签 → 环境定义(「标签即环境」)。
export interface EnvironmentResolveIn {
  name: unknown
}

export interface EnvironmentUpdate {
  description?: unknown | null
  lines?: Record<string, unknown> | null
  name?: unknown | null
}

export interface EnvironmentView {
  description: unknown
  id: number
  is_default?: boolean
  lines?: Record<string, unknown>
  name: unknown
  owner_id?: number | null
}

export interface ExecConfigCopyIn {
  name: unknown
}

export interface ExecConfigCreate {
  description?: unknown
  isDefault?: boolean
  name: unknown
  projectId?: number | null
  scope?: "user" | "project"
  systems?: Array<SystemSubConfig>
  tags?: Array<unknown>
}

export interface ExecConfigUpdate {
  description?: unknown | null
  name?: unknown | null
  systems?: Array<SystemSubConfig> | null
  tags?: Array<unknown> | null
}

export interface ExecConfigView {
  description?: unknown
  id: number
  isDefault: boolean
  name: unknown
  scope?: unknown
  systems: Array<SystemSubConfig>
  tags?: Array<unknown>
}

// 列表行形态(M1 响应投影,PG迁移方案 §2.2 债 4 补刀):去 ``config``
// —— ``config_json`` 是凭证引用面(injectedAuths/serviceBindings),整列
// 随每行列表下发是敏感面泄漏;详情页保留完整 ``config``。
// 
// ``config_summary`` 是列表 UI 既有的四个非敏感展示字段的窄投影
// (schemeName/nRuns/parallel/stepTo/authFailFast),不携带凭证引用。
export interface ExecutionListItemOut {
  baseline_block?: unknown | null
  baseline_eligible?: boolean
  batch_id?: unknown | null
  cancel_note?: unknown | null
  cancel_requested?: boolean
  cancelable?: boolean
  configSummary?: Record<string, unknown>
  consecutive_failures?: number
  failed: number
  finished_at: unknown | null
  has_scenario_snapshot?: boolean
  id: number
  kind?: unknown
  m2_hash?: unknown | null
  passed: number
  plate_pins?: Record<string, unknown> | null
  scenario_deleted?: boolean
  scenario_display_name?: unknown
  scenario_id: unknown
  skipped?: number
  started_at: unknown | null
  status: unknown
  suite_id?: number | null
  total_runs: number
}

// Page 信封(§4.1):既有 {items,total} 补齐 page/pageSize 即向后兼容。
// 
// ``failedTotal``:与 ``total`` 同筛选口径的失败单数 —— 前端
// 筛选行的「共 N 条 · 失败 M 条」原先 N 是全量、M 却只数当前页,分页后
// 口径打架;由服务端一次 count 给全口径值。
export interface ExecutionListOut {
  failedTotal?: number
  items: Array<ExecutionListItemOut>
  page?: number
  pageSize?: number
  total: number
}

export interface ExecutionOut {
  baseline_block?: unknown | null
  baseline_eligible?: boolean
  baseline_evidence?: Record<string, unknown> | null
  batch_id?: unknown | null
  cancel_note?: unknown | null
  cancel_requested?: boolean
  cancelable?: boolean
  client_ref?: unknown | null
  config: Record<string, unknown>
  consecutive_failures?: number
  current_plate?: Record<string, unknown> | null
  error?: unknown | null
  failed: number
  finished_at: unknown | null
  has_scenario_snapshot?: boolean
  id: number
  identity_mode?: unknown | null
  kind?: unknown
  m2_hash?: unknown | null
  ownerName?: unknown | null
  passed: number
  plate_pins?: Record<string, unknown> | null
  scenario_deleted?: boolean
  scenario_display_name?: unknown
  scenario_id: unknown
  skipped?: number
  started_at: unknown | null
  status: unknown
  suite_id?: number | null
  token_id?: number | null
  token_name?: unknown | null
  total_runs: number
}

// 行级状态(spec §9.1)— registry(asdict 的 snake_case)与 JSONL
// 回放(camelCase 键)两种输入都收(populate_by_name),响应按别名
// 序列化为 camelCase。
export interface ExecutionRowOut {
  caseDir?: unknown
  datasetId?: unknown | null
  datasetName?: unknown | null
  finishedAt?: unknown | null
  injectionId?: unknown | null
  rep?: number
  rowIndex?: number
  runError?: unknown | null
  seq: number
  serverSlot?: number | null
  startedAt?: unknown | null
  status: unknown
}

// M6(债 5):行级分页信封 —— {items,total,page,pageSize}。
export interface ExecutionRowsOut {
  items: Array<ExecutionRowOut>
  page?: number
  pageSize?: number
  total?: number
}

// 执行记录顶部 KPI 带(执行设计 §3.5/§4.1):Execution 计数器/时间戳
// 就能算的那部分 — 行级分布(耗时分布/失败原因构成)不落库,不在本
// 响应里(§0 纪律 3:跨执行聚合不出来,等行级落库)。口径 = 查询者自己
// 的执行(§5.1:执行的可见范围只有自己跑的,owner 隔离不因聚合放开)。
export interface ExecutionSummaryOut {
  activeExecutions?: number
  avgDurationSec?: number | null
  failedRuns?: number
  passRate?: number | null
  passedRuns?: number
  repeatFailureScenarios?: number
  todayExecutions?: number
  totalExecutions?: number
  totalRuns?: number
  windowDays?: number
}

// 导出/预览的运行方案覆盖层(spec §8)。dataSetIds 有意不收 —
// 导出是场景级产物,行级展开是非目标。环境显式位已随 §8.2 退役
// (导出地址按身份标签 > 项目默认 > 平台默认解析)。
export interface ExportOverlay {
  serviceBindings?: Record<string, ServiceBinding>
}

// §3.5 配置编辑校验入参:step 的 field_states 增量(可空)。
export interface FieldStatesValidateRequest {
  field_states?: Record<string, unknown>
}

export interface GateDecl {
  metric: Metric
  op?: Op
  value: number
}

// 编排裁剪控制(重构方案):only = 试跑选中段(所选单元 + 传递
// 上游,make 语义);toNode = 串联只跑到某一步。fromNode 刻意不收 ——
// 执行器 from_node 切片要求被跳过的上游输出由外部提供,平台无从提供。
export interface GraphControlSpec {
  only?: Array<unknown>
  toNode?: unknown | null
}

// C5:suite 编排执行规格(D-6 保留横切面:gates/checks 可选)。
export interface GraphSpec {
  after?: Array<GraphUnitSpec>
  before?: Array<GraphUnitSpec>
  checks?: Array<CheckDecl>
  control?: GraphControlSpec | null
  gates?: Array<GateDecl>
  mode?: "aggregate" | "compose" | "fanout" | "chain"
  nRuns?: number
  parallel?: number
  serviceBindings?: Record<string, ServiceBinding>
  units: Array<GraphUnitSpec>
}

// C5:编排单元 —— 一个平台场景在 graph 里的一个节点。
export interface GraphUnitSpec {
  injectionEntryIds?: Array<unknown>
  inputs?: Record<string, unknown>
  map?: Record<string, unknown>
  nRuns?: number
  needs?: Array<unknown>
  ref: unknown
  repeat?: number
  row?: Record<string, unknown> | null
  scenarioId: unknown
  schemeId?: unknown | null
  serviceBindings?: Record<string, ServiceBinding>
  shared?: unknown | null
}

export interface GridEndpoint {
  caseCount?: number
  id: unknown
  lastRunAt?: unknown | null
  method?: unknown
  name?: unknown
  path?: unknown
  signals?: GridSignals
}

// 四格状态条(§2.3)。位置固定:①需求 ②用例 ③最近执行 ④适配告警。
export interface GridSignals {
  alarm?: boolean
  cases?: boolean
  lastRun?: unknown | null
  req?: unknown | null
}

// 顶部统计条(§2.1)。`noRequirement` 随 P2 reference dim 再加。
export interface GridStats {
  hasAlarm?: number
  neverRun?: number
  noCases?: number
  total?: number
}

export interface GroupIn {
  bucket: "mine" | "public" | "project"
  filters?: Record<string, unknown>
  name: unknown
  projectId?: number | null
  q?: unknown
}

export interface GroupListOut {
  items: Array<GroupOut>
}

export interface GroupOut {
  createdAt?: unknown
  filters?: Record<string, unknown>
  id: unknown
  name: unknown
  q?: unknown
}

export interface HTTPValidationError {
  detail?: Array<ValidationError>
}

// 未读分享(悬浮标签数据源)。
// 
// 前端以 Set<resourceId> 维护,列表行渲染 O(1) 查找;销账走
// POST /read(按 id)。
export interface HandoffUnreadItem {
  id: number
  resourceId: unknown
  senderName?: unknown | null
}

export interface HandoffUnreadOut {
  items?: Array<HandoffUnreadItem>
}

export interface HolderIn {
  userId: number
}

// 反查面板 · 引用该账户的身份条目行。
export interface IdentityRefItem {
  aliasName: unknown
  baseService: unknown
  envId: number
  refMode?: unknown
  refUsername?: unknown | null
}

// 批量导入目录服务(空 = 全部未登记)。
export interface ImportCatalogIn {
  names?: Array<unknown>
}

// 导入结果:created / skipped(已登记或不在目录)+ 剩余未登记。
export interface ImportCatalogOut {
  created?: Array<unknown>
  plateReachable?: boolean
  skipped?: Array<unknown>
  unregistered?: Array<unknown>
}

export interface InstanceCredentialMatchOut {
  canManage: boolean
  envId: number
  instances?: Array<MatchInstanceOut>
}

// 创建实例时可选携带的一条调用身份。
export interface InstanceIdentityIn {
  aliasName: unknown
  display?: unknown
  refMode?: "default" | "username"
  refUsername?: unknown
}

// 实例下的调用身份条目(不含账户/密码)。
export interface InstanceIdentityOut {
  aliasName: unknown
  display?: unknown
  refMode?: "default" | "username"
  refUsername?: unknown
}

// 实例改标签(环境降级交互;标签即环境)。
// 
// 目标环境二选一:``envId``(既有环境)或 ``envTag``(自由标签,不存在
// 则自动登记为环境定义)。登录口/版本线/说明随行;API 地址
// (deployments)与身份条目按各自环境维护,不随搬移。
export interface InstanceMove {
  envId?: number | null
  envTag?: unknown | null
}

export interface InstanceOut {
  envId: number
  envName?: unknown
  groupId?: unknown
  line?: unknown
  loginUrl?: unknown
  note?: unknown
  system: unknown
  tags?: Array<unknown>
  updatedAt?: unknown | null
}

export interface InstancePut {
  line?: unknown | null
  loginUrl?: unknown | null
  note?: unknown | null
}

// 实例标签集合(多枚;整组一次提交)。
export interface InstanceTagsIn {
  tags: Array<unknown>
}

export interface InvalidateIn {
  note?: unknown | null
}

export type Kind = "continue" | "step" | "abort" | "read" | "write" | "patch" | "retry" | "skip"

export interface LogSelector {
  category?: unknown | null
  level?: unknown | null
}

// Payload for POST /auth/login.
export interface LoginIn {
  password: unknown
  username: unknown
}

export interface MatchAddrOut {
  baseUrl: unknown
  service: unknown
}

export interface MatchCredOut {
  id: number
  isDefault: boolean
  username: unknown
}

export interface MatchInstanceOut {
  addresses?: Array<MatchAddrOut>
  line?: unknown | null
  loginUrl?: unknown | null
  personalCount?: number
  projectCredentials?: Array<MatchCredOut>
  system: unknown
  tags?: Array<unknown>
}

// Response shape for GET /auth/me.
export interface MeOut {
  capabilities?: Array<unknown>
  must_change_password?: boolean
  projects?: Array<Record<string, unknown>>
  user: UserPublic
}

export interface MemberIn {
  role?: "admin" | "member" | "user"
  userId: number
}

export interface MemberOut {
  addedAt?: unknown | null
  displayName: unknown
  role: unknown
  scenarioCount?: number
  suiteCount?: number
  userId: number
  username: unknown
}

export interface MemberPatchIn {
  role: "admin" | "member" | "user"
}

export type Metric = "pass_rate" | "fail_count" | "total" | "avg_duration_ms" | "max_duration_ms"

export interface NotificationListOut {
  items: Array<NotificationOut>
  page?: number
  pageSize?: number
  total?: number
  unread: number
}

export interface NotificationOut {
  batchId?: unknown | null
  body: unknown
  created_at: unknown
  id: number
  link?: unknown | null
  readAt?: unknown | null
  title: unknown
  type: unknown
}

export type Op = "eq" | "ne" | "gt" | "gte" | "lt" | "lte"

export interface OpCreateIn {
  datasetId?: unknown | null
  opType: unknown
  payload?: Record<string, unknown>
  scenarioId?: unknown | null
}

export interface OpOut {
  appliedAt?: unknown | null
  batchId: unknown
  datasetId?: unknown | null
  datasetName?: unknown | null
  id: number
  note?: unknown | null
  opType: unknown
  payload?: Record<string, unknown>
  scenarioDisplayName?: unknown | null
  scenarioId?: unknown | null
  status: unknown
}

// PATCH /ops/{id} 请求体:payload 整包替换(仅 pending 可改)。
export interface OpPatchIn {
  payload?: Record<string, unknown>
}

// Platform rendering/orchestration container.
// 
// steps is index-aligned with definition.steps (same order, same length).
// resourceMeta is name-aligned with definition.resource keys.
// (runSchemes sidecar 键已随阶段④下线 — 方案不经场景 payload,唯一
// 读写面是 /run-schemes CRUD;存量 payload 中的同键被 extra=ignore
export interface Orchestration {
  resourceMeta?: Record<string, unknown>
  steps?: Array<StepOrchestration>
}

// 入站参数槽位(入站执行参数设计 2026-11-13 §2.1)。
// 
// 契约上移场景级(assertion_registry 同款先例):「这个场景允许外部
// 填什么」是场景的属性。``name`` 必须命中 definition.config.vars 的
// 已声明标量键(写时校验,scenario_store create/PUT 双跑;生成式
// spec 变量不可指 —— data_set_store._scalar_vars 调色板口径)。
export interface ParamSlot {
  description?: unknown
  maxLength?: number
  name: unknown
  pattern?: unknown | null
  required?: boolean
  type?: "string" | "number" | "boolean"
}

export type Pause = "none" | "on_failure" | "every_step"

// 连通测速结果(服务配置管理抽屉)。
// 
// ``ok`` 只表示「拿到了 HTTP 响应」—— 401/404 也是可达,与拨测
// (auth_probe,验登录态)语义不同,别混用。
export interface PingOut {
  latencyMs?: number | null
  message?: unknown
  ok: boolean
  statusCode?: number | null
}

// 「这条用例 × 这个方案」预检入参(执行设计 §1.6)。
export interface PrecheckItem {
  execConfigId?: number | null
  scenarioId: unknown
  schemeId: unknown
}

// 单条预检结论。字段全部是「这条方案配置」的事实,不是用例状态。
export interface PrecheckResult {
  ambiguousAuths?: Array<unknown>
  builtinAuthShadowed?: Array<unknown>
  danglingEntryIds?: Array<unknown>
  deadDatasetIds?: Array<unknown>
  envContext?: Record<string, unknown> | null
  envMixed?: boolean
  envUnspecified?: boolean
  envWarnings?: Array<unknown>
  found?: boolean
  missingAuths?: Array<unknown>
  notCircled?: Array<unknown>
  outOfScopeTargets?: Array<Record<string, unknown>>
  projectAmbiguousAuths?: Array<unknown> | null
  projectMissingAuths?: Array<unknown> | null
  scenarioId: unknown
  schemeFound?: boolean
  schemeId: unknown
  schemeValid?: boolean
  scopeMissing?: Array<Record<string, unknown>>
  unboundServices?: Array<unknown>
}

export interface PrefIn {
  value: unknown
}

export interface PrefMapOut {
  items: Record<string, Record<string, unknown>>
}

export interface PrefOut {
  key: unknown
  value: Record<string, unknown>
}

// off 可选值 = NOTIFICATION_TYPES 全集(词表/开关/前端标签三处
// 同一清单)。S7.4 起 Literal 放宽为裸 str、由 PUT 按词表过滤 ——
// 存量偏好里的退役类型(share_ref_* 四型)能无损回存(静默滤除),
// 不再被收窄后的枚举 422 拒收。
export interface PrefsIn {
  off?: Array<unknown>
}

// 按 type 通知开关;off 列表之外的类型全部开着。
export interface PrefsOut {
  off: Array<unknown>
}

export interface PreviewPlateError {
  message: unknown
  path: unknown
}

// POST /scenarios/preview-plate 请求体:ScenarioDraft + 可选 overlay。
// 
// ``overlay`` 不传 → 与旧 ScenarioDraft 行为完全一致(向后兼容,
// spec §8);传入则 convert 产物经 materialize_run_copy 物化(明文
// 绑定/凭证注入 POST-convert 位点,不过 plate)。
export interface PreviewPlateIn {
  assertion_registry?: Record<string, unknown>
  authDrafts?: Array<AuthDraftIn> | null
  definition: Record<string, unknown>
  orchestration?: Orchestration
  overlay?: ExportOverlay | null
  paramSlots?: Array<ParamSlot>
  paramsStrict?: boolean
  ui?: Record<string, unknown>
}

// Return shape for POST /scenarios/preview-plate.
// 
// 导出场景时前端用 ``converted`` 字段拿 Plate 转换后的"可执行"用例结构
// (已合并 config/services/setup/teardown,字段归一化) — 这就是 GIMBAL
// 实际运行时的输入。``errors`` 是 Plate 返回的字段级校验错。
export interface PreviewPlateResponse {
  converted?: Record<string, unknown> | null
  errors?: Array<PreviewPlateError>
  ok: boolean
}

// §9 ProjectConfigurationSummary:非秘密配置摘要(不返回秘密)。
export interface ProjectConfigurationSummary {
  defaultEnvironmentId?: number | null
  defaultEnvironmentName?: unknown | null
}

// §9 ProjectContext:前端 ProjectLayout 的统一上下文入口。
// 
// effectivePermissions = 主体关系求值(§6);capabilities = 容器
// 能力矩阵(§7)。不返回秘密或全部对象级权限;对象状态约束由资源
// 接口及后端实时判断。
export interface ProjectContextOut {
  capabilities: Record<string, boolean>
  configuration: ProjectConfigurationSummary
  effectivePermissions: Record<string, boolean>
  id: number
  isDefault: boolean
  kind: unknown
  name: unknown
  status: unknown
  uid: unknown
}

export interface ProjectCreateIn {
  description?: unknown
  firstAdminUserId?: number | null
  kind?: "private" | "normal"
  name: unknown
}

export interface ProjectCredentialListOut {
  canManage?: boolean
  items?: Array<AuthAccountOut>
}

export interface ProjectOut {
  canManage?: boolean
  canWrite?: boolean
  defaultEnvironmentId?: number | null
  defaultEnvironmentName?: unknown | null
  description: unknown
  id: number
  isDefault?: boolean
  kind: unknown
  memberCount?: number
  myRole?: unknown | null
  name: unknown
  pendingPromotions?: number
  scenarioCount?: number
  status?: unknown
  suiteCount?: number
  taskCount?: number
  uid?: unknown
}

export interface ProjectPatchIn {
  defaultEnvironmentId?: number | null
  description?: unknown | null
  name?: unknown | null
}

export interface ProjectTokenCreateIn {
  callbackUrl?: unknown | null
  holderId?: number | null
  name: unknown
  scope?: ScopeIn
  ttlDays?: number
}

export interface ReadIn {
  ids?: Array<number> | null
}

// Payload for POST /auth/refresh.
export interface RefreshIn {
  refresh_token: unknown
}

// Payload for POST /auth/register.
export interface RegisterIn {
  display_name?: unknown
  password: unknown
  username: unknown
}

export interface RejectIn {
  reason: unknown
}

// 定义创建:接受完整 ReportDefinition 形态(选择/投影/呈现顶层
// 展开)或 definition 键内嵌(平台内部形态)。
export interface ReportDefinitionCreate {
  definition?: Record<string, unknown> | null
  description?: unknown
  name: unknown
  presentation?: Record<string, unknown> | null
  projection?: Record<string, unknown> | null
  public?: boolean
  selection?: Record<string, unknown> | null
}

export interface ReportDefinitionUpdate {
  definition?: Record<string, unknown> | null
  description?: unknown | null
  name?: unknown | null
  public?: boolean | null
}

// B1 路径推断入参 — 透传 plate resolve-paths action 的 body。
export interface ResolvePathsRequest {
  path_prefix?: unknown | null
  response_body_sample: unknown
}

export interface RestoredEntity {
  entityId: unknown
  entityType: unknown
}

export interface RollbackConflictItem {
  entityId: unknown
  entityType: unknown
  note: unknown
}

export interface RollbackReport {
  batchId: unknown
  conflicts?: Array<RollbackConflictItem>
  restored?: Array<RestoredEntity>
  status: unknown
}

export interface RunOptions {
  debug?: DebugSpec | null
  n_runs?: number
  parallel?: number
  step_from?: number | null
  step_to?: number | null
  subscribe?: Array<SubscribeRule> | null
}

// 一次执行的配方(recipe):数据集/认证等全是纯值。
// 
// Case 层已解散 — RunRequest 即配方本身,直接挂在 scenario 上。
// 旧 ``env`` 字段已随 D2 退役;``environmentId``(authz M2a S2.1)后随
// §8.2 环境降级轮退役 — 旧客户端多发的这两类键被 pydantic 静默忽略,
// 仅失效、不 422(重跑的环境回放走 dispatch 的 ``env_replay`` 参数,
export interface RunRequest {
  batchId?: unknown | null
  callbackPath?: unknown | null
  clientRef?: unknown | null
  credentialSource?: "personal" | "project" | null
  dataSetIds?: Array<unknown>
  dataSetSelection?: Array<DataSetSelection>
  execConfigId?: number | null
  graph?: GraphSpec | null
  injectionEntryIds?: Array<unknown>
  params?: Record<string, unknown> | null
  release?: Record<string, unknown> | null
  reportDefinitionId?: number | null
  runOptions?: RunOptions | null
  scenarioId?: unknown | null
  schemeId?: unknown | null
  schemeName?: unknown | null
  serviceBindings?: Record<string, ServiceBinding>
  steps?: Array<Record<string, unknown>> | null
}

export interface RunResponse {
  executionId: number
  identityMode?: unknown
  runId: unknown
}

// 场景级运行方案(工作台一等实体,plate 零感知,spec §4)。
// 
// /run-schemes CRUD(方案唯一读写面)的请求/响应 wire 契约;
// isDefault/options(M10 RunOptions)为工作台键。
export interface RunScheme {
  dataSetIds?: Array<unknown>
  dataSetSelection?: Array<DataSetSelection>
  injectionEntryIds?: Array<unknown>
  isDefault?: boolean
  logSub?: unknown
  name: unknown
  options?: Record<string, unknown>
  serviceBindings?: Record<string, ServiceBinding>
}

// RS4a 保存检查入参（§5.6）。
export interface SaveCheckIn {
  scenarioId: unknown
  system?: unknown | null
  targetRevision: unknown
}

// Read shape for a Scenario (list / detail / create response).
export interface Scenario {
  config?: Record<string, unknown> | null
  dataSetCount?: number
  meta: ScenarioMeta
  newAuths?: Array<unknown> | null
  orchestration?: Orchestration | null
  projectId?: number | null
  resource?: Record<string, unknown> | null
  schemeCount?: number
  starred?: boolean
  stepCount?: number
  steps?: Array<Record<string, unknown>>
  tags?: Array<unknown>
  visibility?: unknown
}

// POST /scenarios/{id}/copy 可选请求体(另存为)。
// 
// 缺省(无 body)= 旧「复制到我的」行为,副本名沿用 ``(副本)`` 后缀;
// 带 ``name`` = 另存为,重名由端点 409 + suggestion 交前端确认
// (软校验口径见 scenario_store.resolve_name_conflict)。
export interface ScenarioCopyIn {
  name?: unknown | null
}

// Platform draft container.
// 
// definition: the plate Scenario structure as a free-form dict. Backend does
//             not model plate's internal types — plate /convert is the single
//             validation authority ("plate outputs a neutral dict; consumers
//             model it themselves").
export interface ScenarioDraft_Input {
  assertion_registry?: Record<string, unknown>
  authDrafts?: Array<AuthDraftIn> | null
  definition: Record<string, unknown>
  orchestration?: Orchestration
  paramSlots?: Array<ParamSlot>
  paramsStrict?: boolean
  ui?: Record<string, unknown>
}

// Platform draft container.
// 
// definition: the plate Scenario structure as a free-form dict. Backend does
//             not model plate's internal types — plate /convert is the single
//             validation authority ("plate outputs a neutral dict; consumers
//             model it themselves").
export interface ScenarioDraft_Output {
  assertion_registry?: Record<string, unknown>
  definition: Record<string, unknown>
  orchestration?: Orchestration
  paramSlots?: Array<ParamSlot>
  paramsStrict?: boolean
  ui?: Record<string, unknown>
}

// 列表行形态 — 响应投影:不含 steps/config/resource/orchestration
// (payload 重的字段),列表页只消费 meta 摘要 + 计数 + starred。
// 
// 服务端查询仍是全表加载 payload + Python 过滤(M1 不假装拿到 SQL 端
// 过滤——那是 M3 生成列上线后的事);本形态砍的是**响应体**,不是查询。
export interface ScenarioListItem {
  dataSetCount?: number
  meta: ScenarioMeta
  projectId?: number | null
  schemeCount?: number
  starred?: boolean
  stepCount?: number
  tags?: Array<unknown>
  varCount?: number
  visibility?: unknown
}

// Page 信封(§4.1 统一列表契约):{items, total, page, pageSize}。
export interface ScenarioListOut {
  items: Array<ScenarioListItem>
  page: number
  pageSize: number
  total: number
}

// Scenario metadata; one Scenario has exactly one Meta.
// 
// M2 ``Meta`` 的**超集读投影**:声明的字段做校验与别名,其余字段
// (``requirementRef`` 及 M2 后续新增)经 ``extra="allow"`` 原样透传。
// 读侧由 ``_meta_from_row`` 从 payload.definition.meta 组装 —— 此前
// 手写字段清单对未知键静默丢弃,requirementRef 读侧被剥、编排器水合
export interface ScenarioMeta {
  author?: unknown
  createTime?: unknown | null
  description?: unknown
  expire?: boolean
  module?: unknown
  name: unknown
  owner?: unknown
  plate?: Record<string, unknown> | null
  priority: number
  scenarioId: unknown
  system?: Array<unknown>
  tags?: Array<unknown>
  updateTime?: unknown | null
  version?: unknown
}

// ``?fields=options`` 轻量元数据形态(§4.2)——选择器与名称映射专用,
// 砍掉四处「为拿名字拉全量场景表」。可见性口径与列表一致(member =
// 自己 + public / admin = 全量,由路由层保证)。
export interface ScenarioOptionsItem {
  name: unknown
  owner?: unknown
  scenarioId: unknown
  visibility?: unknown
}

// options 形态共用同一 Page 信封(§4.1)。
export interface ScenarioOptionsOut {
  items: Array<ScenarioOptionsItem>
  page: number
  pageSize: number
  total: number
}

// 反查面板 · 单条场景引用:kinds ⊆ {template, snapshot}。
// 
// owner_id 供前端算「删除会被拦截」的预告(与 DELETE 409 同口径:
// 本人场景的 template 才阻断,schemas 见 auth_references)。
export interface ScenarioRefItem {
  kinds: Array<unknown>
  name: unknown
  ownerId: number
  scenarioId: unknown
}

export interface ScenarioRefsOut {
  hidden_count?: number
  visible?: Array<ScenarioRefItem>
}

export interface ScopeIn {
  aliases?: Array<unknown>
  authIds?: Array<number>
}

// 服务键 → 别名(authz M2a S6,consolidated §4.1「方案只做选择,
// 不存值」):``{"alias": "fin-maker"}`` = 服务键 ``fin`` 用别名
// ``fin-maker`` —— 条目默认与 carry 别名键随之切换;地址只由环境
// 决定(同基础服务校验在 ``service_aliases.validate_binding_aliases``)。
// 
// ``url`` / ``authAlias`` 已退役 → 422 ``binding_field_retired``;
export interface ServiceBinding {
  alias: unknown
}

export interface ServiceBindingsOut {
  bindings?: Record<string, unknown | null>
  scope?: unknown | null
  scopeId?: number | null
}

export interface ServiceCreate {
  abbr?: unknown
  description?: unknown
  kind?: "plate" | "external" | "integration"
  name: unknown
  system?: unknown
}

export interface ServiceDrift {
  baseService?: unknown | null
  instanceEnvId?: number | null
  orphaned?: Array<unknown>
  renamedSuggestions?: Array<Record<string, unknown>>
  service: unknown
  uncovered?: Array<unknown>
}

export interface ServiceFieldsOut {
  degraded?: boolean
  fields?: Array<CarryFieldFace>
}

export interface ServiceGrid {
  endpoints?: Array<GridEndpoint>
  plateReachable: boolean
  service: unknown
  stats?: GridStats
}

// 服务×环境实例(组合 deployments + system_env_instances + identities)。
export interface ServiceInstanceOut {
  baseUrl?: unknown
  envId: number
  envName?: unknown
  groupId?: unknown
  identities?: Array<InstanceIdentityOut>
  line?: unknown
  loginUrl?: unknown
  note?: unknown
  tags?: Array<unknown>
}

export interface ServiceInstanceOverviewOut {
  services?: Array<ServiceWithInstancesOut>
}

// 创建/编辑一个服务×环境实例。
// 
// * ``envId`` / ``envTag`` 二选一(自由标签不存在时自动登记);
// * ``baseUrl`` 写 deployments(API 地址);
// * ``loginUrl``/``line``/``note`` 写 system_env_instances(登录口按
//   系统×环境共享);
export interface ServiceInstancePut {
  baseUrl?: unknown | null
  envId?: number | null
  envTag?: unknown | null
  identity?: InstanceIdentityIn | null
  line?: unknown | null
  loginUrl?: unknown | null
  note?: unknown | null
}

// W11 三态分类读面(编排器徽标/保存告警数据源;kind 自主档)。
export interface ServiceKindsOut {
  external?: Array<unknown>
  plate?: Array<unknown>
  unknown?: Array<unknown>
}

export interface ServiceListOut {
  plateReachable?: boolean
  services?: Array<ServiceOut>
  unregistered?: Array<unknown>
}

export interface ServiceOut {
  abbr?: unknown
  createdAt?: unknown | null
  description?: unknown
  inCatalog?: boolean
  kind?: "plate" | "external" | "integration"
  name: unknown
  system: unknown
  updatedAt?: unknown | null
}

export interface ServicePatch {
  abbr?: unknown | null
  description?: unknown | null
  system?: unknown | null
}

export interface ServiceWithInstancesOut {
  instances?: Array<ServiceInstanceOut>
  kind?: "plate" | "external" | "integration"
  name: unknown
  system: unknown
}

// 副本模式结果:新资源 id(场景)或 suiteId + 成员映射摘要。
export interface ShareCopyOut {
  memberCount?: number
  mode: unknown
  scenarioId?: unknown | null
  suiteId?: number | null
  suiteName?: unknown | null
}

export interface ShareCreateIn {
  granteeUserId: number
  mode?: unknown
  resourceId: unknown
  resourceType: "scenario" | "suite"
}

export interface SnapshotRef {
  entityId: unknown
  entityType: unknown
}

export interface StarIn {
  starred: boolean
}

// Platform-side fields for one step, index-aligned with definition.steps[i].
export interface StepOrchestration {
  enabled?: boolean
  name?: unknown
}

// RS4a 提交入参（§5.7）。
export interface SubmitIn {
  applyToSimilar?: boolean
  ops?: Array<Record<string, unknown>>
  reviewConfirmed?: boolean
  saveMode: unknown
  scenarioId: unknown
  system?: unknown | null
  targetRevision: unknown
}

// P2.2:订阅回传摘要里的 fingerprint —— 确认的必须是订阅者看到
// 的那份内容;与当前计算值不一致 409,前端重拉摘要后再确认。
// **必填**。
export interface SubscribeIn {
  credentialSource?: "personal" | "project" | null
  fingerprint: unknown
}

export interface SubscribeRule {
  events?: Array<unknown> | null
  logs?: LogSelector | null
  sink: unknown
  where?: Record<string, unknown>
}

// 整体保存(重构方案 PUT /suites/{id}/composition):模式、成员
// 及顺序、编排配置一次落库;rev 乐观锁,冲突 409 附最新内容。
export interface SuiteCompositionIn {
  members: Array<CompositionMemberIn>
  mode?: "aggregate" | "chain" | "fanout" | "compose"
  modeConfig?: Record<string, unknown>
  rev: number
}

// name 可省略:服务端生成不重名的草稿名(「未命名 Suite N」,
// 重构方案:画布首次拖入创建草稿);带 name 的创建不是草稿。
export interface SuiteCreateIn {
  description?: unknown
  name?: unknown | null
  projectId?: number | null
}

export interface SuiteDetailOut {
  access?: unknown | null
  canEdit?: boolean | null
  canRun?: boolean | null
  canShare?: boolean | null
  createdAt?: unknown | null
  description: unknown
  isDraft?: boolean
  memberCount: number
  members: Array<SuiteMemberOut>
  mode: unknown
  modeConfig?: Record<string, unknown> | null
  name: unknown
  rev?: number
  suiteId: number
  updatedAt?: unknown | null
  visibility: unknown
}

// 场景反查所属 suite(GET /api/scenarios/{id}/suites)。
export interface SuiteLookupItem {
  memberCount: number
  name: unknown
  ownerName?: unknown
  suiteId: number
}

export interface SuiteMemberOut {
  addedAt?: unknown | null
  module: unknown
  name: unknown
  role?: "main" | "before" | "after"
  scenarioId: unknown
  sort: number
  visibility: unknown
}

export interface SuiteMembersAddIn {
  scenarioIds: Array<unknown>
}

// 整表排序:按列表顺序重编 sort(0..n-1)。
export interface SuiteMembersOrderIn {
  scenarioIds: Array<unknown>
}

export interface SuitePageOut {
  items: Array<SuiteSummaryOut>
  page: number
  pageSize: number
  total: number
}

export interface SuitePatchIn {
  clearDraft?: boolean
  description?: unknown | null
  name?: unknown | null
}

// Suite 整体适配入参（§5.8）。
export interface SuiteSubmitIn {
  saveMode: unknown
  suiteId: number
  system?: unknown | null
  targetRevision: unknown
}

export interface SuiteSummaryOut {
  createdAt?: unknown | null
  description: unknown
  isDraft?: boolean
  latestRun?: Record<string, unknown> | null
  memberCount: number
  mode: unknown
  name: unknown
  ownerName?: unknown | null
  publishedMembers?: Array<unknown> | null
  rev?: number
  suiteId: number
  updatedAt?: unknown | null
  visibility: unknown
}

// 按系统的子配置(§4:多系统混合编排下每组配置的组成单元)。
export interface SystemSubConfig {
  aliases?: Array<unknown>
  bindings?: Record<string, unknown>
  carryOverrides?: Record<string, unknown | null>
  service: unknown
}

export interface TaskIn {
  callbackPath?: unknown | null
  cardTemplate?: unknown
  clientRef?: unknown | null
  identityMode?: unknown
  name: unknown
  projectId?: number | null
  resultPolicy?: unknown
  scenarioId: unknown
  schemeId?: unknown | null
  targetSystem?: unknown
  triggerCron?: unknown
  visibility?: unknown
}

export interface TaskPatch {
  callbackPath?: unknown | null
  clientRef?: unknown | null
  name?: unknown | null
  resultPolicy?: unknown | null
  schemeId?: unknown | null
  targetSystem?: unknown | null
  tokenId?: number | null
  triggerCron?: unknown | null
  visibility?: unknown | null
}

export interface TestResult {
  message: unknown
  ok: boolean
  status_code?: number | null
}

export interface TokenCreateIn {
  callbackUrl?: unknown | null
  kind?: unknown
  name: unknown
  scope?: ScopeIn
  ttlDays?: number
}

// Auth response shape — access + refresh + bearer marker + user.
export interface TokenOut {
  access_token: unknown
  refresh_token: unknown
  token_type?: unknown
  user: UserPublic
}

export interface TokenRenewIn {
  ttlDays: number
}

export interface TransferIn {
  toUserId: number
}

// C10 未索引步骤(缺 endpoint_id)—— 适配保护缺口警示条数据。
export interface UnindexedStepOut {
  reason: unknown
  scenarioId: unknown
  stepIndex: number
}

export interface UnreadCountOut {
  count: number
  roleVersion?: unknown | null
}

// Payload for POST /users(admin 开号,M2.5 收紧:任何登录用户都能
// 自行开号的 spec-1 遗留已闭合 —— 用户管理页是唯一开号入口)。
export interface UserCreateIn {
  display_name?: unknown
  password: unknown
  role?: "user" | "admin" | "super_admin"
  username: unknown
}

// DELETE /users/{id} 处置入参(P2-2 三选一,默认转公共库)。
// 
// * ``publicize``:私有场景转公共库(署名保留原作者字符串快照);
// * ``transfer``:场景转让给 ``transfer_to`` 指定成员(数据集/方案
//   随场景走;个人别名一并转共享);
// * ``purge``:场景一并删除(前端明示二次确认)。
export interface UserDeleteIn {
  disposal?: "publicize" | "transfer" | "purge"
  public_transfer_to?: number | null
  transfer_to?: number | null
}

// Page 信封(§6.3):用户列表分页(接口收紧已随 M2.5 落地)。
export interface UserListOut {
  items: Array<UserPublic>
  page?: number
  pageSize?: number
  total?: number
}

// Payload for PATCH /users/{user_id}.  All fields optional.
// 
// ``role``(M2.5)取代 is_admin 成为人事权威字段;末位 admin 保护
// 按角色判定(不可降级最后一个 admin)。
export interface UserPatchIn {
  display_name?: unknown | null
  is_active?: boolean | null
  new_password?: unknown | null
  role?: "user" | "admin" | "super_admin" | null
}

// Public-facing user view. ``created_at`` is serialized to ISO 8601 string.
export interface UserPublic {
  created_at: unknown | null
  display_name: unknown
  id: number
  is_active: boolean
  is_system?: boolean
  role?: "user" | "admin" | "super_admin"
  updated_at?: unknown | null
  username: unknown
}

export interface ValidationError {
  ctx?: Record<string, unknown>
  input?: unknown
  loc: Array<unknown | number>
  msg: unknown
  type: unknown
}

// 运行控制(重构方案):only = 试跑选中段(所选单元 + 其上游,
// 编排模式按 ref、聚合按 scenarioId);toNode = 串联只跑到某一步
// (ref)。from_node 刻意不开放(被跳过的上游输出平台无从提供)。
export interface _SuiteRunIn {
  credentialSource?: "personal" | "project" | null
  only?: Array<unknown>
  toNode?: unknown | null
}
