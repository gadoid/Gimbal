# 入站执行参数(params)+ raw 方案 + clientRef 幂等 — 开发方案(定稿)

- 日期:2026-11-13
- 分支:feat/plate-s1
- 状态:开发方案定稿(三轮评审收敛;实现待批准动工)
- 评审轨迹:params 通道设计 → carry 覆盖语义 → 方案级 carry 开关 → raw 保留字虚拟方案 + 契约上移场景级 → clientRef 幂等

## 0. 决策记录(终版八条)

1. **参数通道 = 「场景声明契约,请求只带值」**。场景级声明
   `paramSlots`(槽位白名单)+ `paramsStrict`(全量校验开关);
   `POST /api/runs` 的 `RunRequest` 新增 `params` 值字典。M1 安全边界
   (runs.py:48 `入站调用只能选择配方,不能携带配方`)不推翻:槽位是
   场景属主预先声明的可信白名单,外部只填值,不定义形状。
2. **契约上移场景级**(评审终版,替代早期「方案级 paramSlots」形态):
   "这个场景允许外部填什么"是场景的属性而非某个方案的属性
   (assertion_registry 同款先例);真实方案回归纯配方职责。
3. **保留字虚拟裸方案 `schemeId:"raw"`**(用户提案采纳,替代「自动
   落库裸方案实体」):零存储零迁移,派发器保留字分支;语义 = carry
   关闭 + 不取任何方案配方。任何场景天然拥有,通用 id 免创建、免查询
   ——外部调用方不需要先查方案列表。真实方案 id 是 `rs-NNN` 命名
   空间(scheme_store.py:63),与保留字无冲突。
4. **真实方案不新增 carry 字段**(评审裁定):「不带 carry」需求由
   raw 接管;真实方案一律维持现状 fill_missing,字段最少、语义最简。
5. **虚行注入,零新机制**:params 校验通过后在派发段合成为**单虚行**,
   走数据集行既有通路 —— `compose_scenario` 行值合入 `config.vars`
   (run_prepare.py:455,行胜于基线、`coerce_row_value` 类型还原)
   一行不改;模板展开/断言/遮罩链全部同源。
6. **安全闸 fail-closed**:参数值含 `${` → 422 `param_template_forbidden`
   (先于类型校验)——值若携带模板引用,会经引擎模板展开把凭证嵌进
   出站请求(凭证外送);null 值 → 422 `param_value_null`(要表达空
   用空串,与数据集三态语义对齐;`coerce_row_value` 对 null 穿透,
   行为未定义,故显式拒)。
7. **strict = 平台验证的完备性,不是调用方自我声明**(否决请求级
   `-full` 开关:那是配方指令,破 M1 口子)。方案……场景声明
   `paramsStrict: true` 时,派发前扫描 steps 全部 `${var.*}` 占位,
   每个占位须 params 给值或基线非空,缺失 → 422
   `param_placeholder_missing`(报完整缺失清单)。
8. **clientRef 幂等**(评审补充,订单场景刚需):外部投递天然
   at-least-once,`execution.client_ref` 现仅落库无去重(execution.py:136)
   —— 网络重试 = 重复业务订单。新增(执行身份, client_ref)部分唯一
   约束 → 重复提交 409 `duplicate_client_ref` 回显原 executionId
   (重跑走既有 rerun);列表增 `clientRef` 过滤参数。

## 1. 背景与动机

外部系统(webhook v4 个人访问令牌)当前可以触发场景执行,但传参面
是空的:

- 令牌调用携带 `dataSetIds / dataSetSelection / serviceBindings /
  injectionEntryIds` 一律 422 `inbound_field_not_allowed`
  (runs.py:54 `_INBOUND_FORBIDDEN_FIELDS`,M1 修复方案 2026-11-01 §1);
- 唯一能动态带值的通道是 `steps` 临时调用(adhoc)——脱离已存场景的
  裸调用,丢掉绑定/断言注册表/凭证槽位/方案全部平台能力。

**目标用例**:订单创建类集成——外部系统每笔订单参数全量不同
(单号/金额/客户/明细……),需要「同一场景 + 每次不同全量参数」
的直通调用,且网络重试不得产生重复订单。

