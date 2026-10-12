# 集成线 P2 · 设计方案(v1.0 草案)

> 日期:2026-10-12　基线:`feat/plate-s1 @ 71bda0ac`(外部接口登记批已落)
> 状态:**v1.0;进度:Y1 ✅(abaf8998) / Y2 ✅(3a50d0ef) / Y5 ✅ / Y3 ✅(2026-10-12)**;
> 余 Y4(卡片模板 kv/counter/list + state_mapping 游标)。
> 拍板:P-A/P-B/P-C 已定(2026-10-12:B / 平台目录 / 升代际 2)。
> 依据:《GIMBAL-外部系统集成架构设计》§详细设计/分期计划 P2 + 2026-10-09 评审定稿
> + 2026-10-12 用户拍板(G7 并 task3c→本批顺带;G2 随 P2;G1 声明驱动随本批;
> personal 二期=本批;**外部系统定义与平台目录合流**)。
> 原设计四项待拍板中,执行通道(半常驻两条)与执行历史(只留最近一次)已随 P1 定案;
> 本方案新增拍板项 P-A/P-B/P-C(§5)。

## 0. P2 范围(与原设计的差异)

| 原设计 P2 条目 | 本批口径 |
|---|---|
| G1 认证分派、call.auth 透传、md5 签名器具名化 | ✅ 保留(具名化已随 X4 落地;本批补声明驱动全链) |
| fin 声明一次性修正 | ✅ 保留 |
| plate:ServiceDefinition.kind(G6);GitLab、Jenkins 系统定义 | ⚠️ **改落平台外部目录**(§2,2026-10-12 合流拍板) |
| 个人模式与订阅生成实例、missing_credential、手动执行冷却 | ✅ 保留 |
| kv / counter / list 模板 | ✅ 保留 |
| 凭证失效暂停与按模式通知(G7 平台侧) | ✅ 保留;G7 执行器侧(error_kind)一并做(避免平台侧判定悬空) |
| 跨次状态(游标,state_mapping) | ✅ 保留 |
| G2 outputs 暴露 | ✅ 保留(明细行 + /runs/{id}) |

## 1. G1 声明驱动全链(Y1)

X4 已落执行器分派框架(`auth_signer`:md5sign 默认 / standard.bearer /
standard.basic)。本批接通声明链:

1. **plate `binding.auth` → convert 透传为 `call.auth`**(M2 Call 加可选字段
   `auth`,缺省 none → 不透传即旧行为)——**M2_GENERATION 1→2**,按 gen_m2
   compat 纪律:提供迁移函数(存量 call 无 auth 键,迁移为无操作;compat
   是加法不兼容面为零,但新增必填无、枚举无删减 → 实际为纯加法,
   代际是否必升由 P-C 拍板定);
2. **导出侧**(gimbal_plate/export/gimbal.py):call.auth = 端点 binding.auth
   (仅四标准值;custom 不透传——签名器名在系统级声明,§1.3);
3. **执行器侧**(call.py):call.auth 非空时设会话 `auth_signer` 映射
   (bearer→standard.bearer;basic→standard.basic;none→不注入;
   custom→查签名器注册表(§1.4));
4. **md5 签名器注册具名 `md5sign`**;系统级声明落 `gimbal:system` /
   `gimbal:defaults` 的 `auth_signer` 键(端点可覆盖);
