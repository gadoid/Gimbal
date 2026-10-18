# 集成线 v2 · 改造设计方案(v1.3,已实现)

> **实现状态(2026-10-14)**:I1/I2/I3/I3.5/I4 全批次落地并通过 §5 验收

> **取代注记(2026-10-19,W3/归一方案批3)**:本方案的「平台目录」路线已被《外部接口定义归一 plate 改造方案》v1.0 取代 —— 定义真源归 plate(kind=integration,不发版,`ext:` 锚点与 external_endpoints 目录已退役);决策链以归一方案 §0.1 为准,本文仅存历史过程价值。
> ——引擎单测 53(含 I1 新增 7)、后端 pytest 973、前端 vitest 1270 +
> vue-tsc 零错、取数视图回归 63;迁移 0024(run/check 加列 + R-A 映射)
> /0025(删 last_status)/0026(external query_safe)已上库;重启后调度器
> 真跑一轮,run=ok/check=none 落库正确。顺带修复一个存量生产 bug:
> 集成 runner 此前读 LaunchResult.run_result 投影的 status/details,而该
> 投影 counts-only,真实失败跑不出 failed/auth/outputs(测试桩伪造形状
> 掩盖);现直接消费 LaunchResult 字段。
> I3 浏览器走查已补(5173 实机):断言失败/错 token/停对端三态在工作台
> 卡片(红灯·检查不通过+断言文案 / 灰灯·凭证失效角标+上次结论+401 /
> 灰灯·网络异常角标+上次结论+connect refused)与集成中心两列(检查
> 结论/运行状态)互不混淆,截图存证。
> I4 登记页开关已补:外部别名详情页(ServiceAliasDetail)「外部接口」
> tab 列目录条目,admin 可标记/撤销 query_safe(确认弹窗 + 审计),
> 非 admin 只读;实机验证标记后 POST 查询可建平台模式功能、撤销后
> 422 并列判定依据「步骤 0(POST,未标 query_safe)」。

> 2026-10-15 起草,同日三轮评审修订。基线 `feat/plate-s1 @ 41a8b5af`。
> 依据:《GIMBAL-外部系统集成架构设计》(P1 定稿)、`claude/integration-p2-design.md`
> (Y1-Y5 已落)、2026-10-14 讨论的两个问题(① 平台模式只读口径挡住 POST 查询;
> ② 卡片「正常/失败」反映的是「能否跑通」而非「检查结论」)。
> v1.1 修订:R-A~R-E(迁移映射 auth_failed / 双出过渡 / outputs 比较口径 /
> 软失败落点 / 投影确认点)。
> v1.2 修订(二轮评审 Q1-Q4 + 小项):分类规则补 timeout/cancelled/halted
> 标记;过期公式改双触发法;结论通知节流改边沿合并;I2 期间旧字段投影
> 写实;真源描述更正;角标优先级;lastError 前缀。
> v1.3 修订(三轮评审):
> * **分类规则 3 回退修复**——v1.2 把 transport 错并进 timeout(丢了
>   v1.1"对应值"的分立),网络/对端异常将永远显示"超时"、角标"网络
>   异常"出不来;拆回两句(§2.2);
> * **边沿合并补两处定义**——加 `check_notified_at` 列(节流间隔需要
>   上次通知时间,与 `check_changed_at` 在被节流时会分道);初始化
>   静默规则(`check_notified_status ∈ {'', unknown}` 只回写不发,
>   防 I2 上线/新建任务首次执行的全量通知风暴;仅 pass↔fail 翻转才
>   发;none↔有结论不发)(§2.3/§2.4);
> * 小项:§1.2 残留的"view 级声明"措辞删除(与 §3.1 更正矛盾);
>   角标优先级补手动停用 `enabled=false`(停用必过期,显示"已停用"
>   不叠加过期置灰,并入 D13)。
> 定稿小项(2026-10-14,不改变结论,随实现落实):
> * §2.5 角标优先级去重(旧"暂停 > 过期"一句删除,只留 D13 定义);
> * 节流规则补 `check_notified_at` 为空口径:**按已满足间隔处理**——
>   静默回写不落通知时间,否则静默回写后的第一次真翻转会被挡一拍;
> * 已知取舍:初始化静默意味着存量实例迁移后首跑直接 fail 不发结论
>   通知——此类实例改造前一直在走 `fail_streak` 运维通知,不存在
>   「没人知道」,接受。
> 约束:不新增模块。改动落在 `integration_runner` / `routers/integration` /
> `FunctionCard` / `IntegrationCenter` / 外部目录 / 执行器 `engine.py`。

