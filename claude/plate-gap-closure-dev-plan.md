# Plate 缺口收口：设计开发计划（v1.0）

> 日期：2026-10-12　基线：`feat/plate-s1 @ 1324f5f`
> 依据：①《Plate 相关实现遗漏检查 2026-10-12》（A-1~A-7 缺陷、B-1~B-7 设计未实现、C 组后置）；②2026-10-12 环境侧遗留项审计（构件分支/PLATE_ARTIFACTS_PATH/零修订/49 端点 draft/RS5 零测试/dev-plan 勾选滞后）。
> 原则：延续 dev-plan v1.0——不为兼容现状妥协、每批带验收门、门不过不合入下一批；运营步骤（P0/P2）与代码批次（P1/P3）并行推进。
> 状态：`[ ]` 未开始　`[~]` 进行中　`[x]` 完成

## 0. 范围与来源

两份检查互补：环境侧审计的结论是**代码全量落地但修订发布链从未在本环境走通**（`plate/artifacts` 分支与 `D:\Gimbal\plate-artifacts` 检出不存在、远端无此分支、plate 服务未配 `PLATE_ARTIFACTS_PATH`、活体 `/api/system/fin/lines` = `registry_unavailable`、rs3 两脚本挂起、全场景 `meta.plate={}`）；遗漏检查的结论是**平台对版本模型的消费有 7 处缺陷 + 7 处设计未实现**，且"按修订编排"链路在今天之前从未真正跑通（4 个修复提交佐证）。

**关键裁定（2026-10-12 用户拍板）**：
1. **working 优先、渐进接入**：全场景默认留在 working ref，版本管理按系统逐个接入（大部分系统尚未落库注册）。接入一个系统 = 注册系统树 → 评审 → 首修订 → 该系统场景钉修订。**rs3 两脚本不做全局回填**，保留为接入工具随接入按系统执行。因此 A-2/A-3 **随 P1 部署、不等回填**——working=预览/不入库是接入前的如实标注。连带效应须周知：**系统接入前，集成任务被 A-4 全量拒绝**（版本模型 §6 语义；dev 集成卡本就空载，可接受——若未来需要过渡期可用，须另行拍板，不做静默兼容）。
2. A-3 落点：`executions.baseline_eligible` 列 + `execution_events` 证据事件 + alembic 0019（已同意）。
3. P2.2 platform 评审完再发首修订（已同意）。
4. **三态接入模型（2026-10-12 用户提出）**：除 working/钉修订外增加第三态 **external（第三方服务接入，无版本管理）**——大部分第三方服务不落库，需要显式标注，而不是混在"尚未接入"里。external 不触发预览、不阻塞集成；**不计入可信基线统计，按外部桶单独统计**（已拍板，见 P1.5 数据形态）；标注落平台服务注册表（`service_aliases.kind`），plate 侧与 M2 形态零改动。详见 P1.0。

不在本计划：C 组后置项（Q12/Q14/CLI 离线加载/语义层读出面/plate 写入服务化——维持各自原排期）；生产部署清单（已有，P4.3 刷新引用）。

## P0　启用链（运营先行；产出 = fin 首修订上线）

- [x] **P0.1 重建构件底座**：`git checkout --orphan plate/artifacts`（空树提交）→ `git worktree add D:\Gimbal\plate-artifacts plate/artifacts` → **立即推远端**（上次丢失的根因 = 构件只存在作者本机，从未 push）→ 重跑 `scripts/gen_m2.py` 使 M2 信封重入构件分支（3.6 第二写入方）。
- [x] **P0.2 配置注入**：`PLATE_ARTIFACTS_PATH=D:\Gimbal\plate-artifacts` 注入 plate 服务进程（restart-services.ps1 启动行加环境变量，或系统级；run_plate.py 自身不读 dotenv）→ 重启 → 探针 `GET :8765/api/system/fin/lines` 从 `registry_unavailable` 变 200。
- [x] **P0.3 fin 发首修订**：fin 树 0 draft / 24 reviewed，无评审阻塞。`plate release`（先演练看 findings，再正式）；验证 manifest（corrections/warnings）、`/diff`、resolve_effective 生效修订解析。
- [x] **P0.4 接入试点 + 运行手册（不全局回填）**：发首修订后，在编排器**手动**把 1–2 个 fin 场景钉到首修订做链路活体验收（版本下拉选修订 → 按修订渲染契约表单 → 执行 → 执行记录带 `plate_pins`）。`rs3_backfill_meta_plate.py` 与 `migrate_strip_binding_fields.py` 保留为**接入工具**，随各系统接入时按系统执行（演练→备份→apply→幂等复跑纪律不变）。沉淀《系统接入运行手册》入库 docs/：注册系统树 → 评审 → 首修订 → 场景钉修订（手动或 rs3）→ strip → 验证清单。
  - 验收门：试点场景按修订渲染、执行带 `plate_pins`；手册入库。

