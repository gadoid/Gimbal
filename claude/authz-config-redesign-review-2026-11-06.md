# Gimbal 权限与配置改造：全量问题清单（2026-11-06）

- 核对对象：`authz-config-redesign-consolidated-2026-11-06.md`（方案）、`authz-config-redesign-impl-changes-2026-11-06.md`（实施变更点），均为第四轮修订版
- 代码基线：`feat/plate-s1 @ 85f8e2d`（含 `feat/logs-reports` 合入）
- 核对轮次：第一、二轮为方案自带（其 §九 / §十）；第三轮为基线漂移核对（方案 §十一，`dc1243a → 85f8e2d`）；第四轮为收尾复核（量级重估、残留一致性、前端耦合点），即本清单成文时；第五轮为成文后复核（两份文档全量通读、未核项关闭、剩余断言抽检）；第六轮为外部评审吸收（2026-11-07，分模块开发方案评审的 5 必改 + 6 建议，逐条对代码核实后全部采纳）；第七轮为修订传播核对（上游两份文档对照开发方案逐条核对，补齐 5 条传播缺口与 3 处残留不一致，并吸收 3 个新问题）；第八轮为时机与口径复核（剥离时机、预检告警条件、恢复 SQL 范围，5 项全部采纳）
- 图例：✅ 已修订进两份文档 / 🔶 登记为实施注意或待定项 / ⚪ 已核实成立、无需动作 / ❓ 未复核（低风险）

---

## 一、与当前实现冲突——必须修订（7 项，第三轮发现，均已修订 ✅）

| # | 问题 | 证据（HEAD `85f8e2d`） | 修订落点 |
|---|---|---|---|
| A1 | **迁移撞号**：alembic head 已是 `0035_execution_steps`，方案的 `0035_role_rename` / `0036_platform_retire` 会分叉 head | `backend/alembic/versions/0035_execution_steps.py` | 方案 §六；实施 W1（`0036`）、C1（`0037`） |
| A2 | **`identity_mode` 默认值就是 `platform`**：只对显式 `platform` 返回 410 挡不住省略字段的创建请求 | `models/integration_task.py:69`；`TaskIn`（`routers/integration.py:244`）同默认且无 Literal 校验 | 方案 §六 M1 关闭入口行；实施 W5 |
| A3 | **`is_admin` 写侧镜像已不存在**：物理列已随 `0004_drop_is_admin` 删除，原「写侧镜像改为 …」一行作废；只剩 `UserPublic._derive_is_admin` 读侧派生 | `models/user.py:49` 注释；`schemas/auth.py:93-107` | 实施 W1（改为更新派生口径） |
| A4 | **`is_sensitive_path` 不存在 + 发布零清理**：publish / copy / 订阅对 `config.users` 与数据集均原样扩散（copy 为 `deepcopy`），唯一剥离点在导入路径；数据集敏感列判定要从零写 | `scenario_store.py`（copy）；`scenario_import.py:550`（唯一剥离）、`:42`（`_SENSITIVE_RE`） | 方案 9.1 / 10.6；实施 W6 |
| A5 | **执行可见已单函数化**：`can_view_execution`（含 admin 分支与「平台执行对 member+ 可见」分支）被 detail / rows / events 与**基线后新增**的执行报告（B4）、批次汇总（B5）五入口共用——原「合并三个解析器」已完成一半，剩余工作只是删分支 | `core/deps.py:171-190`（分支 183-189）、`:239-242`；`routers/executions.py:366-384/160-175` | 方案 9.3；实施 W2 / W4 |
| A6 | **公共下架的收口量比原描述大**：admin 发布 / 下架不限定公共对象（入口闸 `ensure_owner` 对私有对象同样放行），且属主通知在 `was_public` 块外 | `routers/scenarios.py:638-744`（`:736` 通知） | 实施W3「保留的能力」补两处收口 |
| A7 | **C2 依赖 C1 迁移**：指纹闸现状只对 `identity_mode == "personal"` 且非持有人实例生效，平台模板完全绕过；不先迁移存量，订阅制平台模板不受指纹约束 | `services/integration_runner.py:991-993` | 实施 C2 写明顺序依赖 |

## 二、量级与行号修正（第三、四轮，均已修订 ✅）

