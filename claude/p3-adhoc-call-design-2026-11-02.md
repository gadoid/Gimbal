# P3 · 临时调用 · 设计实现方案（2026-11-02）

基线：`feat/plate-s1` @ `4cfa47f`（入站调用与 webhook 的 P0–P2 已收口）。
修订：2026-11-02 实现评审后更正 §四.3 别名校验口径（服务名 vs 系统名），评审记录第 2 节（评审记录按惯例不入仓）。同日对齐实现：§三 补 `pathParams`、§六 `RunTarget` 去掉 `owner_id`、§十一 `adhoc_invalid` 覆盖锚点不存在。
前置：`claude/inbound-webhook-design-v2-2026-11-01.md` 第六节（本方案取代它）、`claude/inbound-webhook-fix-review-2026-11-01.md`。

---

## 一、定位

临时调用 = **不先在平台上建场景，直接按 plate 定义调用一次接口**的入口。产物与普通场景执行完全相同：一条执行记录 + 一次 `execution.finished` 回调。

- **谁来调**：外部系统 / Agent，用入站凭证（`gic_`）+ 用户签发给该别名的 grant（`ggt_`），即个人模式。
- **请求里带什么**：调哪个接口（plate 锚点）、填什么值、要取回什么（`extract` / `assertion`）。
- **平台补什么**：method / path / 字段结构（plate 定义）、服务地址（别名 base_url）、凭证（grant 用户凭证池，经别名 `credential_alias`）、carry、版本（环境版本线）。
- **谁发请求**：执行器。平台把请求组装成一份标准场景，走与普通执行同一条装载链（`prepare_exec` → convert → 物化），交给执行器发出；平台本身不发 HTTP。

---

## 二、决策

| # | 决策 | 结论 | 状态 |
| --- | --- | --- | --- |
| P3-D1 | 平台模式（无 grant）能否使用临时调用 | **不开放**，只允许个人模式（带 grant）。临时调用的灵活性应绑定到具体用户的授权 | 已定（11-02） |
| P3-D7 | JWT 用户能否使用临时调用 | **本期不开放**：前端无入口，接口只对入站个人模式开放，避免出现未设计的调用面 | 已定（11-02） |
| P3-D2 | 请求体是配方，按 M1 原则收紧 | steps 只能带锚点、值、取回声明；method / path / headers / 服务地址 / 凭证一律由平台补 | 已定 |
| P3-D3 | 策略白名单 | 只放行 `extract`、`assertion`、`assign` | 已定 |
| P3-D4 | 多步 | 允许，上限 10 步（步间可用 `extract` → `${var}` 穿值）；不支持数据集、注入、编排 | 已定 |
| P3-D5 | 执行记录形态 | `kind='adhoc'`，`scenario_id='adhoc-<runId>'`，沿用 `suite_graph` 的占位 id 约定，不加列 | 已定 |
| P3-D6 | 版本 | 按服务别名所属环境的版本线取最新修订；请求可显式指定 `release` 覆盖 | 已定 |

---

## 三、请求契约

```http
POST /api/runs
Authorization: Bearer gic_…
X-Gimbal-Grant: ggt_…
Content-Type: application/json

{
  "steps": [
    {
      "endpoint": "settle.order.query",
      "service": "settle-sit",
      "body": {"orderNo": "PO20261030001"},
      "strategy": [
        {"kind": "extract", "expression": "$.data.status", "target": "status"},
        {"kind": "extract", "expression": "$.data.amount", "target": "amount"}
      ]
    }
  ],
  "release": {"settle": "2026.10#3"},
  "clientRef": "agent-task-8812",
  "callbackPath": "/agent/callback"
}
```

**`steps[*]` 允许的字段**（其余字段一律 422 `adhoc_field_not_allowed`，并列出字段名）：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `endpoint` | 是 | plate 接口锚点 `<系统>.<接口>`；系统取首段 |
| `service` | 是 | 服务别名名（与场景中 `call.service` 的取值同义） |
| `body` | 否 | 业务参数；GET 类接口由执行器转 query（现有分派口径） |
| `pathParams` | 否 | plate 路径模板 `{key}` 占位的**值** `{key: 标量}`；模板本身仍来自 plate 定义（实现评审补项：不补它，带路径参数的接口永远调不了） |
| `strategy` | 否 | 只允许 `extract` / `assertion` / `assign`（P3-D3），结构与场景 step 的策略条目一致（执行器 M2 schema，`extra='forbid'`：如 `extract` 为一条一个变量，`expression` + `target`） |