> **状态(2026-10-12)**:P0/P1(W1-W16)全部落地并推送;plate 门 639 绿、
> 后端 825 绿、前端 1214 绿、vue-tsc 零错。遗留:W10 顺带修复了
> `_commit_artifacts` 探测过松(祖先杂散 .git 被向上发现)与空提交报错;
> 141f2b1c 自举批的过期计数/基线/规范形已在 40517dcd 重钉。波次 C/D
(W17-W26)未动 —— W17(platform 49 端点人工评审+首修订)需用户参与。

## P1　平台消费侧止血（A 组，代码批）

按数据风险排序；全部与 P0 无依赖、可即做。A-2/A-3/A-4 随本批部署即生效——接入前 working=预览是如实标注（§0 裁定 1）；**P1.0 三态底座先行，P1.3/P1.4/P1.5 的口径都建立在它之上**。

- [x] **P1.0（先行，新增）第三方服务外部态（external）**：服务接入从两态扩为三态——`managed+钉修订` / `managed+working` / `external（第三方，无版本管理）`。落点 = **平台服务注册表**：`service_aliases` 加 `kind` 列（`plate` | `external`；回填规则 = base_service 出现在任一 plate 系统的 services 声明 → `plate`，否则 → `external`；此后新建别名显式选），alembic 0019（与 A-3 同批）。判定链 = 场景步骤 `service` → 别名 `kind` ∪ `meta.system` 声明；两者皆无 → 保存时告警（unknown service，提示接入 plate 或标注 external）。口径：**external 不触发预览、不阻塞集成**（集成卡本职即验证外部集成），且**不计入可信基线统计、按外部桶单独统计**（入库 = 版本模型 4.3 的**可信基线统计口径**——执行记录照常落库存储、场景照常编排/执行/回放；分桶形态见 P1.5）。UI：编排器/执行详情三态徽标（钉修订 / 当前规格 / 外部·无版本）。external 服务不进 `meta.system`（无 M11 冲突）、其步骤无锚点原样通过 convert——**plate 侧与 M2 形态零改动**。与集成卡 P2「外部系统定义」缺口合流：一次定义，两处消费（执行口径 + 集成卡）。
  - **接口信息边界**：external 步骤的接口信息现状 = **步骤内联手工维护**（method/path/headers/body 存在步骤定义里，执行经 service_aliases 解析 URL，链路已通，缺的是结构化渲染与校验）；结构化升级路径 = **外部接口登记**（平台侧轻量目录：URL 模式 + method + 可选 JSON Schema，支持 OpenAPI 导入，登记后步骤可锚点化、恢复结构化表单与保存校验）——与集成卡 P2「外部系统定义」同批实现，**不在本计划 P1 范围**。
  - 测试：三态判定链、unknown 告警、kind 回填规则、三态徽标。