---

## 1. 现状与问题(断言均经代码复核)

### 1.1 一个状态承载了两个维度

实例只有一个 `last_status`(passed / failed / timeout),`_finish` 的判定:
通道正常且 `run_result.status ∈ {passed, success, ok}` 即 passed;其余
(including 断言失败)一律 failed——`fail_streak` 为
`0 if status == "passed" else prev_streak + 1`,on_change 以
`inst.last_status != status` 为翻转基准(integration_runner.py:421-436)。

| 场景 | 现在的显示 | 应该的显示 |
|---|---|---|
| Jenkins 构建红了,场景里没写断言 | 正常 | 检查不通过 |
| Jenkins 构建红了,场景里断言了 `result == SUCCESS` | 失败,累加 `fail_streak`,连续 3 次通知 admin | 检查不通过,集成本身运行正常 |
| Jenkins token 失效 | 失败,实例暂停(auth_failed) | 运行异常·凭证失效,检查结论保留上次的值并标为过期 |
| 被检系统接口结构变了,提取失败 | 失败 | 运行异常·契约不符,不能误报为检查不通过 |

原设计 §7 已把「status 模板的自定义判定」列为第二期,第一期用执行成败
代替检查结论。本方案补上这个第二期。

### 1.2 平台模式只读口径没有用上 `query_safe`

- `is_scenario_read_only` 只认 GET / HEAD / OPTIONS;其 docstring 自己
  写着「POST 实现的查询随 P2 接 plate 的 query_safe 元数据(方案 §3)」
  ——本方案是在兑现 P1 立下的欠条。
- plate 端点元数据**已有** `metadata.query_safe`
  (gimbal_plate/schema/endpoint/metadata.py:26,注释明说「非 GET 端点挂
  query_views 须显式声明写副作用白名单」),`query_view_runner` 在用
  (view dict 为派生载体,真源即端点元数据,见 §3.1),但集成只读闸
  没读这个字段。
- 外部目录 `ExternalEndpoint` **没有** `query_safe` 字段,`ext:` 锚点
  步骤只能按 method 判定。
- 影响:Jira 的 `POST /search`、MeterSphere 的分页列表查询在平台模式下
  都用不了。

### 1.3 执行器分类缺口(前置,已核实)

`statemachine/engine.py` 的 `_handle_prepare`(287-289)与
`_handle_extracting`(319-321)hard_failed 时直接进 TEARDOWN,**不设
`_error` / `_error_phase`**;而 `core/runner.py:_error_kind_of` 首行
`if status == passed or not error: return "none"`——这类失败的
`error_kind` 恒为 **`none`**,集成侧无法归类,STEP_FAILED 事件文案也只有
`final_state=failed`。verifying 阶段有现成写法(engine.py:340-345)可对齐。

### 1.4 顺带发现(已核实)

- **失败时清空 outputs**:latest 策略下 `_finish` 把失败那次的
  `outputs or {}`(空)写进 `last_outputs`——一次通道抖动,卡片数据
  即被清空(integration_runner.py:433)。
- **过期阈值固定 1 小时**(routers/integration.py:373):*/1 的保活任务
  停摆 1 小时才变灰,每天一次的任务则每天误报过期。周期推算原语现成
  (`cron_expr.next_fire` 已在 runner 中使用)。
- **`on_change` 基准是 `last_status` 翻转**,拆分后需重定义。

---

## 2. 设计:运行状态与检查结论拆分

### 2.1 两个维度

| 维度 | 回答的问题 | 取值 | 驱动什么 |
|---|---|---|---|
| **运行状态** `run_status` | 这次集成能不能正常跑完 | `ok` / `auth` / `timeout` / `transport` / `contract`(契约不符:提取、前置失败) / `channel`(通道、plate、平台内部故障) | `fail_streak`、暂停、运维通知、卡片角标 |
| **检查结论** `check_status` | 被检对象是否健康 | `pass` / `fail` / `none`(场景没断言) / `unknown`(运行异常,没拿到结论) | 卡片主状态灯、结论变化通知、`on_change` |