**顶层**：`steps` 与 `scenarioId` 互斥（同时出现或都缺失 → 422 `run_target_ambiguous`）；`release`（可选，`{系统: "<线>#<修订>"}`）；`clientRef`、`callbackPath` 同场景执行；`runOptions` 不接受（临时调用没有截断与重复的语义）。

明确不接受：`call.method` / `call.path` / `call.headers` / `call.user` / `call.protocol`、`config.*`（含 `services`、`users`、`vars`）、`serviceBindings`、`dataSetIds`、`dataSetSelection`、`injectionEntryIds`、`graph`。

---

## 四、校验（全部在派发前完成，不通过即 4xx，不建执行行）

按顺序：

1. **身份**：入站且带 grant（个人模式）。平台模式 → 403 `adhoc_requires_grant`（P3-D1）；JWT → 403 `adhoc_inbound_only`（P3-D7）。
2. **结构**：字段白名单（第三节）、步数 1–10、策略白名单。
3. **服务别名**：`service` 必须是已登记别名，`kind=plate`，且别名的 `base_service` **等于锚点在 plate 中声明的 service**（别名不能拿来调别的服务的接口）。不满足 → 422 `adhoc_service_mismatch`。
   - 注意区分两个命名空间：锚点首段是**系统名**（`fin.account.query_balance` → `fin`），别名 `base_service` 是 plate **服务名**（`fin-service-sit` → `fin-service`）。现有被测系统都是「服务名 ≠ 系统名」（`fin` / `fin-service`、`platform` / `platform-service`），不能拿 `base_service` 与锚点首段比较。
   - 端点声明的 service 按锚点从 plate 取（`get_endpoint_full`，或目录端点列表按 id 查 `service` 字段）；锚点在目录中不存在时此处直接 422 `adhoc_invalid`。
   - 不一致时 `extra` 带 `endpointService` 与 `baseService`，`reason` 为 `service_mismatch`。
4. **地址落点**：用 `run_materialize.service_url_resolved(svc, declared={}, bindings={}, alias_base_urls=…)` 判定，别名无 base_url → 422 `adhoc_service_unresolved`（比留给引擎报错对调用方友好）。
5. **版本**：`release` 指定了则用它；否则取别名 `environment_id` → `Environment.lines[系统]` → 该线最新修订（`plate_client.list_line_revisions`）。取不到 → 422 `adhoc_version_unresolved`。此处按**系统名**（锚点首段）取版本线，与第 3 步按服务名比较不同，两处各用各的命名空间。
6. **接口存在与字段校验**：组装后调一次 `plate_client.convert`（与 preview-plate 同口径）；plate 拒绝（锚点不存在、未知字段、必填缺失、类型不符）→ 422 `adhoc_invalid`，`errors` 原样带回 plate 的逐字段错误。

第 6 步的 convert 结果不缓存到执行里——执行期按正常链路再 convert 一次，保证「派发前校验」与「执行」走同一代码路径，不分叉。

---

## 五、组装：请求 → 标准场景 payload

新增纯函数 `run_prepare.build_adhoc_payload(req, *, alias_rows, release) -> dict`，产出与库中场景同形的容器 `{"definition": …}`：

```text
definition.meta  = {name: "临时调用 · <别名> · <锚点>", plate: {<系统>: <线#修订>}}
definition.config = {}                       # 服务地址/凭证全部由装载链补
definition.steps[i] = {
  kind: "step", id: "s<i>",
  endpoint: <锚点>,
  call: {service: <别名>, user: <别名的 credential_alias 或省略>},
  request: {kind: "request", body: <body>},
  strategy: <白名单内的策略>,
}
```

要点：