| # | 方案原口径 | 实测（HEAD `85f8e2d`） |
|---|---|---|
| B1 | 后端行内角色比较：约 25 处 member + 约 45 处 admin | 约 70 处（routers ≈60、services ≈7） |
| B2 | 前端 `'admin'` 83 处 | 81 处 / 28 文件；`isAdmin`/`is_admin` 96 处 / 40 文件（不变）；`'member'` 48 处 / 20 文件 |
| B3 | 平台模式后端约 122 处 / 20 文件 | 四标记（identity_mode / PLATFORM_KIND / get_platform_user_id / platform-credentials）约 97 处 / 16 文件 |
| B4 | 平台模式测试文件 44 个 | **14 个**（宽口径 grep 实测 13-14，与实施 C1 清单吻合；44 为高估） |
| B5 | 前端平台模式约 110 处 | 109 处（含测试）；生产代码 70 处 / 19 文件；C1 前 10 个文件已核实存在 |
| B6 | 签发门「三处」 | `routers/access_tokens.py` 实为 5 处（234/280/284/328/334；234 为平台令牌列表可见性） |
| B7 | `users.py:354-395` 重置密码 | 344-392（行为断言全成立：明文返回 `:388-392`、不失效令牌、不 bump `token_version`、`must_change_password` 全后端不存在） |
| B8 | `run_dispatcher.py:1931` 内置凭证合并 | 1938-1945 |
| B9 | `scenario_composer.py:259` 是 RunRequest | 259 是 RunScheme；RunRequest.serviceBindings 在 393；ExportOverlay 274（三处都带字段的事实成立） |
| B10 | `adhoc_run.py:40`（隐含 routers/） | `services/adhoc_run.py:40`，拒收**整个 serviceBindings 字段** + 仅个人令牌闸（`routers/runs.py:214-243`），比原描述更严 |
| B11 | `suites.py:160 / 252 / 1653` | 156 / 255-256 / 1652-1659（163、433、1569 精确不变） |
| B12 | `integration.py:55-90` 判定函数 | 实起于 62（66/80/145 精确不变） |
| B13 | `access_tokens.py:282-298` 范围候选 | 270-298 |
| B14 | `carry.py:65`、`resolve_exec_auths:117` | 64-68、116 |
| B15 | 扇出 `1339/1349/1700`；`me.py` member 分支 | 1337-1340 / 1348-1351 / 1699-1702；`me.py:173-174`（语义澄清：管的是平台任务暂停可见，非执行统计） |
| B16 | 错误形状「字符串 `admin_only`」 | 实为前缀串 `"admin_only: this route requires an administrator"`（`deps.py:135`）；`role_forbidden` 在 `{code: …}`（`deps.py:120-123`） |
| B17 | 「v5 把导入开放给 User」 | 现状导入是 member+ 专属（`routers/scenario_import.py` 挂 `MemberUser`）——W7 是「先放开门、再加 `alias.write` 能力门」 |

## 三、顺序耦合与连锁反应（已写进文档 🔶）

| # | 耦合 | 说明 | 落点 |
|---|---|---|---|
| S1 | 前端 `'member'` 清零守卫 ← W1 | `UsersAdmin.vue`（9 处）与 `api/*` 类型 / zod 定义里的 `'member'` 是角色枚举本身，只有 W1 更名落地才消失；守卫必须与 W1 / W2 / W8 同版本生效 | 方案 §2.3；实施 W8 验收 |
| S2 | C2 ← C1 迁移 | 见 A7 | 实施 C2 |
| S3 | P2 部署表 → 订阅指纹集体漂移 | 同意指纹第七要素是「别名 base_url 集」（`integration_runner.py:471`），地址来源切换使全部订阅实例指纹不一致、集体暂停等重新确认——§1.2 的预期机制，上线按一次性全员暂停公告 | 方案 §六 M2a；实施 P2 验收、风险表 |
| S4 | W7 的两步顺序 | 先把导入门从 `MemberUser` 放开为 `CurrentUser`，再加 `alias.write` 能力门；顺序颠倒会短暂裸奔 | 实施 W7 |
| S5 | W1 + W2 同版本（方案原有，维持） | 角色迁移与判定收敛必须同一版本上线，downgrade 可用、上线前库副本演练 | 实施六（风险与回滚） |

