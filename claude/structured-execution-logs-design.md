# 平台执行结构化日志 — 整体设计方案

> **基线** `1f4cf9f2`（feat/plate-s1，后端已 PG-only）。
> **范围**：执行链（server 链为默认，launch 链兼容，调试链随池受益）的
> **引擎日志**从产生、传输、入库到读侧（查询/SSE/前端/场景消费）的全链路
> 结构化。**关联**：`docs/known-issues/TRANSITIONAL-REGISTRY.md` B3（行级
> 失败原因不入库——本设计补日志面，B3 的 `run_error` 列是事件/台账面，
> 互补不互替）。
>
> **修订史**（2026-10-14 同日五轮，均已落正文）：
>
> | 轮次 | 要点 |
> |---|---|
> | 起草 | 管道（AD/批 1-3）+ 场景（S1-S12/批 4-5）两集合一 |
> | 评审一（12 项） | S1 锚点改失败事件；深链补 unit；S5 折叠键改调用点（实测 0 命中）；展开统一右抽屉；S2 参数改名；S6 竞态前置锁定；S4 导出快照；权限总则；S11 出口防护；时钟前提；S12 堆栈小项 |
> | AD8（用户追加） | 乱码治理四层（实证 99 行 = 70 JSON 零 ANSI + 23 ANSI + 6 纯文本） |
> | 评审二 | tail 游标改**入库 id**（(ts,id) 做 tail 会稳态漏行）；泵背压/池生命周期核验闭环；NO_COLOR 与 loguru 版本无关实证；uvicorn 桥接行预期；access log 直压 WARNING；收口语义立规；连接数预算 |
> | 评审三 | `_flush` single-flight 漏点（ticker 直调绕过互斥）批 1 全路径加锁；收口四步立规（done 帧非独立步骤）；S9 统计槽定 Execution JSON 列、排除负数轴；S6 两行式摘要 + `expression=` 验收；批 3 依赖批 2；视口锚定 |
> | 评审四 | S9 验收对齐五计数；`jsonb_set` 键级原子更新与 flush 同事务（防 `counterDrift` 等写入者互相覆盖）；S6 尾行对齐 D6；测试清单补 single-flight 并发 |
> | 评审五 | S9 定稿：**累计快照**而非增量、SQL `+N` 禁用；终值唯一写入点 = finalize 最后一次 flush（§7 第②步只写状态）；泵侧丢弃计数「脏即写」+ finalize 无条件写 |

---

## 1. 背景与问题

引擎日志天生结构化：每行是一个 JSON 字典（loguru JsonSink），携带
`timestamp/level/logger/category/function/line/message` + 执行上下文标签
（`run/unit/attempt/scenario/module/step/service/protocol/endpoint`，来自
`gimbal/log/exec_context.py` 的 contextualize）。**但平台只用它的一半**：

| 面 | 现状 | 问题 |
|---|---|---|
| 产生 | `src/gimbal/log/formatters.py` JsonSink；stderr 非 tty **自动 JSON**（`integration.py:81`），`GIMBAL_LOG_JSON`/`GIMBAL_LOG_LEVEL` 可覆盖 | 无（契约稳定）；但**乱码**混入文件面（AD8） |
| 传输 | server 链 `ServerSession._drain_stderr` 逐行原样写 `server-engine.log` 文件，**无解析无回调** | 日志不进平台管道 |
| 入库 | `_EventIngester.on_log → insert_logs`（`run_dispatcher.py:369`、`execution_store.py:326`）：结构化列 + 完整 payload | **只有 launch 链接线**（`run_dispatcher.py:1260`）；server 链（默认）零日志入库 |
| 查询 | `/api/executions/{id}/events?kind=log&level_min=…`（P2-07）组合筛选 + category 聚合 | 现成可用 |
| SSE | `/events/stream` 只推事件 | ① 帧分隔符是**字面量 `\n` 两字符**（`executions.py` `_nl=chr(92)+"n"`），前端按真 `\n\n` 切帧永远失败——SSE 帧路径静默失效，页面更新全靠 3s 兜底轮询；② 日志 seq 走**负数轴**，`after_seq` 恒正 → 日志即使入库也永远不被 SSE 推送 |
| 前端 | 日志分析页 `ExecutionEvents.vue`（徽标/着色/筛选）+ 行内「引擎日志」按钮（原始文件） | 日志分析页对 server 链执行**查不到任何日志行**；且 `query_events` 统一 `ORDER BY seq`，负数轴跨批递减 → **日志行顺序跨批是倒的**（现存 latent 缺陷）；类别下拉硬编码已落后引擎词表 |

典型代价（#304 实例）：提取规则 `$.call.response.body.data.data[0].order_id`
在空列表上硬失败，细节（哪条规则、什么路径）只躺在 `server-engine.log`
文件里；事件流与 result.json 只有 `final_state=failed`。行级根因要两击、
且无法按 step/level 过滤；失败通知不含根因；跨执行对比靠手工 API 对拍。

## 2. 目标 / 非目标

**目标**
1. server 链（含调试实例）引擎日志**结构化入库**，与事件同一查询面（kind=log）；
2. 日志可 **SSE 实时流式**获取（结构化帧），断线可续；
3. 前端**实时结构化日志面板**（级别/类别/step 筛选），原始文件按钮保留作审计兜底；
4. 修复既有缺陷（帧分隔符、日志排序、SSE 隐式混流、乱码、类别下拉漂移），
   不是绕过；
5. 量级可控、归属可靠（按标签不按槽位文件）、launch 链零回归；
6. 场景消费闭环：失败根因两击直达、通知带摘要、深链分享、调试台联动。

**非目标（防蔓延）**
- 不改引擎日志字段契约（JsonSink 是唯一真源，平台只投影；AD8/堆栈两处
  一行级引擎小项除外）；
- 不做事件面增强（extract/assert 失败发契约事件 `extract.failed` 等）——
  另立事项，与 B3 的 `run_error` 互补；不动 B3；
- 不做执行/事件保留期策略（执行本身无清扫，事件 CASCADE 随执行；全局
  保留期独立立项，D5）；
- **外部管道消费**（ELK/Loki/webhook 转发）：`/events` API 与 SSE 已可
  自取，平台不内置转发；
- **跨执行全局日志检索**：查询域锁单执行（§9 红线）；
- **实时告警规则**（「出现 ERROR 即通知」类）：与执行终态通知（S6）语义
  不同，属通知域立项；