**为什么 adhoc 不够**(设计 §2.3):请求形状每次现写、地址只按端点/
别名解析、断言白名单三样、无方案契约与治理。让上游系统每次现写整个
请求等于绕开平台所有治理面。

## 2. 语义

### 2.1 场景契约(场景属主维护)

```jsonc
// 场景 draft 容器(与 assertion_registry 同层,平台侧字段,不进 plate)
"paramSlots": [
  {"name": "orderNo",  "required": true, "maxLength": 64,
   "pattern": "^PO[0-9]{8}$", "description": "采购订单号"},
  {"name": "amount",   "type": "number", "required": true},
  {"name": "customer", "required": true, "maxLength": 128},
  {"name": "memo",     "required": false, "maxLength": 256}
],
"paramsStrict": true
```

- `ParamSlot`:`name`(1-64,`^[A-Za-z0-9_]+$`)、`type`
  string|number|boolean(缺省 string)、`required`(缺省 false)、
  `pattern`(≤256,仅 type=string 合法)、`max_length`(缺省 256,
  上限 4096)、`description`;
- 槽位 `name` 必须命中场景 `config.vars` 已声明标量键(写时校验,
  create 与 PUT 都跑——PUT 重验防「删变量后槽位悬空」);生成式
  spec 变量不可指(`_scalar_vars` 调色板口径,data_set_store.py:30);
- 槽位数上限 64(与 RunOptions 上限口径同源);
- `pattern` 是作者约束值格式的工具,**对外部可达槽位建议必配**
  ——路径注入缓解(见 §4)。

### 2.2 请求三态矩阵

| 请求 | 语义 | carry |
|---|---|---|
| `{"scenarioId", "params"}` | 混合模式:默认方案配方 + 业务参数 | 照旧补(渠道字段平台管) |
| `{"scenarioId", "schemeId":"raw", "params"}` | 全量模式:裸执行,纯参数 | **不补** |
| `{"scenarioId", "schemeId":"rs-NN", "params"}` | 指定方案配方 + 业务参数 | 照旧(fill_missing,现状语义) |

```jsonc
POST /api/runs   Authorization: Bearer gtk_…(个人访问令牌)
{"scenarioId": "sc-order-create",
 "schemeId": "raw",
 "params": {"orderNo": "PO12345678", "amount": 199.0,
            "customer": "某客户", "memo": "加急"},
 "clientRef": "ord-20261113-0001",        // 幂等键(决策 8)
 "callbackPath": "/hooks/gimbal"}         // 完成回调(可选)
```

- `params` 值类型:`string | number | boolean`(不含 null);
- `"params": {}` 等价缺省(不入校验、不触 strict);
- 校验通过后 params **原样放行**——改写就是解释,解释就是风险面。

### 2.3 校验器五道闸(顺序固定,422 `code`/`fields` 风格对齐
`_reject_inbound_recipe` runs.py:88-97)

1. 场景未声明槽位且带 params → `param_slot_not_declared`
   (报错文案指引先在场景声明契约);
2. `required` 槽缺失 → `param_required_missing`;未声明键 →
   `param_not_declared`(报完整未知键清单);
3. 逐槽:**null → `param_value_null`;值含 `${` →
   `param_template_forbidden`(先于类型校验)**;类型
   (number/boolean 接受原生 JSON 类型,string 值按基线还原口径接受
   数字串,同 `coerce_row_value` :424)→ pattern → 超长;
4. strict(场景 `paramsStrict: true`):扫描 steps +
   `config.setup/teardown` 的 `${var.*}` 占位(复用
   `services/jsonpath.find_template_var_refs` :752),每个占位须
   params 给值或基线非空 → 缺失 `param_placeholder_missing`
   (完整清单)。
5. raw 模式无方案配方可依据,契约校验全部以场景级契约为准(两态
   同源,无特殊通道)。

### 2.4 互斥族(422/409)

| 同发组合 | 结果 |
|---|---|
| steps + params | 422 `run_target_ambiguous` 系 |
| graph + params(JWT) | 422 `param_graph_conflict` |
| params + dataSets/dataSetSelection(JWT) | 409 `run_source_conflict` |
| params + injectionEntryIds(JWT) | 409 `run_source_conflict`(review ①:虚行路径跳过 `compute_run_fanout`,注入条目解析/悬空 409 在其中——组合无消费场景,砍掉比缝合便宜) |
| schemeId:"raw" + dataSets(JWT) | 409(裸配方无数据集语义) |