## 四、第四轮收尾复核新增（5 项，均已修订 ✅）

| # | 发现 | 处置 |
|---|---|---|
| F1 | 方案 §七 分期表 M1 行残留旧表述「三个执行解析器合并成一个」，与 9.3 修订后口径不一致 | 已改为「执行可见判定收敛为 `can_view_execution` 单点删分支，覆盖含 B4/B5 的五个入口」 |
| F2 | 汇总页「测试文件 44 个」与实施 C1「14 个文件」自相矛盾；实测 14 吻合 | 方案 §六 M1.x 已改为 14 并注明原估偏高；实施 C1 测试段标题加实测口径 |
| F3 | 前端平台模式量级落数：109 处（含测试）/ 生产 70 处 19 文件 | 实施 C1 前端段已更新，10 个清单文件已核实存在 |
| F4 | **tokenId 死链**：`TokensSection.vue:254`「全部调用与回调记录」链接发 `?tokenId=`，但 `ExecutionsList.vue` / `Executions.vue` 都不读该参数（链接当前就无效）；M1 属主隔离后 admin 也无法经它查他人执行；`api/executions.ts:279` 注释口径（「令牌属主或 admin」）需同步 | 实施W8 新增一行：随 W4 定口径（删链接或改本人过滤） |
| F5 | 实施五（能力清理总表）「三个执行解析器」行未反映 A5 的部分完成现状 | 已改为「（可见性已收敛为 `can_view_execution`）｜删 admin / 平台分支，属主单判」 |

## 五、仍未复核（❓ 低风险，实施时顺手核对）

| # | 项 | 说明 |
|---|---|---|
| U1 | ~~W5 验收「15 个入口」~~ **已核（第五轮，G4）** | 实测 14 个端点挂 `PrincipalIn`（executions 5 / integration 7 / webhook_deliveries 3 / runs 2 / run_precheck 2，扣除 5 行类型定义），与 15 基本吻合；W5 验收已改写落数 |
| U2 | C1 前端 109 处未逐处归类 | 文件级清单已核实存在；逐处归类留给 C1 实施时按文件推进 |
| U3 | 执行视图外圈组件 | `SuiteRunsTab`、`DebugConsole`、`useScenarioRuns`、`stores/executions.ts` 等未逐个核（抽检 4 个无角色逻辑）；M1 执行可见收窄时若有回归测试兜底即可 |

## 六、已核实成立的关键断言（⚪ 抽检通过，无需动作）

