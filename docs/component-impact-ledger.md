# 关联组件改造欠账台账

> 配套 `service-registry-redesign.md`(服务注册与凭证底座重构)。
> 新底座对关联组件的影响点与已知变更,一组件一卡;Phase 2 按卡销账,
> 销完在本文件勾记。口径变更以 redesign 文档为准,本文件不复述模型。
>
> **进度快照 2026-11-16**:C1 已做账户化最小适配(表单/行/拨测/反查全部切换,
> 搜索占位符与「system 主档选择」待清);C2a 已账户化;C4 的 ServiceAdmin
> 主档注册簿+对账+实例弹框已完成,ServiceAliasDetail 仅 face 表单切 display,
> 概览/凭证 tab 待改;其余未动。详见 `service-registry-progress.md`。

## C1 凭证管理(Auths.vue / routers/auth_sessions.py)

**状态**: 🟡 最小适配完成(P1-8),剩余 system 主档选择器 / 文案清账。

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

**状态**: ✅ 账户化完成(P1-8)。
- 账户化对称:表单去登录地址;system 主档选择;env 必填
- 菜单「设为默认」语义 = 账户 is_default(ref_mode=default 的取用位)
- prj-cred-* testid 保留

### C2b ProjectConfigPanel(项目配置)

**状态**: ⬜ 未开始(槽位状态节仍读旧口径)。
- 槽位状态节 → **身份条目状态**:项目场景引用的条目 × 成员装载矩阵
  (条目名不变、口径从槽位换条目)
- 执行预览:环境/地址解析链不变(resolve_environment + deployment_urls 均零改),
  条目→账户解析换新链;版本线显示改读实例表
- 「去服务注册」深链锚点更新到新页

### C2c 成员面板 / 令牌面板

**状态**: ✅ 零变更确认。
- 零变更(令牌 scope 键域 = 条目名,不变;成员与架构无关)

## C3 配置

### C3a 执行配置(ExecConfigsView.vue)

**状态**: ⬜ 未开始(后端新链已就绪,前端就绪度仍按旧槽位判定)。
- 就绪度面板换新链:条目装载(ref→账户)取代槽位绑定判定;地址就绪仍读 deployments
- 「地址在服务注册」深链 → 新页锚点

### C3b carry 配置(ServiceBindingEditor.vue)

**状态**: ⬜ 未开始(后端三档键域已就绪;写面未提供键选择器/env 覆盖开关)。
- **入口迁居**:别名详情页 → 环境配置页的 (env, system) 配置分区
- config_key 三档选择器(身份条目 / 服务 / 系统)——键域三级化的写面
- env 覆盖开关(env_id 空 = 全环境基线)
- 存量 238 行(服务键 fin-service)自动落「服务」档,零改值

### C3c 环境管理(现内嵌 ServiceAdmin)

**状态**: 🟡 部分 —— 实例弹框已提供 (system,env) 版本线编辑;
环境表单的 version-line 行仍保留(后端双向同步实例行,不冲突)。
- 环境表单收窄:名称/描述/默认位;「版本线行编辑」迁出到实例卡
  (每个 (env, system) 行自带版本线,不再塞环境表 JSON)

## C4 服务注册 + 环境配置页(Phase 2 重做主体,非欠账,列此对齐)

**状态**: 🟡 ServiceAdmin 重做完成(主档注册簿 + 对账 + 实例弹框 + 删除/登记);
环境配置页未拆独立页(实例配置并入服务注册页,见 redesign §6.0 偏离 1);
ServiceAliasDetail 仅 face 表单切 display,概览/凭证 tab 待改。

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

C4(页面骨架,ServiceAdmin ✅ / AliasDetail 待续)→ C1(凭证,🟡)→
C2b(项目配置,⬜)→ C3a/C3b(配置,⬜)→ C3c 随 C4。C5 观察项随遇随销。
P1-7 测试续期(52 文件)与上述页面改造并行推进,不阻塞。