## 3. carry 覆盖语义边界(与既有机制的关系)

- **params(raw)与 carry 结构性无交集**:raw 跳过 carry 上下文
  构建;params 值只能经 `${var.*}` 占位落 body——「占位即主权」。
- **混合模式下 carry 语义不变**:`_apply_carry` 是 setdefault 填缺失
  (run_materialize.py:395「body 已有键绝不覆盖」)——body 写了
  占位的键 carry 天然让位,缺键才补(混合模式的渠道字段价值所在)。
- **adhoc(临时调用)零改动**(评审定):无方案概念、行为由既有测试
  钉住——显式值恒赢(setdefault)、缺键照补。全量集成一律走
  raw + params,不用 adhoc。
- 字面值恒最硬:body 写死的值 params/carry 都无效(params 只经
  `${var.*}` 起作用)。

## 4. 威胁模型

| 攻击面 | 缓解 |
|---|---|
| 外部值携带 `${auth.x.token}` 借模板展开外送凭证 | **模板闸**(决策 6):值含 `${` 即 422,不解释、不转义、不降级;JSON `\u` 转义解码后仍命中闸(解码在解析期) |
| **注入清单恒完备不变量**(评审新增) | 令牌范围检查从场景 steps 扫描别名/凭证(runs.py:554-576),模板闸保证 params 无法引入新的 auth 引用 → 派发期算出的注入清单在 params 下恒完备,不存在「参数把凭证引到别处」的通道 |
| 参数值改写被测地址/凭证指向 | 结构上不可能:参数只进 `config.vars`,地址链(环境部署表)与凭证链(槽位绑定)不在 vars 可达面 |
| **路径/查询注入**(review ④) | 参数经 `${var.*}` 若被场景引用进 call.path/path_params,约束不足的值(`"?x=1"`、`"/../"`)可同主机内改写路径。平台不做通用消毒(误伤合法值),缓解归作者:**外部可达槽位必配 `pattern`**(文档强制建议) |
| 用 params 绕过 dataSetSelection 禁令 | 契约在场景(属主维护),请求只带值;行引用类能力仍服务端持有 |
| 超大值/海量键 | 槽位 64 上限 + maxLength 4096 + 请求体既有 50m 封顶 |
| pattern ReDoS | 作者=可信方,接受为已知风险(文档建议保守写法) |
| **网络重试 → 重复业务订单** | **clientRef 幂等闸**(决策 8) |
| 方案/契约漂移 | 契约随场景 payload 走(复制/转让/fork 自动携带);PUT 场景重验槽位防悬空 |

## 5. 接收侧实现落点(五段链路,file:line 为实现依据)

```
POST /api/runs
  │ ① 路由入口      runs.py post_run(L456)
  │    _reject_inbound_recipe(仅令牌 L471,不含 params 天然放行)
  │    → 互斥族判定 → 场景加载(L490)
  │    → 令牌:_apply_scheme_recipe(L504;raw 则跳过方案应用)
  │    → 令牌范围检查(L554:别名/凭证 ⊆ 令牌范围,无只读闸,
  │      POST 步骤可过——订单用例成立)
  │    → validate_inbound_params(新,契约自场景行)
  │ ② 契约读写      scenario draft 容器(assertion_registry 先例)
  │    create/PUT 写时校验槽位 ⊆ vars 标量键
  │ ③ 派发          run_dispatcher.dispatch_target
  │    虚行合成(L1042-1044 旁,跳过 compute_run_fanout——
  │    与 suite 预检共用禁改;按签名逐项合成其余返回值)
  │    clientRef 幂等预查 → 409 duplicate_client_ref(回显原 id)
  │    config_json 增 inboundParams/carryPolicy/paramsStrict
  │    job payload(L1363-1397)增 skip_carry —— worker 不回查
  │    上下文(:1343 注释),执行状态必须随任务下发
  │ ④ 装载          _fanout → prepare_exec 新 kwarg skip_carry:
  │    True 时 prep.carry_ctx = None(run_prepare.py:661-675;
  │    materialize 的 None 分支既有,零改动)
  │ ⑤ 配置器+引擎    compose_scenario(run_prepare.py:455)零改动
  │    虚行 → coerce_row_value 基线类型还原 → config.vars 稀疏覆盖
  │    → plate /convert → 引擎模板展开 ${var.*} → 出站请求
  ▼
执行记录 config 快照(run_dispatcher.py:1275-1339):
inboundParams / carryPolicy("off" 仅 raw)/ paramsStrict
```