- **内建日志 diff 视图**（D8）与**泵侧通用正则脱敏**（S11-B）：挂起。

## 3. 总体架构决策（AD）

**AD1 结构契约：引擎 JsonSink 为唯一真源，平台只投影。**
入库列 = 契约字段的固定投影（level/category/module/service/protocol/unit/
attempt/step + message + payload 全字典），映射已存在于 `insert_logs`。
category 枚举以 `gimbal/log/category.py` 前缀表为准（call/auth/strategy/
compiler/scheduler/plugin/debug/step/resolve/context/core）。平台侧**不**新增
结构定义、不做二次加工；未知字段随 payload 透传，契约演进零迁移。

**AD2 传输：server 链 stderr 泵拦截解析，文件照写。**
`_drain_stderr`（`gimbal_server_session.py:74`）逐行 `json.loads`：成功 → 调
`on_log(d)`；失败（非 JSON 行，如三方库裸输出）→ 原样计数、只落文件不入库。
回调异常捕获记日志、不阻断泵（与 `on_event` 同惯例）。`ServerSession.start`
/`ServerSessionPool.start` 增加 `on_log` 透传参数；`run_dispatcher` 在池启动处
传 `ingester.on_log`（与 `ingester.on_event` 对称，一处接线）。

**泵背压（已核验）**：`on_log` 只入队——达阈值经 `asyncio.create_task`
异步 flush（`_maybe_flush`，泵协程不阻塞），DB 慢不传导到 stderr 管道，
引擎不会因平台入库变慢而卡写。`_flush` 失败**回填缓冲重试**
（`run_dispatcher.py:400` P3.5-3，含 CancelledError 语义），不丢批；但回填
无上限——补 **logs 缓冲上限**（建议 50k 条，超限丢最旧并计数入 S9
dropped；**events 缓冲不设上限**，事件是台账不可丢）。

**single-flight 漏点（批 1 必修）**：阈值路径已有在飞互斥（`_pending`
集合 + `any(not t.done() for …)` 即「在飞未收口，余量并入下一轮」），但
`_tick` 每 0.5s **直调 `_flush` 绕过互斥**（ticker 冲刷不进 `_pending`，
阈值路径也看不见它）——两个 `_flush` 并发时各自换出缓冲开独立事务，PG
序列按 INSERT 时刻分 id、按提交时刻可见：先分 id 后提交的批次会落在已
推进的 id cursor 之下（AD5 tail 漏行的 id 版）。**修法：`_flush` 全路径
single-flight 化**（ingester 级 `asyncio.Lock`，覆盖阈值 task / ticker /
finalize 收尾与回填重试四条路径）。

**池生命周期前提（已核实）**：server 池**按执行创建**（总案决策 15：
`ServerSession` docstring「一次执行一个执行器 server 实例」；
`run_dispatcher.py:1454` 在 per-execution 分派函数内 `ServerSessionPool(size=…)`
创建，`_teardown` 收口 close）。`EXEC_MAX_SERVER_INSTANCES=8` 是**单执行**
槽位钳制不是全局池；调试实例同款生命周期。因此「池启动处绑定本执行
ingester 的回调」不存在跨执行路由错配——S8「免费获得」成立。

**归属按 exec_context 标签（unit/step），不按槽位文件**——多 worker 并行时
日志天然按行归属到 case/step，顺带根治 S1.5 登记的「case 无槽位映射时日志
回落错文件」问题在入库面上的表现（文件面回落仅剩审计兜底角色）。
launch 链接线（`launcher on_log`）不动；调试实例走同一池，自动获得。

**AD3 入库门槛：平台侧级别过滤，文件保持全量。**
`settings.EXEC_INGEST_LOG_LEVEL`（默认 `"INFO"`，见 D1）：低于门槛的行在
泵处丢弃（不入库不缓冲），`server-engine.log` 文件不受影响（审计与排障
仍可看 DEBUG）。不设 category 白名单——level 是写侧量级闸，category 是
读侧筛选面，写侧砍维度会破坏查询可预期性。`_EventIngester` 既有双阈值
（200 条 / 0.5s）不变；缓冲机制的增强（single-flight 锁 / logs 上限 /
S9 计数）见 AD2 与 S9。DEBUG 级临时开闸（按执行覆盖）不做进一期（D4）。

**AD4 存储轴：负数 seq 降级为唯一性令牌，读侧按时间轴。**
现状负数轴跨批递减（`log_seq_base = _log_seq - len(logs)`），`ORDER BY seq`
对 kind=log 跨批倒序——不修语义、修用法：
- **写侧不动**：负数轴只承担 `(execution_id, seq)` 唯一约束 + 恢复重跑续接
  （`seed_from_db` 取 min(seq)），不承载排序语义；批 1 在模型注释写明
  「**seq 对 log 行无序语义**」（内部实现，不对外暴露，防后来者再按 seq
  排序）；
- **读侧**：`query_events` 排序改为——`kind=event`（单查）保持 `seq`（事件
  语义序 + SSE 续传依赖）；`kind=log`（单查）改 `(ts, id)`；混合查询（kind
  未指定）改 `(ts, id)`（统一时间轴，id 为同 ts tiebreak，ts 微秒精度）；
- **时钟前提（显式）**：(ts,id) 统一时间轴假设平台侧事件 ts 与引擎侧日志
  ts **同钟可比**——当前同机部署成立（引擎 UTC ISO / 后端入库 UTC）；
  执行器一旦远程化或引入多执行模式，此前提必须重新验证（单调排序键或
  时钟校准），届时混合时间轴（S3）与 around 查询（S2）语义一并复审；
- **否决的替代**：①日志并入事件单调轴（会动 M6 upsert 冲突面与恢复重跑
  seq 续接语义，风险大收益小）；②独立 `log_seq` 列 + 部分唯一索引（双轴
  复杂度，且 on_conflict 目标要跟部分索引谓词绑定，脆）。

**AD5 读侧：事件流与日志流分离，各自 cursor；排序轴与 tail 游标分离。**
- **两条轴，分工明确**：**排序轴 = (ts,id)**（静态查询：分析页、S2 around、
  S4 导出、AD4 读侧排序；id 为同 ts tiebreak，ts 微秒精度）；**tail 游标 =
  入库序 `id`**。不复用 (ts,id) 做 tail 游标的原因：ts 是引擎打点时间、
  入库先后由 flush 时机决定，两者顺序不一致——先 ts 后入库的行会落在已
  推进的 ts cursor 之下，**稳态漏行**（不断线也发生，多 worker 并行时最
  典型）。tail 按 `id > cursor` 取行、前端按 (ts,id) 插入排序展示；