- **私有区旁路（W3 靶点）**：`_ownership.py` 五处 admin 分支（32/45/117/135/145）；`suites.py` 163/433/1569；`scenarios.py:904`；`shares.py` 206/348/359；`integration.py` 66/80/145/169；`data_sets.py:92`；`adaptations.py:324`；`scenario_query.py:65-67`；`webhook_deliveries.py:117`；`executions.py:221-229` tokenId 例外（走 `services/access_token.py:439-440`）。
- **角色硬编码（W1/W2 靶点）**：`auth.py:96/106` 首注册与自愈；`users.py:75/248/454` 末位管理员保护；双 `Literal` 三值（`schemas/auth.py:85`、`schemas/user.py:17`）；`/auth/me` 无 `capabilities`；role 列 `String(16)` 无 CHECK（`models/user.py:50`）；`environments.py` 写操作零审计；`notifications.py:213` 公告 admin 专属；`suites.py:1652-1659` 版本分布无读检查；公共报告定义 `owner_id=None` + admin 可编辑（`report_definitions.py:123/155-183`，且 admin 编辑仅限公共无主定义）。
- **执行与凭证（W4/W6/P 系靶点）**：`can_view_execution` 规则与五入口复用；`query_views.py:91` 用查看者本人凭证；`auth_probe` 只测本人；`activity` 全部按本人过滤；`GET /carry/bindings`（64-68）全表返回；drift 只比对全局层；地址三层（①②在 `run_materialize.py:109/166-191`、③在 `run_prepare.py:277/341`）；`config.users` 基座（`run_prepare.py:180-184`、`run_dispatcher.py:1938-1945`）；指纹七要素（`integration_runner.py:471`，比对 1016）；`auth_references.py` 四类引用扫描；`webhook_outbox` 平台回调（`_enqueue_integration_event`）；`auth_sessions` 键 `(owner_id, alias)` 含 `url` 列；`service_aliases` 模型含 `owner_user_id / base_url / environment_id`；`GET /service-aliases`（`list_aliases:91`）无 owner 过滤（10.5 成立）。
- **前端**：`stores/auth.ts` role 回退 `is_admin` 仍在、`hasRole` 已精确匹配（`8af4b841`）、无 `can()`；`/carry-config` 路由在 `router/index.ts:83`；平台入口三处（TokensSection 平台令牌选项、IntegrationCenter 平台模式选项、IntegrationDetail 标签）；改密强制跳转前后端均为零；执行报告前端（Executions / ExecutionsList / ExecutionReportPanel / api）无任何 admin 分支，文案已按属主口径（404 兜底）。
- **令牌（W5 靶点）**：三道使用门（`services/access_token.py:208`、`integration_runner.py:961`、`routers/integration.py:308`）；`Principal` 仅 user / identity_mode / token（无 `is_platform` 需求成立）；平台令牌签发属主固定 `__platform__`（`access_tokens.py:334-335`）。
- **第五轮补核（⚪）**：`REASON_PASSWORD` 常量存在（`services/access_token.py:71`，W6 复用可行）；grep 守卫豁免理由成立（`suites.py` 确有 `m.role == "main"`，`:596` 等）；C1 后端清单文件全部存在；P7 页面与路由都在（`ServiceAliasDetail.vue`、`CarryConfig.vue`、`router/index.ts:83/261-269`）；工作台卡片 promote / demote 只作用本人（`service_profile.py:108-124`，`user_id=user.id`）；`GET /roster` 现状仅返回 id / username / display_name（`users.py:82-108`，见 G1）。

## 七、待定项现状（方案 §八，四轮复核均未推翻）

七项待定（破窗通道、发布门槛、项目定时执行、保底订阅、私有区内置凭证与直连地址、导出带凭证、系统公告归属）及阻塞关系维持原判。补充一点：待定 6（导出是否带明文凭证）因 A4（现状发布 / 复制零清理）的核实结论，收紧的必要性上升——明文凭证的扩散面比方案成文时认定的更大。

---

## 八、第五轮复核新增（4 项，均已修订 ✅）

| # | 发现 | 处置 |
|---|---|---|
| G1 | **roster 现状已合规**：方案 9.7「可以保留，但只返回名字和 id」把已满足的条件写成了待办——现状就只返回 id / username / display_name，且仅 active、排除本人与系统用户（`users.py:82-108`） | 方案 9.7 已标注「本就合规，无需改动」 |
| G2 | impl C1 表内扇出行号 `:1339/1349/1700` 未与方案 9.7 修订后的 `1337-1340/1348-1351/1699-1702` 同步（两文档自相矛盾） | 已同步 |
| G3 | 两文档头部轮次表述滞后（「第三轮」「第三、四轮」），第五轮修订后未更新 | 已统一为「三至五轮」口径 |
| G4 | U1 关闭：令牌入口实测 14 端点 / 5 文件，「15 个入口」基本吻合（差 1） | 实施 W5 验收已改写并落数 |

---

## 九、第六轮：外部评审吸收（2026-11-07）

评审对象是分模块开发方案（`authz-config-redesign-dev-plan-2026-11-06.md`），意见 5 必改 + 6 建议；经对代码逐条核实，**全部属实、全部采纳**。其中 R4（前端部分）/ R5 / R6 / R7 / R11 当轮只落了开发方案，两份上游文档的同步在第七轮补齐（见 N1–N5）。

