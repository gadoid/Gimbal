# GIMBAL 执行器重构 v2.1 —— 融合实施案

> 日期：2026-09-27
> 地位：本文件是执行器重构的**实施基准**。三方来源与裁决：
> - 架构蓝图取《GIMBAL 执行器重构方案 v2》（2026-09-25，概念终态）；
> - 施工纪律取《GIMBAL 执行器-Suite改造总案与三侧影响分析》（2026-09-24，三侧解耦/零回归护栏/灰度切换）；
> - 已落地基线取《GIMBAL执行器-协议中立与多线程-实施设计》（2026-09-27 上午批次：协议注册表、call union、六锁点、scenario 级并行、plate protocol 字段——全部存活，本文件在其上续建）。
> 与 v2 的核心分歧只有一条：**v2 批次 1 的三侧一次性切换被否决**，改为"新路径跑通 → 双读期 → 集中回收"三步；其余 v2 决策全部采纳。

---

## 一、裁决记录（v2 待确认项的批复）

| # | v2 待确认 | v2.1 裁决 | 理由 |
|---|---|---|---|
| 1 | `call.protocol` 缺省 http？ | **双读期缺省 http；回收批（F）后改显式必填** | 迁移期减少噪音；终态让协议拼写错误在编译期暴露 |
| 2 | Decision `by: human`？ | **不设字段；debugger 会话发出的 Decision 自动视为人工（标记 repaired）** | 决策来源框架已知，用户声明冗余且易错 |
| 3 | 生命周期条目走 strategy 表？ | **采纳** | 避免 fifth 表，符合"统一机制不统一接口" |
| 4 | 批次 1 三侧同窗切换？ | **否决**——拆为新路径（B-E）+ 回收批（F） | 见下节；909 处断言路径重写 + 2 个插件改造 + plate/平台联动，一个窗口不可验收 |

## 二、与 v2 的唯一结构性差异：三步回收替代一次性切换

v2 的终态（无兼容层）**照单全收**，但达成方式分三步：

1. **建新（批次 A-E）**：新契约（CallResult、render/send、拦截点、Plan/Unit、Registry）在旧路径旁边落地；新旧并存，旧形式照常可执行；每批验收门 = 新能力端到端 + **全量回归零新增失败**。
2. **双读（批次 E 完成后）**：迁移脚本（可重复执行）在演练环境跑通；特征化测试密度补到能撑住断言路径重写的验收强度；平台加"读事件流"能力但不删"读终态 JSON"。
3. **回收（批次 F，对齐总案批次 6 窗口）**：一次性删除旧形式（api 糖、旧 scratch 键、HTTP 钩子、嵌入式 Suite、RuntimeControl、占位策略）+ 三侧切换（plate 产 call、平台读 `run.finished`）+ 平台执行链重写。灰度开关、新旧链对账、可回滚三件套照总案 4.4。

双读期代价的自觉声明：期间存在双形状（scratch 双写、api/call 双形式、suite 双路径），**回收批不得顺延成常态**——批次 F 的进入条件写死（见 §五）。

## 三、批次表