- **id 单调是机制而非假设**：前提 = 执行内至多一个在途 flush。现状阈值
  路径已有互斥但 ticker 直调绕过（见 AD2 single-flight 漏点），批 1 以
  ingester 级 `asyncio.Lock` 全路径收口后，「执行内 id 按提交序单调」成为
  机制保证——这是本条 tail 语义的地基；
- `/events/stream`（既有）：**显式 `kind=event`**（消除「无 kind 过滤但
  after_seq 恰好滤掉日志」的隐式行为），cursor=seq，语义不变；
- `/logs/stream`（新增）：`kind=log`，tail cursor=入库 `id`，live tail +
  **backfill 仅首次打开回看**（D2）；`Last-Event-ID` 因此是**精确续传**
  （断线窗口靠 id 单调性不丢不重）；心跳、终态 done、断线重连语义与
  事件流对齐。SSE `id:` 字段直接用 `<row_id>`，无需复合编码；
- `/logs/stream` 复用 `query_events` 的**服务端筛选参数**（level_min/
  category/module/service/unit/step/search）——live tail 只收过滤后的行，
  省带宽省渲染；客户端可再叠加本地即时过滤（输入即滤，不回服务端）。
  事件流不带筛选参数（事件量小，保持语义最简）；
- 两流共用同一 DB 轮询骨架（1s 节拍、批读、is_disconnected 收口）；
- **必测**：构造「先 ts 后入库」样本（跨 flush 批、乱序 ts），断言流中
  不缺行（稳态漏行回归闸）。

**AD6 帧格式：SSE 线协议规范化（修缺陷）。**
三处 `chr(92)+"n"` 全部改真换行 `"\n"`（`_event_sse_line`、done 帧、ping）。
帧 = `id: <cursor>\nevent: ev|log|done\ndata: <json>\n\n`。后端测试**必须
按帧结构断言**（真实换行切帧后解析 id/event/data 字段），禁止子串匹配——
这是本缺陷逃过 CI 的直接原因。

**AD7 前端：统一 fetch-SSE 解析器 + 行内实时日志面板。**
- `stores/executions.ts` 的 `_parseFrame`/切帧逻辑抽成共享 util（真 `\n\n`
  切帧 + 字段解析），事件流与日志流共用；事件流现状「靠 3s 兜底扛」随帧
  修复自然回归 SSE 主通道（兜底保留，语义不变）；
- 执行详情页行内**实时日志面板**（抽屉/展开区）：结构化行（级别徽标/类别/
  step 标签/message），级别与类别筛选、自动滚动、滚动即暂停、终态自动收口；
  行渲染复用日志分析页样式；
- 日志分析页：修排序表现（AD4 生效）、日志行可展开看 payload 其余字段
  （展开走 S7 统一右侧 Sheet 抽屉）；
- 「引擎日志」按钮（case-artifact 原始文件）保留，文案注明「原始文件（含
  未入库级别）」，查看器 ANSI 感知（AD8）。

**AD8 日志洁净度（乱码治理）。**
实证（#304 的 server-engine.log，99 行）：70 行 JSON（**零 ANSI，入库面
干净**）+ 23 行带 ANSI 色码 + 6 行纯文本。乱码只污染**文件与展示面**
（case-artifact 按钮直接看文件），不进 DB。三个来源：
① 启动早期 loguru（bootstrap 前的 ColorFormatter 默认带色）；② uvicorn
自带日志（`uvicorn.run` 未传 `log_config`，默认带色）；③ reporter 控制台
汇总行（✓/✗/STEP FAILED/FAIL total）。

**批 1 落地后复核口径（#306，283 行）**：入库面零 ANSI（211 行入库全
干净）；文件面残留 ANSI 50 行 = reporter 45（步骤标题/描述/汇总，层 3
引擎小项覆盖）+ uvicorn 4（层 2）+ **pre-setup loguru 1**（`start_server`
行在 `configure_logging_from_cli` 之前打出，走 loguru 内建默认彩色 sink
——层 1 已如设计杀掉早期配置阶段及之后的 loguru 彩色，唯此 1 行例外，
随引擎小项一并处理：CLI 入口前置早期日志初始化）。

治理四层（各自一行级，文件保持原始字节审计原则不动）：
1. **平台侧（零引擎改动，拿掉大头）**：`ServerSession.start` 的 spawn env
   加 `NO_COLOR=1`——两条日志初始化路径都由 gimbal 配置层**自行读取**该
   环境变量（早期 `configure_logging_from_cli`：`integration.py` 读
   `NO_COLOR in os.environ`；bootstrap：`LoggingConfig.from_bootstrap`
   同款），**不依赖 loguru 内建的 NO_COLOR 支持，与 loguru 版本无关**
   （仓库钉 `loguru>=0.7.0`，venv 0.7.3）。reporter 的 `ctx.config.no_color`
   取自 `BootstrapConfig.no_color`（loader 的 `_ENV_MAP` **不含** NO_COLOR，
   此链路不吃 env）——正因如此第 3 层 isatty 兜底对 reporter 是承重的；
2. **引擎侧（一行）**：`uvicorn.run(..., log_config=None)`——uvicorn 日志
   改经 root → InterceptHandler 桥进 loguru，输出为 JSON 行（顺带变得
   **可入库**）。**预期**：桥接行无 exec_context（run/unit/step 空），
   category 落 `core`，按 unit/step 过滤时自然被排除——这是特性不是缺陷。
   **access log 直接压 WARNING**（平台/调试台对引擎 server 的每次请求都会
   产生一行 INFO，状态轮询场景量会远超业务日志；默认压住，需要时放开）；
3. **引擎侧（一行，reporter 承重兜底）**：reporter console 的 `_no_color`
   判定补 `or not sys.stderr.isatty()`——第 1 层对 reporter 链路失效时的
   保证（见上）；
4. **前端（治愈存量）**：工件查看器（engine.log 展示）ANSI 感知——默认
   剥除 ESC 序列显示纯文本，附「显示原始」开关；对历史文件立即生效。

引擎侧两处一行改动与 S12 堆栈同类：**独立小项**，不破「批 1-3 管道接线
引擎零改动」承诺（该承诺只覆盖接线）。

## 4. 场景全景与权限总则（角色 × 生命周期）