| # | 评审发现 | 核实证据（HEAD `85f8e2d`） | 处置 |
|---|---|---|---|
| R1 | 0037 只改 `identity_mode` 不改 `visibility`，全部订阅实例会以 `made_private` 暂停 | ✅ `integration_runner.py:991-999`：闸后有 `visibility != "public" → _pause_consent_changed(made_private)`；`TaskIn` 默认 `visibility="private"`（`integration.py:248`） | 0037 第②步同步 `visibility='public'`；补「迁移后订阅实例仍能正常执行」用例 |
| R2 | 0037 未交代存量：加约束前必须先改写存量行；`__platform__` 自持实例改写后会因凭证同迁移删除而永久 `missing_credential` | ✅ `:928`（平台唯一实例 `holder_id == tpl.owner_id` 或 `PLATFORM_KIND`）、`:1027`（platform 分支 `holder = get_platform_user_id()`） | 0037 定死四步顺序（删自持实例 → 双条件改写 → 删凭证/令牌 → 加约束）；迁移测试覆盖四步 |
| R3 | 剥离三时机漏了 `suite_copy` 三入口与 share_ref 引用执行；主规则应在执行时 | ✅ `services/suite_copy.py:80` `deep_copy_suite`；引用执行无拷贝动作，剥离救不了 | 主规则：`built_in_users` 仅执行人 == 属主时生效（覆盖引用 / 订阅 / 存量公开）；剥离降为附加清理；进表 B 矩阵 |
| R4 | 「只能改密」拦了 `/auth/me`，前端判未登录、到不了改密页 | ✅ `stores/auth.ts:8-9` 注释明说 fetchMe 是登录态唯一证明 | 放行 me（带 `must_change_password` 字段）/ refresh / change-password；前端 flag 为真时停通知轮询与卡片拉取 |
| R5 | `User.role.in_(("admin","member"))` 不在守卫覆盖内；M1→C1 窗口期漏 Super Admin | ✅ `access_token.py:573`（注释还留着「09-29 更名后平台任务通知只到 admin」的同款教训）、扇出三处 `.in_` 写法；守卫原正则只匹配属性比较 | 表 A 加 `roles_with(cap)` 反查，SQL 人群选择改写；守卫正则扩三种形状（`.role ==` / `.role.in_(` / `User.role ==`） |
| R6 | W3「admin 仅公共对象可发布」规则空转（对已公共对象再发布无效果） | 成立 | 改为：admin 对他人对象**无发布权**，仅保留公共对象下架权 |
| R7 | T0.2 矩阵自证循环（从同一份表生成，证明不了表本身对） | 成立 | 加人工审定快照 `tests/authz_expected.yaml`（约 20 条关键期望），表变更必须同步改快照 |
| R8 | 临时密码交付方式要定死 | 成立（无其他交付通道） | 定死：返回给管理员一次 |
| R9 | 恢复脚本 alembic SQL vs 启动任务二选一 | 成立 | 定死：0036 内纯 SQL `UPDATE`，不 import 应用代码 |
| R10 | 0036 三件事（更名/加列/恢复）downgrade 绑定 | 成立 | 保持单迁移，迁移测试三件事分别断言 |
| R11 | `persistedIdentity` 不带 `capabilities`，刷新首帧导航跳变 | 成立 | 快照加 `capabilities`，旧字段迁移兼容 |

---

## 十、第七轮：修订传播核对（2026-11-07）

上游两份文档（方案 / 实施变更点）对照第六轮修订与开发方案逐条核对：发现 5 条只落了开发方案、3 处残留不一致，并带出 3 个新问题（N9–N11 均已对代码核实属实）；全部已在三份文档补齐。