| 批次 | 内容 | 验收门 | 状态 |
|---|---|---|---|
| 0 已落地 | 协议注册表 + call union（api 糖归一化）+ 六锁点/Archive 键空间化 + scenario 级并行 + plate `protocol` 字段 + CLI kind 分派 | 已验收（773 通过，零回归） | ✅ 2026-09-27 |
| **A 协议契约** | **CallResult 统一证据形状 + render/send 拆分 + 证据脱敏/截断 + scratch `call` 键双写 + 中立钩子收敛进执行器模板（可补丁）** | 新路径 `$.call.response.body.*` 提取断言端到端；旧断言路径零回归；echo 等自定义协议只实现 render/send 即可跑通 | 🔄 本文档 |
| B 编译与单路径 | 编译管线七阶段截断版（load/normalize/patch/desugar）；Plan/Unit + PlanPolicy/UnitPolicy；Engine+调度器 v1 走 Plan；run scenario/suite/launch 全走 Plan；compile/validate/resolve CLI；aggregate 模式 | 单场景与 aggregate suite 端到端；与旧路径结果对账一致 | ✅ 2026-09-27（resolve CLI 留批次 C——依赖 patch diff 展示；n_runs/retry/lock/needs/shared 非 Schema 缺省值由 validate_plan 明确拒绝并标注落地批次） |
| C 编排 | 静态分析三形态 + bind；compose/fanout/chain；shared 去重；control；before/after 括号；泛型 Registry 四张表 + `ext list --json` | 三模式端到端；三形态连线测试（A3 验收标准） | ✅ 2026-09-27（SuiteGraph kind=graph 与嵌入式 Suite 并存至 F；五层 patch 叠加与 expand 数据集展开留 D/后置；control.only 闭包按模式隐含依赖计算；blocked 为新判定状态，RunResult.blocked 计数） |
| D 并发完整版 | PlanPolicy.parallel 单元级线程池（v2 调度器）；n_runs/retry/lock 三种乘法；凭证按 (protocol,user) 单飞；并发测试基建（竞态注入/压力） | parallel 真跑 + 竞态测试通过；n_runs/retry 计数与计划清单对账 | ✅ 2026-09-27（repeat 编译期展开 ref#k，needs 引用重写为依赖全部变体；n_runs/retry 聚合 attempts，计数对账 total=Σattempts；lock 在"依赖满足、即将运行"时获取；AuthRegistry.singleflight_refresh + auth_expired→refresh_auth→重发一次（http 401 通道）；事件层 run 序号留批次 F；认证完整并入适配器（login 方法+6 authenticator 迁移）留批次 E 前置/F） |
| E 调试 | debugger 插件挂五个拦截点；STEP_FAILED Decision（retry=整步重跑，repaired 标记）；step_from/step_to；server 会话（SSE）+ 鉴权硬前置 | 经 server 单步调试一个运行中场景；patch 待发请求生效 | ✅ 2026-09-27（Decision 经 HookSignal.STOP 携带（str 兼容 abort）；STEP_BEFORE/CALL_BEFORE(patch)/STEP_FAILED 接入，STRATEGY_BEFORE 复用 dispatcher STOP→SKIP，CALL_AFTER 的 RETRY 留后；STEP_FAILED 决策点在 ScenarioRunner 层（teardown 已执行，重跑要求清理幂等——与 v2"teardown 前"的偏差成文）；repaired=人工 retry 后通过（RunResult.repaired 计数）；server: POST /runs 异步 + /runs/{id}/debug（GIMBAL_SERVER_TOKEN 硬前置）+ /runs/{id}/events SSE（Last-Event-ID 续传留 F）；SSE 事件无 seq——F 补） |
| F 回收与三侧切换 | 删除清单（api 糖/旧 scratch 键/HTTP 钩子/嵌入式 Suite/RuntimeControl/占位策略/空壳目录/SpecResolver）；迁移脚本正式执行（909 处断言路径 + 45 文件 + 平台存储 case）；4 插件改造（auth_headers→http 适配器内认证、其余→事件订阅）；plate convert 产 call；平台读 `run.finished`；协议显式必填 | 新旧链对账一致；plate 测试全绿；平台灰度切换；回滚演练通过 | 🔄 F-1 ✅（2026-09-27）：死代码/空壳删除、--fail-fast 接线、plate convert 产 call、存量 38 case 正式迁移。🔄 F-2a ✅（2026-09-27）：**安全前提经核查成立**（平台全链每次执行含 rerun 都重新 plate convert 物化，无历史 case.json 重放路径——证据 run_dispatcher.py:974/978、executions.py:424、reconcile 只标 failed）；据此落地：① 平台 run_materialize 修复（referenced_services/_apply_carry 读 call.service，api 兜底——plate call 化的隐藏依赖，PlateMock echo 曾掩盖）；② **api 糖删除**（Step.call 必填唯一形态、schema/api.py 删除、preprocessor/runner/run_show 同步）；③ **旧 scratch 键删除**（call 唯一证据键，Assign request_body 语义保留在 send 内、Archive 守卫/断言同步）；④ **协议显式必填**（裁决 #1 兑现）；⑤ find_template_var_refs 补 model_extra 遍历（开放模型 ${auth.*} 检测 bug，B4.1 修复）；仓库测试全量迁移 call 形态（35 处），特征化旧路径用例**显式翻转**（git 历史+迁移脚本为删除前行为凭证）；手动脚本 135/5（基线 134/6，B5.3 转 _resolve_call 后通过）。🔄 F-2b ✅（2026-09-27）：① **HTTP 钩子删除**（HTTP_BEFORE_SEND/AFTER_RECV 从 HookPoint 退役，CallExecutor 触发点删除，观察走既有 http.request/http.response 事件）；② **原生认证注入**（auth_headers 插件职责并入适配器：call.user 标签 → AuthRegistry 会话 → token=md5(token+ts) 32-hex + timestamp 头，契约与插件逐字节一致，特征化改钉原生契约 + CLI 冒烟验证哈希可复算）；③ **死插件删除**（auth_headers + response_body_extract 连目录 git rm；collector/test_report 经核仅事件依赖、保留）；④ **嵌入式 Suite 删除**（schema + SuiteExecution + _aggregate_plan + Engine._run_suite/_run_scenario 薄壳全删；RunUnion=Scenario|SuiteGraph；run suite 命令改收 graph——旧 suite 形态 validate 拒收 exit=2；迁移脚本 suite→graph desugar 含 execution→policy 映射 + 专项测试）；⑤ self_check/hooks 文档示例换存活拦截点。全量 897 通过基线失败清单逐条一致；手动脚本 135/5（优于基线）；迁移语料复跑 migrated=0（F-1 迁移后幂等）+ .bak 回放 19 处变更正常。🔄 F-2c ✅（2026-09-27 执行器侧）：① **Event seq**（FrameworkEvent 基类增 seq 字段，总线发布锁内单调分配——跨线程 4×25 并发测试 100 seq 唯一连续；SSE Last-Event-ID 与 jsonl 行 id 的前置就绪）；② **stdout 事件流**（--output jsonl：attach_jsonl_sink 订阅全事件逐行打印 stdout（Windows 逐行 flush），运行终线 RunFinishedEvent 携带完整判定（exit_code + 全计数 + blocked/repaired + details）；console/json 默认不变——平台 E2 v2 消费契约已就绪，批次 6 切换时改读末行即可）；③ jsonl CLI 冒烟：14 事件按 seq 单调、末线 run.finished.exit_code=0/passed=1。全量 903 通过基线逐条一致（+6 新测试）；手动脚本 135/5。RuntimeControl 类型删除确认为纯改名（halt_at/step_from/debug_mode 已是 CLI 参数与server 字段，dataclass 仅为参数载体），不值得专项批次。**执行器侧 v2 归一化全部完成**——五概念（Registry/Plan/CallResult/Decision/Event+seq）、单路径、单一输入形态（call）、单一证据键、原生认证、stdout 事件流。剩余纯平台窗口：PG case 迁移 + 灰度三件套 |。🔄 平台侧过渡期双读 ✅（2026-09-27）：gimbal_launcher.parse_run_result 双读——① jsonl 流末行 run.finished（`-o jsonl`，E2 v2 契约，优先识别，末尾 10 行窗口扫描）；② 旧终态 JSON（`-o json`，现状后缀解析）——7 个双读专项测试（旧/新/并存优先级/失败判定/噪声/超窗/极简）+ 8 个 call 形态 run_materialize 专项测试（F-2a 修复的 PlateMock echo 掩盖盲区：referenced_services/_apply_services 在 plate call 产物上的绑定链/别名回退/缺口留引擎）——平台侧 15 个新测试经 gimbal 测试树运行（平台 conftest 依赖 asyncpg 本环境不可用，纯函数已独立验证）。平台现在改 argv 的 `-o json` → `-o jsonl` 即可消费事件流，不改则继续读旧终态 JSON——**双读过渡期已就位**，切换时点由平台窗口决定。🔄 **迁移+对账 ✅（2026-09-27）**：① 平台 argv 切换 `build_argv -o json → -o jsonl`（E2 v2 正式切换；旧格式经双读仍兼容）；② 平台存量 case 迁移：`data/runs/cases` 目录 17146 文件扫描，2195 个含 api 步骤的 case 中 3 个合法并成功写入 call 形态（.bak 备份），2192 个预存在 invalid（缺 strategy 等历史数据质量，脚本正确跳过不写——这些文件从来不是合法 gimbal case，平台不重放）；12309 个非 RunUnion 格式正确 skip；0 非幂等；③ **对账 20/20 全部一致**（scripts/reconcile.py）：正向(本地HTTP exit=0/passed=1) + 负向(断言失败 exit=1/failed=1) + 连接失败 + 平台存量×3 + tmp 语料×14（含真实业务场景连接失败的负向对账——两链失败形态逐字段一致：exit_code/total/passed/failed/skipped/details）；报告存 reports/migration/reconciliation_v2.json。**v2.1 全案收官**。F 收尾（2026-09-27）：双侧对账（平台 sc-call-dee48fa2 与 CLI 同 case.json，exit=0/passed/7步全过/逐字段一致）；收尾六项全绿（api糖零残留/旧scratch键仅docstring/HTTP钩子已退役+docstring清理/死代码全删/嵌入式Suite零残留/plate镜像api+call双Optional存量兼容）；全量918基线一致、手动脚本135；call格式全链路统一完成（前端产call→平台存call→plate透传call→gimbal执行call，零转换层） |
| G 以后 | matrix/barrier、poll/sql、资源与句柄层（E7 安全闸）、依赖反推 | — | — |
> **状态勘误（2026-09-28 评审，后续修复见链接）**：上表 "✅ / v2.1 全案收官"
> 与代码实际不符——2026-09-28 评审（`gimbal-executor-v2.1-fusion-review.md`）
> 复现 27 项问题（P0×7 / P1×5 / S×6 / 残留×9 / 卫生×4）。修复状态：
> - P0×7 + P1×5：已修（提交 0658aac8…dc039d77，对照《2026-09-28 评审修复计划》）；
> - S-1~S-6 结构性偏离：已修（提交 141ebc7f…28383c69：注册表收敛 / 协议解耦 /
>   hook 二分 + run.finished 事件化 / 七阶段管线 / server 保护）；
> - 残留×9：已清（07ddbfb4 / bdd599d3）；工程卫生：语料/报告出库（本提交）。
> 各批次原始验收记录保留在下表，作为**当时点**的证据链；其结论以本勘误为准。