- [x] **P1.1（A-1，高：数据丢失）ScenarioMeta 读侧透传**：`schemas/scenario_composer.py:40` 手写 meta 改为"定义里的 `meta` 原样透传 + 行上列覆盖 `scenarioId`/`updateTime`/`owner`"（或直接用生成物 `Meta`），删除手写字段清单；删除 `update()` 中 `system` 空写 `["default"]`、`module` 空写 `"default"` 的伪系统兜底（与 M11"每个系统必须有 plate 声明"冲突）。测试 = 遍历 M2 `Meta` 全字段断言读写往返不丢（`requirementRef` 实测丢字段案例入测试）。
- [x] **P1.2（A-5）M2 对象池写入**：读取点在 `routes_grammar.py:376` 与 `release/read.py:181`（`<构件根>/objects/{hash}.json`），但全仓无写入方。实现 = plate 启动（或 gen_m2）把当前 M2 内容寻址写入 `objects/{hash}.json`，幂等；未配构件根时启动静默跳过 + 计数告警（发版路径仍按 3.6 fail-fast）。写入走 release.py 同款构件分支提交机制，不留脏树。测试 = 写入幂等 + 按 hash 取回 + 未配置时行为。
- [x] **P1.3（A-2）预览判定口径**：`run_dispatcher.py:638` `is_preview = bool(req.debug)` 改为版本模型 §6 口径——**任一 managed 系统为 working 即预览**（external 不触发，见 P1.0）；调试执行钉了精确修订则不算预览。
- [x] **P1.4（A-4）集成任务拒绝 working**：`integration_runner` 触发前检查场景 `meta.plate`，任一 managed 系统 working → 409（文案指路"钉修订或等回填"）；**external 放行**。只读护栏的回落读取行为保持。
- [x] **P1.5（A-3）入库标准记录**：版本模型 4.3——无 managed 系统 working、生效修订中场景用到的接口全部已评审、且无 external 服务。**设计落点（本计划拍板）**：`executions` 加两列——`baseline_eligible`（bool，严格门：自举指标分子）+ `baseline_block`（String，可空，首要阻塞原因 `working` | `unreviewed` | `external`；多因全量记证据事件）——**external 执行按 `baseline_block='external'` 单独分桶统计**（通过率/稳定率可按桶出，不混入基线分母）；`execution_events` 记 `baseline_eligible` 证据事件（未过接口清单 / external 服务清单 / working 系统清单），alembic 0019。本批只做判定+记录，**消费面（自举 Agent 指标、统计报表）另立项**。
- [x] **P1.6（A-6）旧适配残留清理**：删 `POST /adaptations/catalog/diff` 空桩 + `stores/adaptations.ts`、`useInterfaceChange.ts` 调用点；"接口变更"提示由 `useVersionHints`（"定义已修正"）承接；`impact`/`refs_drift`/`impact_summary` 三个按 working 全局目录计算的函数按"不保留兼容设计"删除（若有引用面先迁移到生效修订口径再删）。
- [x] **P1.7（A-7 + 链路级用例）**：I-1 回归测试补上；新增端到端用例 = `_release_fx` 真 plate + 平台测试客户端，覆盖"按修订编排→保存→执行→执行详情"断言每一步读的是同一修订（拦"单测全绿、链路不通"类——本次 4 个修复提交全是这类）。
  - 验收门：三侧全量零回归；P1.1 往返测试与 P1.7 链路用例绿。

## P2　platform 评审与收口（人工 + 运营；P2.1 可与 P1 并行）

- [x] **P2.1 49 端点人工评审**：141f2b1c 自举批 49 个 `review: draft` 端点逐个过（人工动作；自举文档在 `gimbal-tmp/bootstrap/` 本机留存可参照）。
- [x] **P2.2 platform 发首修订**：**评审完成后**再发（draft 状态发版只会带 warnings 进修订，评完再发可避免修订语义噪音；这也与"评审过的定义才可信"的入库标准口径一致）。
- [x] **P2.3 platform 接入**：对该系统的场景执行 rs3 两脚本（幂等）或编排器手动钉修订，按 P0.4 手册流程走。
  - 验收门：fin/platform 两个已接入系统的场景零 working；已接入系统的执行记录 `plate_pins` 全量有值。

> **状态(2026-10-13 补记)**:P2 全部落地 —— P2.1 49 端点 2026-10-12 评审清零(plate-s1-review §3a);P2.2 `platform@1.0#1` 已签发推远端(构件 739941c2);P2.3 rs3 两脚本已跑(36 场景钉修订,33 剥离派生字段,复跑 0),验收门过(见《系统接入运行手册》§3/§3a)。本节框当时漏勾,非未做。