|  | 执行中 | 刚结束（排障窗口） | 长期 |
|---|---|---|---|
| **测试执行者**（发起人） | 实时 tail（批 3 面板）；失败即停时看最后窗口 | **S1 失败根因直达**；S2 上下文窗口；S3 混合时间轴 | S10 跨执行对比（为何这次过那次不过） |
| **场景/用例作者** | 调试台实时日志（S8，随批 1 免费获得） | S1/S3 + 按步骤分段核查取值链路 | S4 深链分享（把过滤态发给同事） |
| **平台管理员** | S9 入库链路自监控 | S6 失败通知带根因摘要 | 审计兜底走原始文件（AD2 已定） |
| **引擎/策略开发者** | S8 调试 | 新扩展日志自动归类（§11） | S12 堆栈精简帧（引擎侧小项） |
| **外部系统（CI/脚本）** | `/logs/stream` SSE tail | `/events` API 拉取 | 非目标（§2） |

**权限总则（贯穿所有场景）**：日志查询/SSE/导出端点全部走**执行可见性鉴权**
（与 `/events` 同款 OwnedExecution：属主/admin/公共/引用分享）；深链与导出
文件**不豁免鉴权**——同事打开无权执行的深链得到 404，分享链接只在可见性
范围内有效。

## 5. 场景方案（S1-S12）

### S1 失败根因直达（锚点导航）——P0

**场景**：执行详情看到 step-002 失败，想知道为什么。现状要：开日志分析页
→ 手填 step 过滤 → 肉眼找。#304 排障即此路径（人工做了三步）。

**方案（锚点 = 失败事件，非首条 WARNING）**：重试/轮询/降级都打 WARNING，
首条 WARNING 常是过程噪声（#304 实证：根因细节行
`ExtractExecutor 执行提取: expression=…` 是 **INFO** 级，WARNING 只说
"Phase aborting"）。因此锚定**失败事件本身**——行/失败步骤的 `step.failed`
事件（混合时间轴上的 (ts,id) 点），根因几乎总在失败点之前。S1/S2/S3 由此
收敛为**一个动作**：深链进混合时间轴视图，`around=<失败事件 ts>|<id>`、
`n_before` 覆盖该步骤窗口。

**维度（必须带 unit）**：数据集多行 × parallel 时各行共用 step 编号，深链
必须同时带 `unit=<失败行 unit_id>`（行记录自带，与执行器 unit 标签 1:1——
P2-01/P2-04 投影不变量，`ExecutionRow.unit_id` 即取自事件标签）。与 S6
同口径。

**成本**：纯前端（详情页动作 + S4 + S2 的 around）。**归属批 4。**
**验收**：多行执行中指定失败行 → 两击内见到以失败事件为中心、含根因行的
混合时间轴窗口；深链只含该 unit 的行。

### S2 失败上下文窗口 ——P0

**场景**：WARNING 行本身常不够（要配合前面的 INFO 提取行读），要看失败点
前后各 N 行。

**方案（参数名避开 cursor 语义）**：`/events` 增加
`around=<ts>|<id>&n_before=50&n_after=50`——锚点行数语义，既有 `after_seq`
cursor 参数保持原义不动。实现复用 (ts,id) 轴比较（与 AD4 同源）；锚点
默认 = 失败事件的 (ts,id)（S1 传入），分页继续按 (ts,id) cursor 双向翻。

**成本**：后端一个查询分支 + 前端动作。**归属批 4。**
**验收**：around 前后行数正确、同 ts (ts,id) tiebreak 稳定、与 cursor 翻页
无缝衔接。

### S3 混合时间轴（事件+日志同屏）——P0

**场景**：「这个 call.exchange 前后引擎在干什么」——事件与日志 interleaved
才是真实执行现场。AD4 已让混合查询按 (ts,id) 统一排序，API 已支持
（kind 不传即混合），缺的是 UI 视图。

**方案**：分析页加视图切换「日志 / 事件 / 混合时间轴」。混合视图行渲染：
事件行用现有事件样式、日志行用日志样式，时间轴一列贯通。S1 的深链落点
即此视图。时钟前提见 AD4。

**成本**：纯前端。**归属批 4。**
**验收**：混合视图按时间轴单调；同 ts (ts,id) 稳定；失败事件锚点窗口正确。

### S4 过滤态深链与导出 ——P0

**场景**：排障结论要分享/留档：把「step=step-002 & warning+」这个视图发给
同事，或导出文本贴工单。现状过滤态不可复制（不进 URL）、不可导出。

**方案（导出 = 快照语义）**：① 过滤态双向同步进 URL query（进入时读、
变更时 replace）；② 「复制链接」即分享（权限见 §4 总则）；③ 「导出」——
导出开始即**冻结上界 cursor**（快照点），只导出至该点为止，文件头写明
快照位置与过滤条件；翻页用 after-cursor 拼齐。注意 `/events` 的 `count`
是**返回行数不是总数**（已核实），不得用作对账基准。设行数上限（建议
50k）超限提示收窄过滤。文本（人类可读投影）+ JSON 双格式，前端生成不走
后端。

**成本**：纯前端 + 导出翻页循环。**归属批 4。**
**验收**：带过滤态 URL 冷开恢复视图；导出行数与**冻结快照点**的实际行数
一致（执行仍在跑也不漂移）；超限提示生效。

### S5 日志降噪（连续重复折叠）——P1

**场景**：轮询/重试/长循环打同类行，几百行淹没关键信息。

**方案（折叠键 = 调用点，实测依据）**：#304 真实日志实测（70 条 JSON 行）：
`(step, message)` 精确匹配**可折行 0**——消息带插值变量（耗时/id/计数），
精确匹配几乎不命中，原方案作废。改用**调用点键** `(step, function, line,
level)`：JsonSink 已序列化 `function/line`，同调用点的连续行即循环体，
无需数字归一化。声明为**近似折叠**（同调用点不同变量值合并展示，展开
可见明细首行 + 计数）；仅折叠视图呈现，不改数据、不影响导出（导出保留
全量）。短跑（无循环）零收益属预期，价值在循环密集场景。

**成本**：纯前端。**归属批 5。**
**验收**：连续同键折叠、非连续不误折、导出不受影响；用循环密集的执行
做活体验证。

### S6 失败通知带根因摘要 ——P1

**场景**：失败通知现在只有「sc-id · N 通过 / M 失败」，要点进来才知道
为什么。根因数据已在库里。