| # | 发现 | 处置 |
|---|---|---|
| N1 | R5（`roles_with` + 守卫三种正则形状 + 窗口期漏 Super Admin）未落上游 | 补进方案 §2.3、实施 W2（表 A 行 + 守卫行） |
| N2 | R6（admin 无发布权）未落上游：实施 W3「保留的能力」仍含「发布」 | 改为仅 `visibility_unpublish`（条件 `visibility == "public"`） |
| N3 | R7（人工审定快照）未落上游：实施 W2 验收仍只写「由表生成」 | 补 `tests/authz_expected.yaml`（约 20 条关键期望） |
| N4 | R11（快照带 capabilities）未落上游：实施 W8 无此项 | 补进 W8 `stores/auth.ts` 行 |
| N5 | R4 前端部分未落上游：实施 W8 改密行没写停轮询、没写按 me 标志跳转 | 补进 W8 改密强制页行 |
| N6 | 实施 W6 验收「只能调用改密接口」与同节白名单自相矛盾——照写会把 `/auth/me` 断言成 403 | 验收改为与白名单一致（me / refresh / 改密 200，其余 403） |
| N7 | 实施 W6 验收缺主规则断言（只查拷贝产物） | 验收补「主规则：非属主执行内置凭证不生效」+「附加清理」两段 |
| N8 | 方案 §七 M1 行与实施 §五总表仍是「剥离」旧口径 | 均改为「非属主执行时不生效（主规则）＋ 跨属主拷贝时剥离（附加清理）」 |
| N9 | **新**：主规则改变 M1 引用执行行为——被分享人经 share_ref 执行原靠属主内置凭证能跑通，生效后会在被测系统认证失败，而 M1 预检仍是「告警后继续」（失败中止要到 M2a P5） | M1 预检补明确告警或拦截（「此场景依赖属主内置凭证，请绑定自己的凭证」）；suite 含引用场景同理；列入上线公告（方案 9.1、开发方案 W6） |
| N10 | **新**：0036 恢复 SQL 只改 state 会与 `revive_paused_instances` 口径不一致 | 已核实函数口径（`integration_runner.py:1620`）：`state='idle'` + `paused_reason=''`（NOT NULL 空串）+ `next_run_at=now()`，另有恢复通知；SQL 按此写全，不发通知的差异注明可接受；迁移测试断言「SQL 恢复的行 == 函数恢复的行」 |
| N11 | **新**：0037 删平台令牌后执行记录 `token_id` 随 FK 置空，看不出执行由哪枚令牌发起 | 已核实 `models/execution.py:126` `ondelete="SET NULL"`；生产无存量只影响开发库，可接受；0037 迁移说明已注 |

---

## 十一、第八轮：时机与口径复核（2026-11-07）

对剥离时机、预检告警、恢复 SQL 的口径复核；5 项全部成立、全部采纳。

| # | 发现 | 处置 |
|---|---|---|
| E1 | **「订阅时剥离 `config.users`」时机不成立**：订阅不复制场景（实例引用活的公共场景），剥离动作无处落——在订阅时剥离等于改作者的场景，而公开时机已剥离过。R3 修订从原方案三时机原样继承，未审视其与「订阅引用活场景」的矛盾。**连带**：同意指纹含 `definition.config`（`consent_fingerprint_of:471`），存量公开场景重新发布触发剥离时指纹变化，已有订阅以 `template_changed` 暂停——预期行为，与 N9 同一份上线公告 | 三份文档（方案 9.1、实施 W6、开发方案 W6）删「订阅」时机并注明不成立；指纹连锁写进 9.1 与两份 W6 的公告条目 |
| E2 | 实施 W6 缺 N9 预检告警行（又一处传播缺口）；告警条件不精确会很吵 | 实施补行（落点 `run_precheck` / `run_prepare`）；**三条件同时满足才告警**：① 执行人非属主；② `config.users` 不为空；③ 对应别名在执行人自己的认证会话里解析不到；订阅执行同理；三份文档口径同步；验收 / 测试补「任一不满足不出现」断言 |
| E3 | 开发方案 W6 清理项表残留「临时密码登录后仅改密接口可用」，与白名单矛盾（N6 同款残留） | 改为与测试项③一致（me / refresh / 改密可用、其余 403） |
| E4 | 恢复 SQL 缺 `template_id IS NOT NULL`——函数只恢复实例不动模板（`integration_runner.py:1641` 查询即有此条件），纯 SQL 不加则口径不一致 | 两份文档的 WHERE 条件补齐 |
| E5 | 方案 §2.3 末句「测试由表驱动生成」未提人工快照，与实施 W2 不齐（纯文档一致性） | 补半句挂 `tests/authz_expected.yaml` |

---

**总账**：八轮共整理 **65 项**发现——冲突 7（A）、修正 17（B）、耦合 5（S）、第四轮新增 5（F）、第五轮新增 4（G）、第六轮外部评审吸收 11（R）、第七轮修订传播核对 11（N）、第八轮时机与口径复核 5（E）；全部已修订进三份文档（方案 / 实施变更点 / 开发方案）或登记为实施注意；未复核项 3 收 1（U1 已核），余 2 项（U2 逐处归类、U3 执行视图外圈）留实施时核对。