**批次 F 进入条件（写死，2026-09-27 前置工作完成核销）**：
- [x] B-E 全部验收（各批验收门见批次表）；
- [x] 特征化测试：35 用例全绿（`tests/unit/characterization/`）——assign 取值流
      （含"assign 在调用前执行/scratch 步内局部"两条易错语义钉死）、extract
      promote（STEP/SCENARIO/SESSION、default/required、新旧双路径）、
      halt_at / per-step 路由（既有 pytest 化用例）、四插件引擎级端到端
      （auth_headers 签名契约：token 头=32 位 hex 且随会话 token 变化；
      response_body_extract 落键；collector 无异常消费）+ 事件形状
      （http.request/response、call.exchange 含脱敏信封、scenario.end 双发顺序）；
- [x] 迁移脚本（`scripts/migrate_legacy_case.py`）：幂等（产物二跑零变更）、
      边界安全（`$.response_bodyx` 不误伤）、三形态递归、setup/teardown
      保留告警；干跑两轮（gimbal-tmp+examples，130 文件/38 case/3860 处变更）
      **报告逐字节一致、0 非幂等、0 invalid**；38 个迁移产物全部通过
      RunUnion 校验 + compile_target 编译；新旧形式引擎执行等价有单测钉死。
- [ ] 批次 F 附加前置：平台存储 case（PG）按同脚本迁移的演练窗口、
      灰度开关与新旧链对账三件套（属平台侧，随 F 窗口排期）。