**方案（两行式摘要）**：
- **锚点**：摘要取**失败事件之前最近的 WARNING/ERROR 日志行 + 其前面同
  unit、同 step 的一行**（共两行分 200 字符）——S1 的实证已证明根因细节
  常是 INFO（#304：WARNING 只有泛化的 "Phase aborting"，`expression=` 在
  其前一行的 INFO 里），单取 WARNING 会把泛化句当根因；找不到
  WARNING/ERROR 时回退取失败事件前最后两条日志行，再没有则静默降级为
  现状文案。事件面 `extract.failed` 立项后改为优先取事件 payload（挂账）；
- **竞态前置（锁定既有不变量）**：已核实现行代码顺序为 gather 收口 →
  `ingester.finalize()`（注释明写「先于终态落库」）→ `_finalize_execution`
  → `_notify_finished`——顺序本就正确，本条把它升格为显式前置不变量并加
  防回归用例：「执行最后一步失败、失败行日志刚进缓冲即终态」场景下摘要
  必须取到（若 finalize 顺序被改则红）；
- **出口打码（S11 联动）**：通知是日志内容**唯一对外出口**，摘要入 body
  前做轻量打码（token/password/authorization 形态正则，见 S11）。

长度/条数：每失败 unit **一组两行**，共 200 字符，最多 3 组（与 D6 一致）。
挂钩点 `_notify_finished`（`run_dispatcher.py:2190`）。

**成本**：后端一处组装 + 通知模板。**归属批 5，且必须晚于 S11A 抽查测试
落地（同批内先后写死）。**
**验收**：#304 型失败通知 body 含 **`expression=`**（不只断言
`hard_failed`——泛化句过不了这条验收）；竞态防回归用例过（§7 四步收口）；
无日志执行通知不回归；打码生效（构造含 token 的 WARNING 行）。

### S7 长尾浏览（加载更多 + 虚拟滚动）——P1

**场景**：多行 × parallel 大执行日志数千行，单次拉默认上限截断。

**方案（固定行高 + 展开外移）**：S5 的 ×N 展开、S12 的 payload 展开都会
改行高，与虚拟列表「行高固定」前提冲突。裁定：**列表恒固定行高，三处
展开（日志行详情/折叠组成员/异常详情）统一走一个右侧 Sheet 抽屉**
（对齐仓库既有拍板：右侧面板用 Sheet side=right）。分析页「加载更多」
（(ts,id) cursor 翻页）；实时面板虚拟滚动。

**成本**：前端两处 + 共享抽屉组件。**归属批 5。**
**验收**：>2000 行执行可完整翻页；面板万行级不卡；展开走抽屉、列表行高
恒定；**插入排序视口锚定**（tail 按 id 收行、按 (ts,id) 插入，晚到行插入
视口上方时保持首个可见行不动、按其 key 补偿偏移——暂停滚动查看不跳动，
批 3 面板同款验收）。

### S8 调试台实时日志 ——P1（免费获得 + UI 胶水）

**场景**：交互式调试（C6 调试台）时，命令与引擎反应要同屏看。

**方案**：批 1 的泵接线覆盖调试实例（同一 server 池，池生命周期见 AD2），
日志自动入库/可流。UI 胶水：DebugConsole 侧挂日志 tail 面板（复用批 3
组件，按当前调试执行的 unit 过滤）。

**成本**：UI 胶水一处。**归属批 4（组件就绪后）。**
**验收**：调试会话中下 debug 命令，日志面板同步滚动。

### S9 入库链路自监控与完整性计数 ——P1

**场景**：泵解析/回调/落库都是 best-effort 静默吞——「日志是不是丢了」
无法回答。#304 实测口径：stderr 99 行中 70 行 JSON，非 JSON ~30%（早期
彩色 loguru / uvicorn / reporter 汇总行；AD8 落地后大多转 JSON 或纯文本）。

**方案（累计快照 + 脏即写）**：
- 计数器（`logs_ingested / logs_dropped_unparsable / logs_below_level /
  flush_errors / logs_dropped_overflow`）在 ingester 内存中累计，
  **随每次 flush 把五项的当前快照整体写入** `Execution.config_json` 的
  `ingest_stats` 键（沿用 `counterDrift` 写 config_json 的既有先例）——
  **jsonb_set 是设值不是累加**：single-flight 后每执行只有一个写入者，
  快照整体写入天然幂等；**明确禁止 SQL 侧 `+N` 形态**（将来任何不是
  整事务回滚的重试路径都会重复计数）。崩溃后最后一次成功 flush 的快照
  幸存；
- **泵内计数项的落库触发**：`below_level` 与 `dropped_unparsable` 在泵里
  计数、这些行**不进缓冲**——尾部只剩丢弃行时没有 flush 把计数带出去。
  因此 ticker 的冲刷条件从「缓冲非空」扩为「缓冲非空 **或 计数脏**」；
  `finalize()` **无条件写一次快照**（即使缓冲已空），对账在尾部不缺行；
- **终值唯一写入点 = finalize 的最后一次 flush**（§7 第①步内），第②步
  终态事务**只写状态不再写计数**（快照语义下再写只是重复并多一个写入
  点）；「通知前可见」由 ① 先于 ② 保证；
- **并发安全**：`config_json` 有多个写入者（`counterDrift` 等），快照写入
  **禁止**「读整个 JSON → 改键 → 整体写回」的 ORM 形态（互相覆盖）；列型
  已核实为 **JSONB**（`JsonVar = JSON().with_variant(JSONB(), …)`），用
  `jsonb_set` 做**键级原子更新**，且放在 single-flight 锁内、**与该批
  flush 同一事务**——快照与已入库行严格一致，对账不存在「行入了计数
  没加」的窗口；
- **统计槽 = `config_json` 键，明确排除「负数轴保留槽位」**（理由：
  `seed_from_db` 取 min(seq) 续接会被保留槽干扰；槽位伪行混入
  `/events`/`counts`/导出处处要加例外；用伪行模拟统计表与 AD4「seq 只是
  唯一性令牌」自相矛盾）。「无表结构变更」因此成立；
- **flush_failed 双写**：除尝试写 `ingest.flush_failed` 事件外，**必打一条
  到平台后端自身日志文件**（DB 不可用时唯一幸存面，与「审计兜底走原始
  文件」口径一致）；
- 诚实边界：进程被 kill 时未 flush 的尾量计数不可考，对账公式
  `文件行数 ≈ logs_ingested + dropped + below_level` 允许崩失败量差。