## P3　B 组（按遗漏检查 D.3 序；P3.3 依赖"已钉修订场景存在"——P0.4 试点即满足）

- [x] **P3.1（B-4）RunRequest 形状**（✅ W19/14241574：runOptions 生成物形状 + 上限 64 + DebugLaunchSpec 删;Q4 已折回 M2 方案决策表）：Q4 结论已在 dev-plan T1.1 落定（nRuns/parallel 无超 64 存量 → 平台对齐 64），**折回 M2 方案 Q4 行成文**；`RunRequest` 平铺 `stepTo`/`nRuns`(≤1000)/`parallel`(≤200) 改 RunOptions 生成物形状、上限对齐 64；`DebugLaunchSpec` 一并生成物化。
- [x] **P3.2（B-5）镜像清零收尾**（✅ W20/31e6a894：AuthSession 持生成物 UserCredential;DebugCommandIn 生成化 gen_m2 dbgcmd 目标;checks→CheckDecl;director skill 改读 /api/m2）：平台 `AuthSession` 改持有生成的 `UserCredential`、`DebugCommandIn`、`DebugLaunchSpec`、Suite `checks` dict→生成物、director skill 改读 `/api/m2`（删静态 scenario-schema.md）。
- [x] **P3.3（B-1/B-2）执行详情修订台账（前端）**（✅ W21：当时修订/重跑将使用/不一致提示 + 趋势切换点(SignalDots 蓝环) + m2_hash 派发回填 + W11 三态展示并入）：显示"当时的修订"（`plate_pins`）与"重跑将使用的修订"，不一致时提示；执行趋势图在修订/版本线变化处标切换点。
- [x] **P3.4（B-3）RS4b"应用到同类步骤"**（✅ W22/ccc6db8c：applyToSimilar 按锚点展开,逐 pass 重扫索引,非收敛保护）（`submit-suite` 已有，补同类步骤批量应用）。
- [x] **P3.5（B-6）事件表 payload**（✅ W23/62d7cbd9：fields 提取缺陷修复(FieldInfo→get_default),25 条全满;m2.hash_mismatch 移入 events/ 入表）：ext 快照 24 个事件的 `fields` 填充；`m2.hash_mismatch` 从 `server_debug.py` 移入 `events/` 并入表。
- [x] **P3.6（B-7）plate_client 按修订缓存**（✅ W24/63425b6e：三读取面容量 64 FIFO/LRU,无 TTL;strict_ref 死代码删除）：修订条目不设 TTL、只按容量淘汰（与 b4a8bfc0 修订缓存同机制）；`declarations_of_at` 入缓存；删 `strict_ref` 死代码。
  - 验收门：每项自带测试；P3.1 后 CI 三形态重生成守卫绿。

## P4　测试与文档收尾

- [x] **P4.1 RS5 冷化测试**（✅ W25：test_cold_archive.py 六例——引用闭包/pin/working/多线）：`release/cold_archive.py` 全仓零测试引用——补判定查询测试（被场景引用 / 可能成为生效修订 / 被执行记录 `plate_pins` 引用的修订不在清单中）。
- [x] **P4.2 dev-plan v1.0 勾选同步**（✅ W26：T1.1/T1.6/T4.1/T4.2/T5.2 改勾）：T1.1①（api→call 已落）、T1.6 待做项（版本线声明已入库）、T4.1/T4.2（主体已交付）、T5.2（冷化已实现）改勾；本计划状态随批同步。
- [x] **P4.3 生产部署清单刷新**（✅ W26：构件分支重建+必推远端、alembic 0019/0020 已并入 docs/系统接入运行手册.md §0/§4 与 runbook-pg 原地升级记录）：并入 P0.1 构件分支重建步骤（含推远端）与 P1.5 的 alembic 0019。

## 任务拆分与实现序（2026-10-12，v1.0）

四个实施波次；波次 A（代码）与波次 B（运营）可并行。规模：S≈半天内 / M≈1–2 天 / L≈2 天以上。

### 波次 A　平台消费侧止血（对应 P1；W1–W12）