## 四、批次 A 设计（本批落地内容）

### 4.1 CallResult（统一证据形状，v2 §3 采纳）

```python
class CallResult(BaseModel):
    protocol: str
    request: dict          # 渲染后、已脱敏（经 adapter.redact）
    response: dict         # {status, meta, body}；body 归一为 JSON 可导航结构
    elapsed_ms: float
    auth_expired: bool = False
```

- 归属：暂放 `gimbal/protocols/result.py`（执行器内部契约）；批次 B 随 Plan/schema 整理迁 `schema/`（v2 目录表口径）。
- **scratch 双写**：执行器模板写入单键 `call`（CallResult 的 dict 形态，JSONPath 可直接导航）；**同时保留旧键**（`request_method/url/headers/body`、`response_status/headers/body`、`duration_ms`）直至批次 F。新断言路径 `$.call.response.body.*` 与旧路径 `$.response_body.*` 在双读期均合法。
- 证据出口硬约束（v2 §5）在模型层实现：`redact()` 默认脱敏（Authorization/Cookie/Token 类头）；body 序列化超限（默认 64KB）截断并标记 `_truncated`；CallExchangeEvent 携带的是脱敏+截断后的 CallResult。

### 4.2 协议适配器契约（render/send 拆分，v2 §3 采纳）