**成本**：后端计数 + 双写。**归属批 5。**
**验收**：终态后 `Execution.config_json.ingest_stats` **含五项计数**（含
`logs_dropped_overflow`）且与文件对账吻合；**尾部仅丢弃行的执行（不进
缓冲的 below_level/dropped_unparsable）终值仍完整**；注入坏行/溢出计数
正确；人为 DB 断连时后端日志文件出现 flush_failed 记录。

### S10 跨执行对比（最小形态）——P2

**场景**：同场景 #304 挂 #300 过——diff 两次执行的日志找差异（本轮 #304
排障的实际动作，目前靠手工 API 对拍）。

**方案**：**一期最小形态**：依赖 S4——两次执行的过滤态深链并排开两个
浏览器窗（step 过滤使两次执行的行按步骤对齐可比）。**不做**内建 diff
视图（行对齐语义复杂：bl_no 随机、时间戳必然不同，有效 diff 维度只有
message/level/category 的按步骤对齐——收益/成本比差，等真实使用频率
说话）。

**成本**：一期零开发（S4 副产品）。**决策点 D8** 确认一期不做内建。

### S11 敏感信息防护 ——P2（决策点 D7）

**场景**：日志入库扩大了暴露面（DB 备份/更长留存/通知摘要外发）。已知
边界：`case.json` 因明文凭证刻意不暴露；日志 message 理论上可能带凭证。

**方案（A 为主 + 出口窄防护）**：
- **A（主）引擎侧红线**：凭证不入 message 作为引擎日志纪律（与 case.json
  同一纪律），配**全类别**抽查测试（对入库日志 message 扫
  `password|token|authorization` 模式，命中即红）——范围不限于 auth/call：
  协议层 dump 请求头经 stdlib 拦截可能落 `core`；
- **出口窄防护（S6 专用）**：通知摘要是日志内容唯一对外出口且仅 200
  字符，入 body 前做轻量正则打码——零成本、不构成通用脱敏模块；
- **B 泵侧通用正则脱敏**：挂起，仅当 A 的抽查长期失守再启用（误伤与
  性能代价不成比例）；
- **顺序约束**：S11A 抽查测试落地先于 S6 上线（同批内先后）。

**归属**：A + 出口防护随批 5；B 挂起。

### S12 异常行渲染 + 精简堆栈 ——P0（渲染）/ P2（堆栈）

**渲染（批 3）**：JsonSink 已把异常结构化为 `exception:{type,message}` 字段。
行内异常徽标（类型）+ message；展开走 S7 的统一右抽屉看 payload 全字段。

**精简堆栈（引擎侧小项，独立于批 1-3 的「引擎零改动」承诺——该承诺只
覆盖管道接线）**：JsonSink 的 exception 序列化增加可选精简帧
（`frames: [{file, line, function}] × N`，配置门控如 `GIMBAL_LOG_STACK_FRAMES`
或 DEBUG 级自动开，默认关防噪声/性能）。平台零改动（payload 自动携带，
属 §11 两级扩展故事的零改动层）。**归属：独立小项，随批 5 或引擎侧
任意批次捎带。**

## 6. 分层改动清单（代码锚点）

| 层 | 改动 | 锚点 |
|---|---|---|
| 引擎 | **零改动**（管道接线）；独立小项：uvicorn `log_config=None`、reporter isatty 兜底（AD8）、精简堆栈（S12/D10） | `core/server.py`、`reporter/builtin/console.py`、`log/formatters.py` |
| 传输 | `_drain_stderr` 解析 + `on_log` 回调；`ServerSession.start`/`ServerSessionPool.start` 加参透传；spawn env `NO_COLOR=1`（AD8） | `gimbal_server_session.py:44,74` |
| 入库 | 泵处级别门槛（`settings.EXEC_INGEST_LOG_LEVEL`）；`insert_logs` 不动；`_EventIngester` 阈值不变，**加 single-flight 锁 / logs 缓冲上限 / S9 计数（`jsonb_set` 同事务）**；flush_failed 双写 | `gimbal_server_session.py` + `app/core/config.py` + `run_dispatcher.py` |
| 查询 | `query_events` 排序分支（AD4）；`around`/`n_before`/`n_after`（S2）；`_notify_finished` 摘要（S6） | `execution_store.py:425`、`run_dispatcher.py:2190` |
| SSE | 事件流显式 kind=event；帧分隔符修真换行；新增 `/logs/stream`（**tail 游标=入库 id**、backfill、服务端筛选） | `app/routers/executions.py:328-414` |
| 前端 | 共享 SSE 解析 util；详情页实时日志面板；分析页排序/展开/类别下拉 counts 驱动；深链/导出（S4）；混合时间轴（S3）；降噪/虚拟滚动/右抽屉（S5/S7）；工件查看器 ANSI 感知（AD8）；通知摘要渲染（S6） | `stores/executions.ts`、`views/Executions.vue`、`views/ExecutionEvents.vue`、`views/DebugConsole.vue` |

无表结构变更、无迁移（`execution_events` 列与索引已覆盖：标签列可筛，
`(execution_id, seq)` 唯一；`ix` 于 execution_id 过滤后规模可控）。

## 7. SSE 线协议（规范）

```
事件帧:  id: <seq>\nevent: ev\ndata: {"id":..,"seq":..,"ts":..,"kind":"event",...}\n\n
日志帧:  id: <row_id>\nevent: log\ndata: {"id":..,"ts":..,"kind":"log","level":..,"category":..,"step":..,"message":..}\n\n
心跳:    : ping\n
收口:    event: done\ndata: {"status":"..","lastCursor":".."}\n\n
```
- 日志帧 `id:` = 入库序 row_id（tail 游标，见 AD5），展示顺序由前端按
  (ts,id) 插入排序；
- `Last-Event-ID` 回传原样 cursor：事件流=seq（精确），日志流=row_id
  （精确，id 单调性保证不丢不重）；backfill 仅服务**首次打开回看**
  （`?backfill=N`，默认 200，0 关闭，D2）；