**检查规则的唯一来源是场景里的断言**,平台上不做第二套「输出字段 →
红黄绿」规则:GIMBAL 的核心能力就是「策略 + 断言」的归一化,规则写在
场景里可评审、可导出、可调试;平台再长一套就是第二个规则引擎。原设计
§7 二期的「输出值映射」因此作废。

### 2.2 分类算法(`integration_runner` 内的一个纯函数,表驱动可测)

输入:`launch_status`、`run_result.details[].steps[]` 的
`status / error_phase / error_kind`、编译后 case 是否存在 verifying 阶段
策略。按序判定,命中即停:

1. 通道故障、plate convert 异常、平台内部异常,以及**调试链的
   `error_phase=halted`**(仅调试链出现)→ `run=channel`,`check=unknown`
2. 任一步 `error_kind=auth` → `run=auth`,`check=unknown`
3. **超时与网络分立**(v1.3 修复 v1.2 回退——两句,不可再合并):
   - `error_kind=timeout` **或** `error_phase ∈ {timeout, cancelled}` →
     `run=timeout`(Q1:单元超时(plan.py)与协作取消(scenario_runner)
     的标记不经 calling 阶段类型化,`error_kind` 是 `logic`,不补会落
     兜底错判 contract);
   - `error_kind=transport` → `run=transport`(网络/对端异常——并入
     timeout 会让卡片角标"网络异常"永远出不来)。
   两者 `check=unknown`。