| # | 任务 | 落点 | 前置 | 验收 | 规模 |
|---|---|---|---|---|---|
| W1 | A-1 meta 读侧透传 + 删 default 兜底 | `schemas/scenario_composer.py:40`、`scenario_store` 读写两侧 | — | M2 `Meta` 全字段读写往返测试绿（`requirementRef` 案例入测） | S |
| W2 | alembic 0019：`service_aliases.kind`（default `external`）+ `executions.baseline_eligible/baseline_block` | `alembic/versions/0019_*.py` | 与 W3 同批 | 迁移幂等；PG 演练 | S |
| W3 | kind 回填脚本 + 三态分类 helper | `scripts/p1_backfill_service_kinds.py`（演练/--apply，按 plate `/api/systems` services 声明分类）+ `app/services` 分类函数（步骤 services ∪ `meta.system` → plate/external/unknown） | W2 | 回填幂等；分类函数单测 | M |
| W4 | 别名管理面 kind 出入参 | `models/service_alias.py` + 别名路由 + 前端服务信息页选择器 | W2 | 新建别名显式选 kind | S |
| W5 | A-2 is_preview 三态口径 | `run_dispatcher.py:638` | W3 | 单测覆盖：working→预览、external→非预览、debug 钉修订→非预览 | S |
| W6 | A-4 集成拒绝 working | `integration_runner` 触发前检查 → 409（external 放行） | W3 | 409 用例 + external 放行用例 | S |
| W7 | A-3 baseline 判定+落库 | 执行终态化写入点（`run_dispatcher` fanout 收尾）：写 eligible/block + `execution_events` 证据事件（多因全量） | **W8** | 判定单测三桶（eligible/working/external）+ 事件证据落库 | L |
| W8 | plate 出参补评审状态 | `get_endpoint_full_at` / `get_projection` 响应带对象 `review`（plate 侧只读加法 + 测试） | — | 平台可按钉定修订取到逐接口 review | S/M |
| W9 ✅(bff7535e) | A-6 旧适配残留清理 | 删 `POST /adaptations/catalog/diff` 空桩 + 前端 `stores/adaptations.ts`、`useInterfaceChange.ts`；`useVersionHints` 承接；删 `impact`/`refs_drift`/`impact_summary` | — | 前端"接口变更"提示消失或由版本提示承接；三侧零回归 | M |
| W10 ✅(d14edb23+40517dcd) | A-5 M2 对象池写入 | plate 启动把当前 M2 内容寻址写 `objects/{hash}.json`（走 release.py 同款构件分支提交；根未配置→跳过+计数） | W13（构件根存在才可全验） | 写入幂等 + 按 hash 取回 + 未配置行为 | M |
| W11 ✅(760925e7) | 三态徽标 + unknown 告警 | 编排器步骤/执行详情徽标（钉修订/当前规格/外部·无版本）+ 保存 unknown service 告警展示 | W3 | vitest 徽标/告警用例 | M |
| W12 ✅(0e8370c9) | I-1 回归 + e2e 链路用例 | 平台测试进程内起 plate app（httpx ASGI）+ `_release_fx` 夹具；"按修订编排→保存→执行→执行详情"同修订断言 | W13 可选（夹具自建则无依赖） | 链路用例绿；能在本地复现"读侧丢字段/缓存键错配"类缺陷 | L |

提交分组（每组过三侧门：后端 pytest / 前端 vitest / plate pytest）：W1 → (W2+W3+W4) → (W5+W6) → (W8→W7) → W9 → W10 → W11 → W12。

### 波次 B　启用链（对应 P0；W13–W16）

| # | 任务 | 落点 | 前置 | 验收 | 规模 |
|---|---|---|---|---|---|
| W13 | 构件底座重建 | 孤儿分支 `plate/artifacts`（空树提交，git plumbing）→ `git worktree add D:\Gimbal\plate-artifacts` → **push -u origin** → `gen_m2` 重发 M2 信封（CLI 用法实现时查 `scripts/gen_m2.py`） | — | worktree 三检出；远端有分支；信封对象在池 | S |
| W14 | env 注入 | `restart-services.ps1` plate 启动前设 `$env:PLATE_ARTIFACTS_PATH`（子进程继承） | W13 | 探针 `/api/system/fin/lines` 由 `registry_unavailable` → `ok` | S |
| W15 | fin 首修订 | `plate release`（演练看 findings→正式） | **工作区净（先提交 claude 文档，B1 脏树门会拒）**、W13/W14 | `plate lines` 见 `1.0#1`；manifest corrections/warnings 合预期；`/diff`、resolve_effective 通 | M |
| W16 | 试点钉定 + 运行手册 | 浏览器把 1–2 个 fin 场景钉首修订→执行→`plate_pins`；写 `docs/系统接入运行手册.md` | W15 | 试点场景按修订渲染、执行带 pins；手册入库 | M |