5. **fin 声明一次性修正**:fin 23 端点中 19 个错标 bearer(实际 md5)——
   改标 custom + 系统 auth_signer: md5sign;同提交用现有 fin 用例回归;
   修正后发 fin 新修订(2.0#2 或 1.0#2,按版本线惯例)。

风险(原设计风险表第一条):签名器改造与 fin 声明修正必须同提交,否则现有
用例全部认证失败——本批按此纪律执行。

## 2. 外部系统定义落平台目录(Y5,合流拍板的落地)

GitLab/Jenkins **不进 plate**(推翻原设计 §详细设计 1 的落点,依 2026-10-12
「一次定义、两处消费」拍板):

1. **登记**:服务信息页建 kind=external 别名(gitlab/jenkins)→ OpenAPI
   导入(外部接口登记批 X1 已交付的导入器直接用);base_url/凭证挂别名
   (credential_alias 或个人凭证池);
2. **集成任务的场景引用**:集成任务选用的场景,其步骤锚点用 `ext:` 锚点
   (X2 已交付)——「编辑集成用例显示 integration 系统」的原需求消解:
   外部系统天然不在 plate 被测接口列表,编排器对 ext: 锚点步骤走外部
   目录下拉;
3. **只读闸升级**:P1 判定 method ∈ GET/HEAD/OPTIONS;外部目录条目天然
   知道 method → 闸判定兼容 ext: 锚点(读目录);plate 端点的 POST 查询
   `query_safe` 元信息随端点声明走(Y1 同批发不发?——**挂 plate 元数据
   加法,随 fin/platform 修订节奏,不在本批硬做**;本批只读闸对 ext: 步骤
   按目录 method 判,plate 步骤维持 method 判定)。
4. ServiceDefinition.kind(G6)**不做**——外部不进 plate 后无过滤需求
   (被测列表天然只有 sut)。

## 3. G2+G7:outputs 暴露与 auth 错误分类(Y2)

执行器(与平台 dispatch 消费面同批):
1. **明细行**(`_detail_row`)加 `outputs`(场景作用域变量快照,过脱敏键表)
   与 `error_kind`(none/auth/timeout/transport/logic;401/403/预处理登录失败
   → auth);
2. `/runs/{id}` 响应带 outputs(同脱敏);
3. 平台 `integration_runner`:run 结果明细行 error_kind=auth → 实例
   `paused/auth_failed`(不重试,防锁号);按模式通知(个人=持有人,
   平台=operator/admin);凭证更新复活钩子(参照取数视图先例);
   订阅时缺凭证 → `paused/missing_credential`。
4. 普通执行链(dispatch)不消费 outputs(避免无谓载荷;仅集成路径读)。

## 4. 个人模式 + 卡片模板 + 跨次状态(Y3/Y4)

按原设计 §3/§4/§7 实施,增量点:
1. **personal 解禁**:create_task 放开 identityMode=personal;订阅生成实例
   (工作台加卡时);写操作必须个人(平台模式只读闸已有,补 personal 全开);
2. **手动执行冷却**:个人模式持有人无限冷却?原设计表:个人=持有人可立即
   执行(无冷却),平台=冷却 —— 按 P1 的 60s 冷却对平台保留,个人 0;
3. **卡片模板 kv/counter/list**(FunctionCard 结构化渲染注册面)+ 第二期的
   字段格式化不做;
4. **state_mapping → state_vars**(跨次游标):物化函数加变量叠加参数
   (纯函数保持);result_policy on_change 判定基准维持状态翻转。

## 5. 决策记录(2026-10-12 用户拍板)

- **P-A = B**:保留五枚举,签名器名走系统级 `auth_signer` 声明(端点可覆盖);
  Call 透传承载 = `call.auth`(枚举)+ `call.auth_signer`(可选,custom 时
  签名器名;随 call 一次性合成端点覆盖 > 系统声明)—— 两字段同一代际。
- **P-B = 平台目录**:GitLab/Jenkins 落平台外部目录(ext: 锚点);G6 不做;
  推翻原设计 plate 系统目录落点(依 10-12 合流拍板)。
- **P-C = 升代际 2**:M2_GENERATION 1→2 + no-op 迁移函数(纪律优先)。

## 6. 波次与验收

| # | 内容 | 规模 | 验收 |
|---|---|---|---|
| Y1 ✅ | G1 全链(M2 call.auth + 导出 + 执行器 + fin 修正 + fin 新修订) | L | 已落:gen2+no-op 迁移;投影透传;执行器声明驱动分派;fin 19 端点修正+1.0#2 已发推;基线重钉(dispatch/query_views);门 1275+865 绿 |
| Y2 ✅ | G2+G7(outputs/error_kind/暂停/通知/复活) | M | 已落 3a50d0ef |
| Y3 ✅ | 个人模式(解禁/订阅实例/missing_credential/冷却) | M | 已落(写操作放行;订阅即建;无冷却;缺凭证 paused/missing_credential + 复活) |
| Y4 | 卡片 kv/counter/list + state_mapping 游标 | M | 增量拉取游标跨次生效;三模板三档渲染 |
| Y5 ✅ | 只读闸 ext: 分支 | S | 已落(登记=运营动作,X1 导入器) |

顺序:Y1 → Y2 → Y5 → Y3 → Y4(Y5 前置 Y1 的 fin 修正不依赖;Y3/Y4 相对独立)。
门:每波三侧全量(后端 pytest / 前端 vitest+vue-tsc / plate pytest + gimbal 单测)。
