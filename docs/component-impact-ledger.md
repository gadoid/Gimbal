# 关联组件改造欠账台账

> 配套 `service-registry-redesign.md`(服务注册与凭证底座重构)。
> 新底座对关联组件的影响点与已知变更,一组件一卡;Phase 2 按卡销账,
> 销完在本文件勾记。口径变更以 redesign 文档为准,本文件不复述模型。
>
> **进度快照 2026-11-16**:C1 ✅;C2a ✅;C2b ✅;C3a ✅(装载就绪链修复);
> C3b ✅(三档键选择器 + env 覆盖开关 + 后端系统键面聚合);C4 ✅;
> C5 观察项 ✅。**Phase 2 页面欠账全销(含 P2-B.6 导入映射按 ref 重做)**;
> P2-A 测试续期亦已完成(52 文件全处置)。剩余:migrations 时代造形、
> Phase 3 文案清账。详见 `service-registry-progress.md`。

## C1 凭证管理(Auths.vue / routers/auth_sessions.py)

**状态**: ✅ 完成(P1-8 账户化 + 主档选择收口)。
- 表单 system 切**主档选择**(原生 select;主档系统 ∪ 存量行系统 ∪ 预填值,
  主档外选项标「未注册」;主档不可达时不误标)
- 组头未注册系统标「未注册」徽章(深链服务注册;主档可达时才判)

**新架构定位**:账户池管理页 —— 账户 = 一等公民(2026-11-16 平铺改造的延续),
身份条目是引用侧(反向展示)。

已知变更:
- 表单:**去「登录地址」**(上提实例);system 改为主档选择(不再自由文本);env 必填
- 行展示:登录地址列 → 「被 N 个身份条目引用」(引用计数新口径);
  「未声明」徽章退役(迁移自动补齐条目声明)→ 改为「未被条目引用」弱提示
- 拨测:url 取实例 login_url(system×env);实例缺席 → 「实例未配置,去环境配置页」
- 分组仍 system×env;未注册主档的 system 标「未注册」
- testid 契约原样保留(auth-row-* / f-alias / auth-test-* 等)
- 后端:auth_sessions 端点切账户形状(字段去 url/alias/slot;条目引用计数走
  auth_references 新口径)

## C2 项目子面板(ProjectDetailView 五面板)

### C2a ProjectCredentialsPanel(项目凭证)

**状态**: ✅ 账户化完成(P1-8)+ system 主档选择收口(对称 C1)。
- 账户化对称:表单去登录地址;system 主档选择;env 必填
- 菜单「设为默认」语义 = 账户 is_default(ref_mode=default 的取用位)
- prj-cred-* testid 保留

### C2b ProjectConfigPanel(项目配置)

**状态**: ✅ 完成(口径切换;后端 slot-status 在 P1 已条目化,响应形状不变)。
- 槽位状态节 → **身份条目装载**(成员凭证清单):条目 × 成员装载矩阵,
  chips「已绑/未绑」→「已装载/未装载」,项目覆盖 chip →「项目池 · 已覆盖」;
  prj-slot-* testid 保留(条目名不变)
- 执行预览(EffectivePreviewDialog,双宿主):装载表 条目/账户# 口径,
  缺装载提示与空态文案同步;preview-* testid 保留
- carry 节 hint 对齐三档键域(条目键 > 服务键 > 系统键 > 层默认)
- 版本线读面与「去服务注册」深链:P1 读面形状不变 + ServiceAliasDetail
  重做时已切新页锚点,本卡无残余动作

### C2c 成员面板 / 令牌面板

**状态**: ✅ 零变更确认。
- 零变更(令牌 scope 键域 = 条目名,不变;成员与架构无关)

## C3 配置

### C3a 执行配置(ExecConfigsView.vue)