4. 任一步 `error_phase ∈ {preparing, extracting}` → `run=contract`,`check=unknown`(依赖 §4 执行器修复)
5. 任一步 `error_phase=verifying` → `run=ok`,`check=fail`,`check_message` 取第一条失败断言的 message
6. 全部步骤通过:有断言 → `check=pass`;无断言 → `check=none`;
   **仅软失败**(引擎 #9 后 soft 失败不设 error、不算 failed)→ **按
   通过计,`check=pass`(当前口径;报告重构引入 warn 档后再细分,见 D6)**
7. 兜底:`error_kind=logic` 且不属以上 → `run=contract`(宁可报运行
   异常,不误报检查不通过)

### 2.3 状态推进规则(重写 `_finish`)

- **暂停**:只看 run。`auth` 立即暂停(现有逻辑不变);`missing_credential` 不变。
- **`fail_streak` 与运维通知**:只在 `run ≠ ok` 时累加(通知对象保持现状);
  `check=fail` **不累加、不通知、不暂停**。
- **检查结论**:`run ≠ ok`(check=unknown)时**保留上次** `check_status` /
  `check_message`,卡片标「结论可能过期」;`run = ok` 时写入新结论。
  **「检查结论变化」通知 = 边沿合并**(v1.2/Q3 引入,v1.3 补全定义):
  - **只在 pass ↔ fail 翻转时发**;`none` ↔ 有结论(场景加/删了断言)
    不发;
  - 发送条件:`check_status ≠ check_notified_status` **且**
    `check_status` 与 `check_notified_status` 均为 `{pass, fail}` 之内的
    翻转 **且** `now - check_notified_at ≥ 节流间隔`;发送后回写两者;
    **`check_notified_at` 为空时按「已满足间隔」处理**(定稿小项:静默
    回写不落通知时间,空值若按间隔未满足算,静默回写后的第一次真翻转
    会被挡一拍;I2 单测覆盖);
  - **初始化静默**(v1.3):`check_notified_status ∈ {'', unknown}` 时
    只回写 `check_notified_status`(不落 `check_notified_at`、不发)
    ——存量迁移后首跑/新建任务首跑不会产生全量通知风暴。**已知取舍**:
    存量实例迁移后第一次执行若直接 fail,这次不发结论通知——此类实例
    改造前一直在走 `fail_streak` 运维通知,不存在「没人知道」,接受;
  - 被节流的翻转**下次执行自动补发**(状态还差着一拍),不丢。
  节流间隔 = 周期(口径同下方过期计算)。
- **outputs**:`run ≠ ok` 不覆盖 `last_outputs`(卡片继续显示上次数据);
  `run = ok` 时无论 check 都写入(fail 的输出本身就是证据)。
- **`on_change` 新基准**:`check_status` 翻转,**或** outputs 变化。
  变化的比较口径(R-C 写实):新 outputs 经 `_scrub` 脱敏后与
  `last_outputs` **序列化比较**(`json.dumps(..., sort_keys=True,
  ensure_ascii=False)` 字符串不等即变化)——键序稳定、深度覆盖、实现
  一行;字段级 diff 是渐进增强,本期不做。
- **过期 = 错过两次应有的触发**(v1.2/Q2,取代"now 距 next_fire 的
  时长 > 2×周期"的原案——`next_fire(cron, now) - now` 是**距下次触发
  还有多久**而非周期,临近触发趋近 0,正常实例会来回闪烁):
  `nf1 = next_fire(cron, last_run_at)`、`nf2 = next_fire(cron, nf1)`,
  `now > nf2 + 宽限` 判过期(宽限 2 分钟 = 调度节拍 15s + 准入顺延
  余量)。对不规则 cron(仅工作日等)同样成立;无 cron / 解析失败回退
  现状 1 小时(fail-open 到旧行为)。**通知节流的"周期"同此口径**。

### 2.4 存储变更(一次加列,收尾批删除旧列)

`integration_tasks` 实例层:

| 列 | 变更 |
|---|
| `last_status` | I2 批内保留(双出过渡,投影规则见 §2.5),**I3 验收通过后随 I3.5 删除** |
| `run_status` | 新增 String(16) 默认 `''` |
| `check_status` | 新增 String(16) 默认 `''` |
| `check_message` | 新增 Text,失败断言摘要截断 500 字符 |
| `check_changed_at` | 新增 UtcDateTime 可空 |
| `check_notified_status` | 新增 String(16) 默认 `''`(Q3:结论通知边沿合并的状态回写位) |
| `check_notified_at` | 新增 UtcDateTime 可空(v1.3:上次**通知**发出的时间——节流间隔的基准;与 `check_changed_at` 语义分立:被节流时结论先变、通知后发,两者会分开,不可借用) |

存量迁移(R-A 修正):

| 现状行 | 映射 |
|---|
| `last_status=passed` | `run=ok, check=unknown`(下次执行校正) |
| `last_status=failed` 且 `paused_reason='auth_failed'` | **`run=auth, check=unknown`**——auth_failed 暂停不按周期重试,不手动恢复永无「下次执行」,映射成 channel 会永远错标最严重分类;行上有 `paused_reason` 可精确判别 |
| `last_status=failed`(其余) | `run=channel, check=unknown` |
| `last_status=timeout` | `run=timeout, check=unknown` |

其余不做回填推断,下次执行自愈。

### 2.5 读取侧

- **`/cards`**:**I2 起双出**——新字段 `runStatus / checkStatus /
  checkMessage / checkChangedAt / stale`(按 §2.3 周期口径计算)与旧
  `lastStatus` 并存;I3 前端切到新字段并验收后,I3.5 删旧列与出参。
  **旧字段投影规则(Q4 写实,I2 重写 `_finish` 后旧前端读到的
  `lastStatus` 必须有定义)**:`passed` ⟺ `run=ok` 且
  `check ∈ {pass, none}`;`timeout` ⟺ `run=timeout`;其余一律
  `failed`——过渡期旧卡片显示与现状语义一致(检查不通过仍显示失败,
  不会因 run=ok 而显示正常)。
- **FunctionCard**(四模板共用状态叠加层):主状态灯显示检查结论
  (pass 绿 / fail 红 / none 无灯只显运行状态 / unknown 灰);运行异常
  显示角标(「凭证失效 / 超时 / 网络异常 / 契约不符 / 通道故障」),
  主结论置灰 + 「上次结论 · N 分钟前」;M 档 check=fail 显示 `checkMessage`,
  运行异常显示 `lastError` 摘要;kv / counter / list 数据区按 §2.3
  保留上次数据,运行异常只置灰不清空;**角标优先级按 D13:暂停 > 停用
  ("已停用")> 过期,高优先级角标在场时不叠加过期置灰**。
- **IntegrationCenter 列表**:「状态」列拆「检查结论」「运行状态」两列;
  立即执行回显改两段式(「运行正常 · 检查不通过:xxx」)。

---

## 3. 设计:平台模式只读口径补全

### 3.1 判定口径(与取数视图统一)

一个步骤满足任一即视为只读:

- 方法 ∈ `GET / HEAD / OPTIONS`;
- **plate 锚点步骤**:端点 `metadata.query_safe = true`(从 `/full` 契约
  读取;钉修订场景按 `meta.plate` 修订取,与现取 method 路径一致)。
  **实施确认点(R-E)**:`plate_client.get_endpoint_full` 的 `EndpointFull`
  投影若未透出 `metadata`,补投影字段(plate 端已有,平台侧小增量);
- **`ext:` 锚点步骤**:外部目录条目 `query_safe = true`;
- 无锚点的手写原始调用:只认 method,fail-closed。

**真源说明(v1.2 更正)**:取数视图的 `query_safe` **不是** view 级独立
声明——plate 侧 `gimbal_plate/service/query_views.py:81` 的
`"query_safe": ep.metadata.query_safe` 表明它本就从端点元数据派生,
view dict 只是派生载体。即集成只读闸与取数视图消费的是**同一个真源**
(契约元数据),收敛为一个判定函数的理由比 v1.1 表述的更强:共享
`(method, query_safe)` 的取数与裁决,外部目录是元数据的第二个来源
(同形状字段)。

### 3.2 外部目录加字段

- `external_endpoints` 新增 `query_safe Boolean NOT NULL DEFAULT false`。
- **标记权限 = admin**(与外部接口登记一致,写接口现均为 `AdminUser`),
  标记/撤销均写审计:新增动作 `external_endpoint.query_safe`,
  `detail` 带接口名与别名(审计页人话口径,与资源名快照机制对齐)。
- **OpenAPI 导入不自动标记**:即使 spec 写了 `x-query-safe` 也只预填
  待确认,需人工确认——误标意味着平台账号可能执行写操作。
- **保存平台模式任务时**:不满足只读口径的步骤按
  「步骤 i(POST,未标 query_safe)」列出判定依据。

### 3.3 不改变的部分

- 写操作仍只走个人模式(决策 5、10)。
- 执行前二次检查保留:标记被撤销后,平台模式实例下次执行失败收口,
  分类 `run=channel`;**`lastError` 用固定前缀「只读检查未通过:」**
  (v1.2 小项:卡片角标据此显示人话,而非裸的"通道故障")。

---

## 4. 执行器侧修复(前置条件)

`gimbal/statemachine/engine.py`:

- `_handle_prepare`:hard_failed 时设 `_error_phase = "preparing"`,
  `_error = "[preparing] <首条失败策略 message>"`;
- `_handle_extracting`:同款,`extracting`。

写法与 verifying 现有实现(engine.py:340-345)一致,每处两行。

影响:`error_kind` 从错误的 `none` 变为 `logic`;STEP_FAILED 事件有了
可读文案;结构化日志 S6 摘要、执行详情行级失败原因同受益。

回归:引擎单测补两个阶段 hard_failed 的 `error_phase` / `error_kind`
断言;平台侧 `test_failure_digest` 跑一遍。

---

## 5. 批次与验收

| 批 | 内容 | 规模 | 验收 |
|---|---|---|---|
| **I1 执行器** | §4 两个 handler 补 `error_phase` / `_error`;单测 | S | prepare / extract hard_failed 的 `error_kind=logic`、`error_phase` 正确;引擎测试全绿 |
| **I2 后端状态拆分** | 迁移(§2.4,R-A 映射 + `check_notified_status`/`check_notified_at`);分类函数(§2.2);`_finish` 重写(§2.3,含 on_change 序列化比较、边沿合并节流、双触发过期);`/cards` **双出**新旧字段(含 Q4 旧字段投影);结论变化通知类型 | M | 分类函数表驱动单测覆盖 §2.2 全部分支(**timeout 与 transport 分立两格**、`error_phase=timeout/cancelled → run=timeout`、`halted → channel`、软失败 → pass);断言失败不累加 `fail_streak`、不暂停;运行失败保留 outputs 与上次结论;**边沿合并:周期内 fail→pass 被节流后下次执行补发恢复通知;`check_notified_status` 初始为 ''/unknown 时首跑静默回写零通知(无通知风暴);none↔有结论不发;`check_notified_at` 为空时按已满足间隔——静默回写后的首拍翻转即发,不被节流挡**;**双触发过期:临近触发的正常实例不闪烁,错过两次触发才过期,*/1 与每天两种 cron 正确,cron 坏回退 1 小时**;**旧字段投影:check=fail 且 run=ok 时 `lastStatus=failed`**;迁移后 auth_failed 暂停实例显示 `run=auth` |
| **I3 前端** | FunctionCard 状态叠加层;IntegrationCenter 拆两列、两段式回显;全部读取切新字段 | M | vitest 四模板 × {pass, fail, none, 运行异常};vue-tsc 零错;浏览器走查:故意断言失败 / 错 token / 停对端服务三态互不混淆 |
| **I3.5 收尾** | 删 `last_status` 列与 `/cards` 旧出参(单独迁移) | S | 全库无 `lastStatus` 残留(前后端 + 测试);回归全绿 |
| **I4 只读口径** | 统一判定函数;plate `query_safe` 接入(含 EndpointFull 投影确认);`external_endpoints.query_safe` 字段 + 登记页开关 + 审计动作 | S-M | 平台模式下标了 `query_safe` 的 POST 查询可保存执行;未标记拒绝并列判定依据;撤销标记下次执行失败收口;取数视图回归全绿 |

顺序:I1 → I2 → I3 → I3.5;I4 可与 I2/I3 并行。门禁:后端全量 pytest、
前端 vitest + vue-tsc、引擎单测。

---

## 6. 拍板记录

| # | 问题 | 拍板 |
|---|---|---|
| D1 | 提取/前置失败(响应结构变了)归哪类 | **运行异常·契约不符**——被检系统一升级就报「检查不通过」会误导;要检查的内容写成断言 |
| D2 | 场景无断言时的检查结论 | **`none`**,卡片只显示运行状态;不把「跑通了」等同「检查通过」 |
| D3 | 结论变化通知发给谁 | 个人模式发持有人;平台模式发模板 owner。订阅者级通知依赖订阅关系(现状在布局里),后置 |
| D4 | 外部目录 `query_safe` 标记权限 | **admin** + 审计;导入不自动标记 |
| D5 | `last_status` 处理 | **双出过渡、I3.5 删除**(v1.1 修订 R-B:原「前后端同批切换」与批次顺序矛盾,双出消除中间态) |
| D6 | 软断言映射黄灯 | **本期不做**;分类表显式记「仅软失败 → `check=pass`(当前口径)」,报告重构(task 3)引入 warn 档后再细分 |
| D7 | 存量 auth_failed 暂停实例的迁移映射 | **`run=auth`**(v1.1 修订 R-A:此类实例不按周期重试,映射 channel 将永远错标) |
| D8 | on_change 的 outputs 变化比较 | **脱敏后序列化比较**(sort_keys 字符串不等即变化);字段级 diff 后置 |
| D9 | 结论翻转通知频控 | **边沿合并**(v1.2/Q3 引入,v1.3 补全):仅 **pass↔fail** 翻转发送(none↔有结论不发);`check_notified_status`+`check_notified_at` 双回写位,状态差一拍且距上次通知 ≥ 周期才发(**`check_notified_at` 为空按已满足间隔**——静默回写不落通知时间,首拍真翻转不被挡);**初始 `''`/unknown 静默回写不发**(防全量通知风暴;存量首跑直接 fail 不发——改造前有 fail_streak 运维通知兜底,接受);被节流的翻转下次执行补发,不吞恢复通知 |
| D10 | 过期计算 | **双触发法**(v1.2/Q2):`now > next_fire(cron, next_fire(cron, last_run_at)) + 2min` 判过期("错过两次应有的触发");不规则 cron 同样成立;通知节流间隔同此周期口径;cron 坏回退现状 1 小时 |
| D11 | I2 期间旧字段 `lastStatus` 投影 | `passed ⟺ run=ok ∧ check ∈ {pass, none}`;`timeout ⟺ run=timeout`;其余 `failed`——过渡期旧卡片语义与现状一致 |
| D12 | `error_phase=timeout/cancelled` 与 `halted` 的归类 | **timeout/cancelled → `run=timeout`**(Q1:这两个标记不经 calling 类型化,不补会落兜底错判 contract);`halted` 仅调试链 → `run=channel` |
| D13 | 卡片角标优先级 | **暂停(凭证失效/缺凭证)> 手动停用(`enabled=false`,显示"已停用")> 过期置灰**——暂停与停用的实例必然过期,双提示是噪音,其角标出现时不叠加过期置灰(`enabled` 列已核实存在,integration_task.py:76);撤销 query_safe 的闸失败 `lastError` 前缀「只读检查未通过:」 |

---

## 7. 非目标

- 平台侧输出值规则引擎(断言替代,§2.1);
- 集成执行历史(维持「只保留最近一次」);
- suite 作为集成目标(`target_type=suite` 已预留,随 Suite 侧排期);
- MeterSphere 签名器、知识类拉取(原设计 P4);
- 字段级 outputs diff 与软断言 warn 档(随报告重构)。