- **method / path 不写入**：锚点步骤由 plate convert 按定义补全（现有锚点机制）。
- **凭证**：`call.user` 设为别名上的 `credential_alias`；装载链 `exec_auth_aliases` 会因别名默认命中把它纳入注入清单，按执行 owner（grant 用户）的凭证池解析。别名未配 `credential_alias` 时省略 `call.user`，接口若需认证由执行器步骤级报错。实现时需对照执行器 `call.user → AuthRegistry` 的取用方式确认这一点。
- **服务地址**：不写 `config.services`，由 `prepare_exec` 的别名 base_url（第③层）补齐。
- **carry**：由 `prepare_exec` 按锚点 carry 面注入，与普通执行一致。

---

## 六、派发：`dispatch_run` 拆两段

现在 `dispatch_run` 直接依赖库中的 `ComposerScenario` 行（`compute_run_fanout(db, scen, req)`、`_create_execution(scenario_id=scen.scenario_id, …)`、快照取 `scen.payload`）。拆为：

1. **取目标**（路由层）：
   - 场景执行 → `RunTarget(scenario_id, payload, kind="scenario")`；
   - 临时调用 → `RunTarget(f"adhoc-{run_id}", build_adhoc_payload(...), kind="adhoc")`。
   - `RunTarget` **不带 owner**：执行者始终是调用者本人，与拆分前 admin 代跑的语义一致，不借拆分改变它。
2. **按目标派发**（`dispatch_run(db, target, req, …)`）：校验、扇出、建执行行、快照、入队全部共用。`compute_run_fanout` 改为接收 `payload` 而非 ORM 行；临时调用没有数据集与注入，扇出恒为 1 行。

`run_id` 需要在取目标之前生成（占位 id 要用），`dispatch_run` 改为接收外部传入的 `run_id`。

**对拍**：拆分前后，现有场景执行的 run copy、`config_json`、快照逐字段不变（新增一条对拍测试钉住）。

---

## 七、记录与展示

- `executions.kind = 'adhoc'`；后端 `NON_SCENARIO_KINDS`、前端 `executionKind.ts` 各加一项。执行列表的场景 id 列、「同配置重跑」按钮按 `isScenarioBacked` 自动隐藏；重跑接口走已有的 `rerun_unsupported` 分支。
- `scenario_name` 写 `meta.name`（「临时调用 · 别名 · 锚点」），列表直接可读。
- `execution_snapshots` 存组装后的 payload，「当时调了什么」可追溯。
- `plate_pins` 由装载链照常写入（版本追溯）。
- 可见性沿用现有规则：owner（grant 用户）本人、admin、经由该别名的入站凭证。

---

## 八、回调

沿用 `execution.finished`，无新事件类型：

- `kind: "adhoc"`，`scenarioId: null`（占位 id 不对外暴露），其余字段同场景执行。
- 临时调用扇出恒为 1 行，满足 D10，`outputs` 取 `extract` 结果（已脱敏）。
- 多步时 `outputs` 合并各步 `extract`，同名后者覆盖前者（与集成链口径一致）。

---

## 九、平台模式只读检查的加固（随 P3 一并提交）

**核实结论（更正此前判断）**：此前我提出「平台模式只读检查不看策略层，`call` / `sql` 策略可能带来副作用」。核实执行器代码后：当前注册的策略只有 `extract`、`assign`、`assertion`、`sleep`（`gimbal/strategy/dispatcher.py`），**都没有对外副作用**；`call` 是步骤主调用的协议适配器，不是可挂在步骤上的策略；`sql` / `chaos` / `poll` 在当前执行器中不存在。所以**现在不存在这个漏洞**。

但策略可以由插件注册，将来新增的策略可能有副作用。做一处纵深防御：

- `integration_runner.is_scenario_read_only` 增加一条：步骤上出现**不在** `{extract, assign, assertion, sleep}` 之内的策略类型 → 判为不只读（fail-closed），`offenders` 写「步骤 i（策略 X 未知）」。
- 新增策略时，若确实无副作用，显式加入该集合。

---

## 十、数据模型

**无迁移。** 临时调用复用 `executions` 现有列（`kind`、`scenario_id` 占位、`caller_alias_name`、`grant_id`、`client_ref`、`callback_path_override`）与 `execution_snapshots`。

---

## 十一、错误码汇总