- 日志流支持服务端筛选参数（AD5）；
- **收口语义（终态四步；done 帧非独立步骤）**：done 帧是 SSE 轮询看到
  「终态且无新行」后的**自然结果**，真正的不变量是写库时机，顺序固定为：
  **① `ingester.finalize()`**（全部事件/日志含引擎 `run.finished` 事件
  落库 + **S9 计数终值快照**随最后一次 flush 写入）→ **② 终态事务**
  （只写 `Execution.status` 终态，**不再写计数**——终值已随①落定）→
  **③ `_notify_finished` 通知** → **④ 轮询自然收敛**（两条流各自看到
  终态后发 done 帧收口）。
  关键约束：`run.finished` 事件与全部日志**先于**终态状态可见——事件流
  的 `finished_seen` 收口条件、日志流的 done、S6 摘要取数、S9 计数读取
  共用这一条不变量（现行代码顺序已正确，此处升格为协议级规定 + 防回归
  用例）。

## 8. 量级、索引与连接预算

- **量级**：#304 三步 ≈ 99 行 stderr（70 JSON）/ 23 条事件，INFO 全量约
  4-5× 事件量；12 步多行执行数千行、单行数百字节，PG 无压力。并发上限
  已被 `EXEC_MAX_SERVER_INSTANCES=8` 钳制；
- **极端防护**：泵侧逐行解析 + ingester 缓冲（批 200/0.5s 落库，flush
  失败回填重试不丢；**logs 缓冲上限 50k，超限丢最旧计数入 S9**——events
  不设上限，台账不可丢；`_flush` 全路径 single-flight 锁保证执行内 id
  单调，见 AD2/AD5）；
- **索引**：tail 查询改 `id > cursor` 后天然按主键序扫描；静态 (ts,id)
  排序单执行规模（数千行）内存排序可接受——批 1 验收补一条 EXPLAIN
  记录（`WHERE execution_id=? ORDER BY ts,id` 的计划），不为它预先加索引；
- **连接数**：详情页同时开事件流+日志流 = 每标签页两条长连接；HTTP/1.1
  同源 6 连接上限下开三个详情页会挤压普通 API 请求。缓解：**面板收起即
  断开日志流**（D3）；部署侧确认反代是否启用 h2（有则天然缓解）；
- **归属**：日志行自带 unit/step 标签，行级过滤 `?unit=case-000…&step=step-002`
  直接命中；跨槽位时钟偏差只影响全局时间轴美观，不影响归属正确性（时钟
  前提见 AD4）。

## 9. 筛选能力矩阵

筛选维度 = 入库标签列（已建，`execution_events` 模型），三层能力对齐：

| 维度 | API `/events`（已有） | 分析页 UI（已有） | `/logs/stream`（新增） | 实时面板（批 3） |
|---|---|---|---|---|
| kind（事件/日志） | ✅ | ✅ 下拉 | 固定 log | 固定 log |
| level 精确 / level_min（warning+ 序比较） | ✅ / ✅ | level_min 下拉 | ✅ 服务端 | ✅（本地+服务端） |
| category（含聚合 chip 点选） | ✅ | ✅ + `/events/counts` 聚合 | ✅ 服务端 | ✅ |
| module / service / unit（case 行）/ step / event_type | ✅ | ✅ 全暴露 | ✅ 服务端（event_type 除外） | step 快捷 + 本地 |
| message 全文 search（ILIKE） | ✅ | ✅ | ✅ 服务端 | 本地即时 |
| after_seq / cursor 续传 | ✅（事件=seq） | — | ✅ **id（精确续传）** | 随流 |

边界（有意不做）：**payload 内字段不作筛选维度**（只有标签列可筛——新字段要
可筛需加列，见 §11 两级扩展故事）；时间范围筛选不做（单执行域天然有界，
时间轴排序即够）；跨执行的全局日志检索不做（查询域 = 单执行）。

## 10. 退役与保留清单

**不退役（角色变化或保留原位）：**

| 项 | 处置 |
|---|---|
| `case-artifact?file=engine-log` 原始文件按钮 | 保留，降级为审计兜底：看未入库的 DEBUG 级、排障「入库链路自身」故障；S1.5 的多 worker 文件回落歧义在**入库面**被根治（按标签归属），文件面回落保持原样（兜底场景可接受） |
| `server-engine.log` 文件 | 保留，全量级别（门槛只作用于入库），原始字节审计原则 |
| 日志负数 seq 写侧 | 保留，语义降级为唯一性令牌（AD4） |
| 3s 兜底轮询（N5） | 保留；SSE 复活后回归「保险」角色（SSE 断流生命线） |
| 日志分析页 `ExecutionEvents.vue` | 保留并增强（排序修/行展开/混合时间轴/URL 过滤态） |
| launch 链 `on_log` 接线 | **本设计不动**；随 launch 链自身既定退役节奏走（EXEC_CHAIN 灰度已收口，launch 退役是既有路线图事项，不因本设计提前） |

**真正消失的（被替代）：**
- 「server 链日志只在文件里、平台查不到」的现状；
- 事件页对 server 链执行「筛 kind=log 永远空结果」的现状；
- SSE 隐式行为（无 kind 过滤、靠 after_seq 恒正意外滤掉日志）→ 显式
  `kind=event`；
- 字面量 `\n` 帧发射 → 规范帧；
- 日志文件/展示面的 ANSI 乱码（AD8 治理：非 JSON 行转纯文本、uvicorn 行
  转 JSON）；
- 前端类别下拉与引擎词表的双源漂移 → counts 驱动。

**结论：无用户可见功能退役**；内部语义修正若干，launch 接线随链退役。

## 11. 扩展性：「订制日志打印」与新策略/协议

每层有明确的扩展点与代价：

| 订制诉求 | 扩展点 | 代价 |
|---|---|---|
| 引擎加新**上下文字段**（如订单号、租户标记） | AD1 全字典入 payload | **零改动**即可见（分析页行展开可看）；要成为**可筛维度**才需加标签列+索引（一次机械迁移）——两级扩展故事 |
| 引擎加新**日志类别** | `gimbal/log/category.py` 前缀表加一行 | 引擎侧一行；平台 category 列即刻可筛、聚合 chip 自动出现 |
| 自定义**级别** | `query_events` 的级别序元组同步加 | 平台侧一行 |
| 平台侧**装饰/富化**（入库前补 slot/case 归属、租户标记） | 泵回调 `on_log` 是唯一拦截点 | 平台侧局部，不动引擎 |
| **写侧策略**（按 category 规则、按执行覆盖 DEBUG） | AD3 级别门槛同一闸口扩展 | 平台侧；D4 即此形态 |
| **按执行控制日志级别** | 平台 spawn 时传 `GIMBAL_LOG_LEVEL` env（机制已存在） | 零引擎改动 |
| 前端**订制呈现**（per-category 配色、自定义列、导出格式） | 行渲染是结构化字段的纯函数 | 纯前端 |