### 波次 C　platform 接入（对应 P2；W17–W18）

| # | 任务 | 落点 | 前置 | 验收 | 规模 |
|---|---|---|---|---|---|
| W17 | 49 端点人工评审（`systems/platform/endpoints/`，参照 `gimbal-tmp/bootstrap/` 文档） | 人工动作，可与 A/B 并行 | — | draft 清零 | 人工 |
| W18 | platform 首修订 + 接入（按 W16 手册：release→rs3 两脚本或手动钉） | W17 | 已接入系统场景零 working、`plate_pins` 有值 | M |

### 波次 D　B 组与收尾（对应 P3/P4；W19–W26）

W19 B-4 RunRequest 改形+Q4 折回 M2 文档（M）；W20 B-5 镜像清零（M/L）；W21 B-1/B-2 执行详情修订台账+趋势切换点（M，前置=已有钉定场景）；W22 B-3 应用到同类步骤（M）；W23 B-6 事件表 fields 填充+`m2.hash_mismatch` 入表（M）；W24 B-7 plate_client 按修订缓存+删 strict_ref 死代码（S/M）；W25 RS5 冷化测试（S，`tests/plate/test_cold_archive.py`：被引用/可能生效/被 plate_pins 引用的修订不在清单）；W26 文档同步（dev-plan 勾选、本计划状态、生产部署清单刷新）（S）。

### 风险与注意

- **W7 依赖 W8**：plate 现有 projection 出参无 review 字段（`routes_grammar.py` grep 零命中）——若快照对象数据里已带 review 则 W8 只是透出，更小。
- **W12 是最大测试工时**：平台测试内起 plate app 是新基座（plate 自身 `test_http_*` 已有进程内先例可抄）。
- **W15 脏树门**：发版前 `git status` 必须净；先提交计划文档再执行。
- **后端无 --reload**：波次 A 每组合入后需手动重启做浏览器验收。
- alembic 0019 一次承载 P1.0+P1.5 全部新列，避免双迁移。

## 依赖与里程碑

```
P0.1 ─▶ P0.2 ─▶ P0.3 ─▶ P0.4（试点 + 手册）
P1（全部独立可即做；A-2/A-3/A-4 部署即生效 = 接入前全量预览/集成拒绝）
P2.1（人工评审）─▶ P2.2 ─▶ P2.3（platform 接入）
P3.3 起 B 组随时可做（试点钉定后即有可演数据）
```

- **里程碑 MC1** = P0 + P1：修订链可用（试点钉定 + 接入手册）+ 平台口径正确（预览/入库标准生效）
- **里程碑 MC2** = P2：fin / platform 两系统接入完成（其余系统按手册渐进接入，不在本计划排期）
- **里程碑 MC3** = P3：B 组清零
- **里程碑 MC4** = P4：测试与文档收口

## 后置（维持原排期，不在本计划）

| 项 | 出处 | 排期 |
|---|---|---|
| CLI / Agent 离线加载修订构件 | Release §7 | 随 task 5 |
| 语义层（词条/片段/交付物）读出面 | 设计完整性评估 3.1 | 自举 Agent 线之前 |
| Q12 平台 Suite 预检 import 执行器编译器 | M2 欠账 | task 5 时改调执行器校验接口（注：platform app/ 现已零 gimbal import，实际欠账仅剩 Suite 预检一处行为面） |
| Q14 JSONPath 三份实现唯一化 | M2 欠账 | 依赖方向调整时（对拍测试已有） |
| plate 写入服务化 / 版本线配置页 | Release | 已定等 plate 服务化 |