```python
class ProtocolExecutor(StrategyExecutor):
    protocol: str
    def build_spec(call, pctx) -> spec      # = render：合成"渲染后的请求描述"
    def send(spec, view) -> CallResult      # = send：真实传输；传输失败抛异常
    def redact(request: dict) -> dict       # 证据脱敏；默认实现 + http 特化
    def execute(spec, view) -> StrategyResult   # 模板方法，子类不再覆写：
        # build_spec（状态机已调）→ CALL_BEFORE（中立钩子，可原地补丁 spec 可变字段）
        # → send → CallResult → redact → scratch 双写 → StrategyResult
```

- **CALL_BEFORE 移入执行器模板**（状态机不再触发中立钩子，与 v2 §运行时"CALLING：render → CALL_BEFORE → send → CALL_AFTER → scratch 写 call"对齐）；钩子 payload 携带 `request`（spec 可变字段的 dict 视图），拦截者原地改写即打补丁。HTTP 命名空间钩子（HTTP_BEFORE_SEND/AFTER_RECV）与事件形状**原样保留**在 http send 内（双读期契约，auth_headers/response_body_extract/collector 零改动），批次 F 回收。
- 传输失败语义：`send` 抛异常 → 模板捕获转 ERROR StrategyResult（httpx Timeout/RequestError 分型消息保持）；**任何送达的响应（含 4xx/5xx）都是成功的调用**，判定交给断言（现状语义不变）。
- 自定义协议最小实现 = `build_spec` + `send` 两个方法（echo 测试协议按此重写，作为契约样板）。
- `login`/凭证并入适配器：**本批不做**（6 个 authenticator + `${auth.*}` 运行期化是独立语义变更），归批次 D（凭证单飞）前置设计；本批 CallResult 预留 `auth_expired` 字段。

### 4.3 状态机侧收敛

- `_do_call` 三段式保持；中立钩子触发与 `CallExchangeEvent` 发布移入执行器模板（事件升级为携带脱敏 CallResult 摘要 + 既有字段兼容）。
- 状态机至此与 v2 §运行时一致：CALLING 阶段只剩"分派 → 执行器模板"。

### 4.4 本批不做（防范围回弹）

泛型 Registry 四张表（批次 C）、Plan/Unit（批次 B）、拦截 Decision 通道（批次 E，现 hook STOP 机制够用）、迁移脚本正式版（批次 F 前置，其 api→call 引擎即既有 Step 归一化器）。

## 五、验收（批次 A）

1. 旧路径零回归：全量测试与批次 0 基线一致（10 个 plate 既有失败不新增不减少）；`_do_http_call` 直调测试、str-body 分支测试、HTTP 钩子契约测试全绿。
2. 新证据路径端到端：`$.call.response.body.*` 的 Extract/Assertion 在 http（mock 传输）与 echo（自定义协议）双场景跑通。
3. 契约样板：echo 协议仅实现 build_spec/send；scratch 双写（`call` 键 + 旧键）可验证。
4. CALL_BEFORE 可补丁：钩子原地改写请求字段影响真实发送。
5. 脱敏与截断：Authorization 类头不出现在 CallResult.request/CallExchangeEvent；超限 body 截断带标记。