**新策略 / 新协议（高频扩展场景）：零注册，按构造生效。**
- 归类是**结构性**的（logger 名前缀映射），不是**行为性**的（注册表成员）：
  新策略落在 `gimbal.strategy.*` → 自动 category=`strategy`；新协议落在
  `gimbal.protocols.*` → 自动 category=`call`；引擎自身的 ext 注册面
  （`gimbal ext list` 六张表）与日志管道**刻意解耦**，平台不消费它；
- step/service/unit/attempt 标签在步骤边界由状态机 contextualize 绑定，
  策略/协议内部代码**自动继承**——新扩展无需自行传播上下文；
- 引擎侧仅两条**编码惯例**（非注册）：① 用 `get_logger(__name__)` 且模块
  落在 gimbal 命名空间（仓库既有惯例；越界者落 `core`，仍流通只是筛选粒
  度变粗）；② 协议/调用边界按现有协议惯例绑 `exec_context(protocol=…,
  endpoint=…)`，否则该协议日志行缺 protocol/endpoint 标签；
- 要独立**新类别名**才动代码：`gimbal/log/category.py` 前缀表 + 同文件
  `CATEGORIES` 词表（订阅校验消费）两行；
- 前端类别下拉改 counts 驱动（批 3 顺手修，已缺 `step`/`resolve`/
  `context` 三个现存类别——硬编码漂移的实证）。

红线（设计性边界，扩展不越过）：筛选维度必须落在标签列（payload 不可筛，
§9）；单执行查询域（不做跨执行全局日志检索）；引擎字段契约仍以 JsonSink
为唯一真源（平台不自造结构）。

## 12. 实施批次（批 1-5，每批独立验收）

| 批次 | 内容 | 依赖 |
|---|---|---|
| **批 1 骨干** | 泵拦截+on_log 接线+级别门槛+**logs 缓冲上限**+**_flush 全路径 single-flight 锁**+排序修+帧分隔符修+帧结构测试+spawn env `NO_COLOR=1`+模型注释「seq 对 log 无序」+EXPLAIN 记录 | — |
| **批 2 流** | `/logs/stream`（**id tail 游标**/backfill/服务端筛选/**先 ts 后入库不缺行测试**）+ 前端共享 SSE 解析器 + 事件流显式 kind | 批 1 |
| **批 3 面板** | 详情页实时日志面板（S12 异常徽标/展开/**插入排序视口锚定**）+ 分析页排序/展开/类别下拉 counts 驱动 + 工件查看器 ANSI 感知 | **批 2**（面板消费 `/logs/stream`） |
| **批 4 诊断导航包** | S1（失败事件锚点+unit）+ S2（around+n_before/n_after）+ S3 混合时间轴 + S4 深链/导出（快照）+ S8 调试台胶水 | 批 1-3（其中 S2 的后端端点仅依赖批 1，可先行） |
| **批 5 运营与通知包** | **S11A 抽查（先行）→ S6 通知摘要（硬顺序）** + S5 降噪（调用点键）+ S7 长尾（固定行高+右抽屉）+ S9 自监控（快照+双写）+（可选捎带 S12 堆栈、AD8 引擎侧两小项） | 批 1 |

批内顺序：批 5 中 S11A → S6 硬顺序；批 4 中 S2 后端面可与批 2/3 并行。
每批验收门：后端对应面测试 + 前端 vitest + vue-tsc 零错 + 浏览器主路径。

**后端测试要点**：泵（好行/坏行/回调异常/门槛/**DB 慢注入泵不阻塞/
缓冲上限丢最旧**/**泵侧丢弃行计数也随 flush 落库：尾部仅丢弃行终值完整**/
**single-flight 并发：慢 DB 下阈值与 ticker 同时触发，断言同一时刻至多
一个 flush 在途**）；排序（跨批乱序样本）；**SSE 帧结构断言**（真换行切帧
解析 id/event/data，禁子串）；`/logs/stream` backfill/**id 精确续传**/
终态/**先 ts 后入库不缺行**；S6 竞态防回归（尾日志刚入缓冲即终态，§7
收口语义）；S9 对账（快照幂等重放不重复计数；`ingest_stats` 与
`counterDrift` 共存不覆盖）；入库行零 ANSI 回归断言。**集成**：server 链
活体——发起真实小执行 → `/events?kind=log` 非空、`?step=<失败步>` 命中
WARNING 行（#304 型场景回归样例）。**前端**：共享解析器真换行单测；SSE
帧驱动刷新（fake timers）；面板渲染/筛选/暂停/**收起断流**；导出行数对账。

## 13. 决策点（D1-D10，均带建议值）

| # | 问题 | 建议 |
|---|---|---|
| D1 | 入库级别默认值 | INFO（DEBUG 只在文件；WARNING 起会丢 step/context 类有用 INFO 行） |
| D2 | 日志流 backfill 默认条数 | 200；语义=**仅首次打开回看**（cursor 改 id 后重连走精确续传，backfill 不再承担断线补窗） |
| D3 | 面板入口形态 | 详情页行内抽屉（展开即 tail），**收起即断开日志流**（连接数预算，§8）；分析页保持事后深查定位 |
| D4 | 按执行临时开 DEBUG 入库 | 一期不做；需要时改配置重启即可（执行频率低） |
| D5 | 事件/日志保留期 | 本设计不绑；执行保留策略独立立项（现状：随执行 CASCADE，无清扫） |
| D6 | 通知摘要锚点与格式 | **失败事件前最近 WARNING/ERROR + 其前同 unit/step 一行**（两行分 200 字符——S1 实证根因细节常在 INFO；回退：失败前最后两条日志行 → 现状文案）；每失败 unit 一组 × 最多 3 组；出口打码；`extract.failed` 事件立项后改优先取事件 payload |
| D7 | 脱敏策略 | A（引擎纪律 + 全类别抽查）+ S6 出口窄防护；B 挂起 |
| D8 | 跨执行对比一期形态 | 深链并排，不做内建 diff |
| D9 | 导出格式与边界 | 前端双格式；**冻结快照上界**写入文件头；行数上限 50k 超限提示 |
| D10 | S12 精简堆栈 | 引擎侧可选项：`GIMBAL_LOG_STACK_FRAMES=N`（或 DEBUG 自动开），默认关；独立小项不占批次 |