**clientRef 幂等**:执行模型两个部分唯一索引——
`(token_id, client_ref)` WHERE 两者非空;`(user_id, client_ref)`
WHERE token_id 为空且 client_ref 非空(JWT 维度)。入队前预查命中
→ 409 `duplicate_client_ref`(detail 带原 executionId);并发竞态
由唯一索引兜底(IntegrityError 捕获回查映射同 409)。**alembic 0056**
同步建索引(建前查重容错)。重跑走既有 rerun。
查询:`GET /api/executions?clientRef=…`(可见性口径内过滤)。

**rerun 回放**(executions.py:874-900):读回 `inboundParams` →
`body.params`、schemeId("raw" 原样);快照语义不重校验(与
dataSetSelection 回放同口径)。

## 6. 调用方对接指南(定稿随 http-api.md 落地)

- **样例双版本**:curl(bash)+ PowerShell `Invoke-RestMethod`
  原生(curl.exe 在 PS5.1 会剥双引号——实测踩坑);`Content-Type:
  application/json` 必带。
- **令牌前置**:个人访问令牌(PAT)scope 须覆盖场景引用的别名与
  凭证(范围检查 runs.py:554,否则 403 `inbound_denied`);场景
  POST 步骤可过闸(无只读限制)。
- **错误码自助表**:401(令牌过期/吊销 → 重新生成)/ 403(归属
  not_owner、范围 inbound_denied)/ 422(校验,fields 自描述)/
  409(互斥、`duplicate_client_ref` 带原 executionId)/ 201 →
  轮询 `GET /api/executions/{id}` 或回调。
- **回调**:目标 = 令牌登记 callbackUrl + 请求 callbackPath;
  HMAC 签名 `t=<ts>,v1=<hex>`(webhook_outbox.py:239)+ 指数退避
  重试;调用方验签后按 runId/status 处理,clientRef 回显关联。
- **幂等用法**:每笔业务单据给稳定 clientRef;重试原样重发 →
  409 即说明首投已成功,拿原 executionId 查结果即可。

## 7. 实施切分(批准后动工)

1. **① 校验器**:services/run_params.py 纯函数 + 全 422 码矩阵单测;
2. **② 契约读写**:ScenarioDraft 字段 + scenario_store 存取 +
   create/PUT 写时校验;
3. **③ 路由**:互斥族 + raw 保留字分支 + params 校验挂接;
   `_apply_scheme_recipe` 返回所应用方案(现返回 None,L100-154,
   唯一调用方);
4. **④ 派发**:虚行合成 + config_json 三键 + job payload skip_carry
   + `prepare_exec` kwarg + **clientRef 唯一索引(models)+ alembic
   0056 + 幂等预查**;
5. **⑤ rerun + 查询**:params/schemeId 回放 + clientRef 过滤;
6. **⑥ 测试**:tests/test_run_params_inbound.py(fixtures 仿
   test_adhoc_run.py `inbound_fixtures`;矩阵 parametrize 对齐
   :251-272 样板)——契约读写/全 422 码/null/raw 无 carry/
   混合照补/幂等 409+查询/rerun 回放;回归六个既有测试文件;
7. **⑦ http-api 文档**(§6 内容落地)。

## 8. 挂账(不进本期)

- **契约发现端点**:`GET /api/runs/param-slots?scenarioId=…`
  (principal_or_user 面)——scenarios 路由 JWT-only,外部令牌方
  v1 靠线下约定获取契约;
- 前端槽位契约编辑面(方案编辑器/场景设置);
- PAT scope 细分(如「无参调用 only」);
- adhoc 行为零改动(既有测试钉住)。

## 9. 兼容性

- 未声明契约的存量场景:params 带 422,行为零变化;
- 旧客户端:params 是新键,pydantic 静默忽略,无误带风险;
- 存量 client_ref 列数据:0056 建索引前查重容错;
- 令牌面:`_INBOUND_FORBIDDEN_FIELDS` 不含 params(新字段天然放行),
  其余禁令原样。