| HTTP | code | 场景 |
| --- | --- | --- |
| 403 | `adhoc_requires_grant` | 平台模式发起临时调用（P3-D1） |
| 403 | `adhoc_inbound_only` | JWT 发起临时调用（P3-D7） |
| 422 | `run_target_ambiguous` | `steps` 与 `scenarioId` 同时出现或都缺失 |
| 422 | `adhoc_field_not_allowed` | 出现白名单外字段 / 不允许的策略 / 步数越界 / 带 `runOptions` |
| 422 | `adhoc_service_mismatch` | 别名不存在、非 plate 别名、或别名 `base_service` ≠ 锚点声明的 service |
| 422 | `adhoc_service_unresolved` | 别名无 base_url |
| 422 | `adhoc_version_unresolved` | 取不到环境版本线或修订 |
| 422 | `adhoc_invalid` | 锚点在 plate 中不存在（§四.3，先于别名校验），或 plate convert 拒绝（§四.6）；均附逐字段 `errors` |
| 503 | `plate_unavailable` | 派发前校验期间 plate 不可达（取端点定义或干跑 convert） |

---

## 十二、实现检查点

- [ ] P3-1 路由：`RunRequest` 增加 `steps`、`release`；互斥与身份校验（第四节 1–2）
- [ ] P3-2 别名 / 地址 / 版本解析（第四节 3–5）
- [ ] P3-3 `build_adhoc_payload` 纯函数（第五节）
- [ ] P3-4 派发前 convert 校验与错误映射（第四节 6）
- [ ] P3-5 `dispatch_run` 两段拆分 + `compute_run_fanout` 改签名 + 外部 `run_id`（第六节）
- [ ] P3-6 `kind='adhoc'` 前后端登记、`scenario_name`、快照（第七节）
- [ ] P3-7 回调 payload 的 `kind` / `scenarioId` 处理（第八节）
- [ ] P3-8 只读检查的未知策略 fail-closed（第九节）
- [ ] P3-9 集成指南新增「临时调用」一章：请求契约、白名单、错误码、版本规则、示例

---

## 十三、测试

| 模块 | 用例 |
| --- | --- |
| 身份 | 平台模式 403；JWT 403；个人模式通过 |
| 结构 | `call.method` / `call.path` / `call.headers` / `config` / `serviceBindings` / `runOptions` 各一条 422；未知策略与 `sleep` 422；11 步 422；`steps` + `scenarioId` 422 |
| 别名 | 不存在 / external 别名 / 别名 `base_service` ≠ 锚点声明的 service 各 422；无 base_url 422；**夹具用真实形态**（系统 `settle`、端点 service `settle-service`、别名 `settle-service-sit`），并补一条「`base_service` = 系统名但 ≠ 端点 service」→ 422 |
| 版本 | 显式 `release` 生效；按环境版本线取最新修订；无环境 422 |
| 校验 | 锚点不存在、未知字段、必填缺失 → 422 且带 plate 逐字段错误；均不建执行行 |
| 组装 | `build_adhoc_payload` 产物：无 method/path、`call.user` = 别名 `credential_alias`、无 `config.services` |
| 执行 | 单步临时调用成功：执行行 `kind='adhoc'`、占位 id、快照为组装 payload、`plate_pins` 写入；凭证来自 grant 用户池；地址来自别名 |
| 回调 | `kind=adhoc`、`scenarioId=null`、`outputs` 为 extract 结果；多步合并 |
| 展示 | 执行列表隐藏场景 id 与重跑；重跑接口 409 `rerun_unsupported` |
| 对拍 | `dispatch_run` 拆分前后，现有场景执行的 run copy / `config_json` / 快照逐字段不变 |
| 只读加固 | 平台模式场景出现未知策略类型 → 只读检查不通过；`extract` / `assign` / `assertion` / `sleep` 不影响判定 |

---

## 十四、不在本期

- 平台前端的临时调用界面（JWT 用户入口）。
- 临时调用的定时执行（D4：定时必须引用持久化场景）。
- 数据集、断言注入、编排在临时调用中的使用。
- 「临时调用另存为场景」：有需求时另立项，可直接把快照里的 payload 落成场景。