**状态**: ✅ 完成(装载就绪链修复 + 条目口径)。
- 旧 `slotBound` 读账户行 slot/alias 字段 —— 账户化后恒 false(整面板
  误报缺绑定);换**条目装载新链**:换用条目 → (主档 system, 条目 env,
  ref) → 个人池账户命中(与后端 pick_bindings 同构;default ref 只认
  is_default 账户)
- 装载表:声明条目 / 换用条目(各带未登记标)/ **装载坐标列**(system ×
  env · ref,建账户落点)/ 已装载·缺账户
- 缺账户深链 /auths 预填直达改按 **(system, envId)**(旧 newSlot 退役)
- 注册表定向检索面 = 声明条目 ∪ 换用条目;地址就绪仍读 deployments

### C3b carry 配置(ServiceBindingEditor.vue)

**状态**: ✅ 完成(三档键选择器 + env 覆盖开关;入口留条目/服务详情与
项目配置页 —— 环境配置页未拆独立页,见 redesign §6.0 偏离 1)。
- **三档键选择器**(项目配置页 ③):条目 / 服务 / 系统 optgroup 分组,
  选项 = 条目注册表 ∪ 主档服务/系统 ∪ 存量绑定键(兜底组);键落在
  哪一档在写面显式可选
- **env 覆盖开关**(编辑器 svc-bar):空 = 全环境基线层,选定环境 =
  覆盖层;读面(本键 + base 层)与写入同坐标,toast 标写入层
- **后端系统键面聚合**(`/carry/bindings/{key}/fields`):纯系统名键 →
  该系统全部服务面并集(服务名键不受同名系统影响);新增用例
  `test_service_fields_system_key_aggregates_member_services`(待 PG
  环境执行 —— 本机无 TEST_DATABASE_URL)
- api/carry.ts:getBindingsFor/putBindings 增 envId 参
- 存量 238 行(服务键 fin-service)自动落「服务」档,零改值 ✅

### C3c 环境管理(现内嵌 ServiceAdmin)

**状态**: 🟡 部分 —— 实例弹框已提供 (system,env) 版本线编辑;
环境表单的 version-line 行仍保留(后端双向同步实例行,不冲突)。
- 环境表单收窄:名称/描述/默认位;「版本线行编辑」迁出到实例卡
  (每个 (env, system) 行自带版本线,不再塞环境表 JSON)

## C4 服务注册 + 环境配置页(Phase 2 重做主体,非欠账,列此对齐)

**状态**: 🟡 ServiceAdmin 重做完成(主档注册簿 + 对账 + 实例弹框 + 删除/登记);
ServiceAliasDetail 已条目化(头部徽标 环境+ref / 概览补账户装载行 / 就绪矩阵扩
实例登录口·版本线两列 / 凭证 tab→账户装载 / 登记表单补 env+ref、列表扩列);
环境配置页未拆独立页(实例配置并入服务注册页,见 redesign §6.0 偏离 1)。

- ServiceAdmin.vue → 结构面:系统分组注册簿 + 对账条(未注册/漂移/不可达)
  + external 登记
- 环境配置页(新):环境 → 系统实例列表(login_url/版本线/说明) + 身份条目管理
  + carry 配置入口(C3b)
- ServiceAliasDetail.vue 退役;旧路由重定向(书签不 404)

## C5 编排器 / 工作台(观察项,兼容零改)

**状态**: ✅ 键域兼容确认(composer 下拉已切条目域,P1-8)。

- 编排器别名下拉(listAllAliases):键域不变零改;「系统不匹配」检查数据源
  扩主档(微适配,可并入 Phase 2 任意轮)
- 工作台服务卡 / 服务画像:catalog 读面不变
- DataSetGridEditor / dataset-grid 的 ${slot} 静态扫描:不变

## 销账顺序建议

C1–C5 全部销账(2026-11-16);P2-A 测试续期 + P2-B.6 导入映射按 ref 重做
已完成。后续:migrations 时代造形 → Phase 3 文案清账。
