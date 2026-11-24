# 已知问题与过渡态登记表

> 一期交付登记总账(2026-10-14 建档):每条写明影响、退出条件、归属。
> 来源:交付前问题清单(14 类)+ UI 走查 + 各轮复核登记项。
> 处置口径:修复即销条(移到文末「已销」);新登记条目按同表格式追加。
> 收尾排布(2026-11-23):A-E 各条批次顺序、决策点与暂缓项见
> `docs/wrapup-plan-20261123.md`。

## A. 等待外部决策(阻塞者:用户/团队)

| # | 条目 | 影响 | 退出条件 | 归属 |
|---|---|---|---|---|
| A1 | feat/plate-s1 合入 main | 后续所有基线工作(见 B1)以 main 为准 | 用户拍板合并 | **✅ 2026-11-23 已销**:用户拍板「推送 + 快进 main」,origin/main 快进 2c70a12b..b44e7874 = feat/service-registry 顶端,严格包含 plate-s1(merge-base 即其顶端、plate-s1 独有提交 0),不必单独合 |
| A2 | GitHub Support 工单(GC 旧对象) | 含凭证旧提交仍可按 SHA 取回 | 提交工单并确认 GC(文案在仓外 D:/Gimbal/github-purge-request…md rev2) | 团队 |
| A3 | 78 处外部系统凭证轮换 | 泄漏凭证若在其他环境复用则有效 | 团队逐个确认轮换(私有环境口令已按拍板豁免) | 团队 |
| A4 | CI 从未实跑 | 本批全部改动未经 CI 验证 | `workflow_dispatch` 触发一轮全绿 | **🟡 2026-11-23 处理中**:plate-ci 接通后连钉 7 处断点(gen_m2 误删 / 加载已退役脚本的死测试 / json2ts 探活行必退 1 / pytest-xdist 未进 lock / 增量升级门 21 项漂移 → 迁移 0066 / 契约守卫干净检出导入即崩 / 测试辅助 commit-tree 漏传 git 身份),已修并于 Python 3.12 + lock 同构环境在 Windows 与 Linux 双平台 gate 全量复现(见 progress「CI 交接处理」);main 实跑全绿后销条。*(2026-11-24 证据注记:GitHub plate-ci run#4 于 main 顶端 `0ef83781` **push 触发全绿**(frontend+gate 双 job,2026-11-23 23:44 CST)—— 全绿 run 已实际存在;字面退出条件「workflow_dispatch 触发」未跑(本机无 gh 凭证),销条待一次 dispatch 或用户追认 push-run 即可,无需再改代码。另:`fix/ci-main-green` 顶端(前端路由修复 `566b1f0e` + 本批 6 提交)尚未有 CI run,随下次 PR/push 兑现)*。*(2026-11-24 收尾轮再注:`f25aacc8` 与 `e2819115` 两轮 push 均红,红面 = `workbench.assembly.test.ts:103` 在 CI 慢机超默认 5s 整测超时(vitest 5 升级后的新环境面,**非**原批 7 断点回归;本地 4 连全绿测不出);已修于 `fix/core-wrapup`(assembly/feature-cards 两测试文件补注册表 loader 预热 + 文件级 testTimeout 15s);销条条件不变 —— 本分支合入后的下一轮 push 全绿,或一次 dispatch)* *(2026-11-25 推送注记(勘误):批 G-J 共 16 提交已推 ed131922..dbaa989c,但分支 push **不在触发面**(plate-ci on = PR/main-push/dispatch)—— 分支 0 run。销条证据 = PR 触发的 全量 run(修复已在分支顶端 4efcc72c,红面 workbench.assembly 慢机超时应消)或一次 dispatch;main 顶部 e2819115 仍红)* |
| A5 | 两个待裁定 known-issue | P0 候选 normalize-registry-writeback、P1 dollar-brace-backfill | 用户拍板处置口径 | **✅ 2026-11-24 已销**:用户拍板两项裁定并同日落盘 —— ①normalize-registry-writeback(E)= **隔离区+后端闸**(`unrecognized` 隔离键原样写回 + `validate_registry_shape` 写侧闸 422,提交 `40f37b16`);②dollar-brace-backfill(G)= **改文档不改行为**(「null 是合法值」,docstring/编辑器注记对齐,提交 `eca14bdc`);裁定行+修复记录入各自 known-issue,README 总表行同步。重开条件不变(各自 §4) |
| A6 | exists-property-hole 公开承诺文本 | 对外说明未定稿 | 用户过目 | 用户 |
| A7 | SQLite 时代本地文件 | backend/data/app.db 及 4 个 bak(磁盘,非仓库) | 确认无需回滚后归档删除 | 用户 |

## B. 有明确前置的工程项

| # | 条目 | 影响 | 退出条件 | 归属 |
|---|---|---|---|---|
| B1 | gen_m2 compat 守卫无真实基线 | 不兼容 M2 变更不会被拦(main 无 schema,恒跳过) | A1 合入后首个含 m2.schema.json 的 main 即闭合 | **✅ 2026-11-23 已闭**:main(b44e7874)含 m2.schema.json,`compat --base origin/main` 首次以真实基线通过。前置补充:生成器 `scripts/gen_m2.py` 在 90e7918e 退役批次中被误删(在用工具,非一次性脚本 —— CI 两步 + tests/plate/test_m2_step2 + routes_grammar 运行期文案 + 生成物头注均依赖),同日 CI 交接处理恢复(与退役前逐字节同) |
| B2 | S1.5 质量尾项池 | 快照化/原子重载/ref 多版本/路径可配置等(见 plate-design 修订十) | 合入后按依赖排期 | **✅ 2026-11-24 尾项收口(批 A/E)**:量级勘误 —— 四项大头已在 feat/plate-s1 落地(RS0-RS3),余尾项清零:④ 路径可配置 = cmd_reload 写死仓库根 systems/ 改 load_registry() 无参(批 A);② 原子重载 = POST /api/admin/reload 触达运行服务(构建-成功才换,失败 503 reload_failed 旧快照原样服务;嵌入模式 409;admin token 门 fail-closed —— PLATE_ADMIN_TOKEN 未配置即 403 reload_disabled,配置后要求 X-Admin-Token 常量时比对)+ G5 working@<sha7> 标识(批 E,门为批 J 补);③ REF_REQUIRED = 成文销问(用户拍板维持「调用方保证」,全仓零发送方;plate-version-model §4.2 注记落档);① 快照化 = 修订快照缓存 + working 伪快照已在 plate-s1,无余量 |
| B3 | 行级失败原因不入库 | 执行详情顶层 error 仅覆盖 dispatcher 级;行级原因在工件(两击可达) | execution_rows 加 run_error 列(迁移+写入+读侧) | **✅ 2026-11-23 已落**:迁移 0065(live 已升;*11-24 勘误:当时 live 实为 0064 未动,实际升级发生在 11-24 部署轮 0064→0066 连升,带 pre-dump*)+ 模型/RowState/终态投影(引擎 runError 优先、派发层 error 次之,[:2000] 防超长)+ 行页 ExecutionRowOut.runError + 报告 groups.runError(前端行头呈现)+ graph 恢复/逐单元行补键;roundtrip + 引擎失败×派发异常双路 e2e 钉死 |
| B4 | pydantic 无上界 | 依赖漂移风险(2.13 曾与旧代码不兼容) | 钉 `<next-major` 或锁定 | **✅ 实质已闭合未销条**:`8d2a4164`(2026-10-15,登记次日)已钉 `pydantic>=2.6,<3` + `pydantic-settings>=2.0,<3`,requirements.lock 锁 2.14.1(当前全量绿);2026-11-23 复核销条 |
| B5 | REST 契约漂移守卫 + 错误码单源化(审计批次⑤治本;**轻量切片 2026-11-20 已落**:`gen_api_contract.py` 快照 openapi.json+error-codes.json(213 码/437 位点/35 动态)双守卫 = plate-ci 步骤 + test_api_contract;**治本切片 1 2026-11-23 已落**:`gen_frontend_contract.py` 生成前端 `api/generated/openapi.ts`(219 schema 直译,Any→unknown)+ `errorCodes.ts`(227 码 as const + `ApiErrorCode` union);`contractGuard.ts` 编译期对账(手写⊆生成 assignability,executions 域示范 5 断言;后端 Any 字段致生成宽于手写,故守卫取方向「手写声明的形状必须存在于生成形状」);`ApiError.hasCode(ApiErrorCode)` typed 判等(AdaptationBatchDetail 示范,typo 编译期红已亲验);漂移守卫 = `test_api_contract.py::test_frontend_contract_no_drift` + 负例亲验) | 无意识漂移已被拦;错误码前端接入面 = 渐进(hasCode 可用,字面量判等未全量替换);**37 api 文件手写类型迁移未动**(方向:facade re-export 生成类型/或守卫逐域扩断言) | 切片 2 已落(2026-11-24 批 D):suites 域 5 response 形状入 contractGuard(SuiteRunItem/ValidateOut/RevConflict = 前端投影无契约 schema 不适用;latestRun Any 面 Omit 摘除)+ hasCode 迁移 7 点位(rev_conflict×2/name_taken/导入三码/auth_expired 投影位改旗标);扫描器补元组赋值形态(QueryViewError/ImportRejected)—— sut_auth_expired/scenario_id_exists/alias_name_taken/mapping_stale/query_credential_required/service_url_required 六码补进契约;顺手修三处真实链死链(suiteErrDetail 摸 e.response 恒 null,publish_required 死分支改挂现行 suite_member_not_public)。切片 3 已落(2026-11-24 批 I):projects/users/auth_sessions 三域 6 断言(ProjectOut/MemberOut/UserPublic/UserListOut/AuthReferencesOut/AuthListOut),CONTRACT_GUARD_DOMAINS 五域;publishUnpublished 死字段两面退役。余:其余域逐批扩断言与 37 api 文件手写类型迁移(常轨渐进) | 后续批次 |
| B6 | C3 conftest 钉 legacy vs 生产默认 server(2026-11-20 已做死兜底直读对齐) | 28 个测试文件按 legacy 假引擎编写;出厂默认路径非默认被测路径 | 自举:FakeServerSession 对齐假 launch 覆盖面 → 钉位翻 server → 删 legacy 链 | **② 已落(2026-11-23)**:conftest 钉位翻 server + `ShimServerSession` 垫片(run_case 以 legacy 同款 kwargs 委托 `gimbal_launcher.launch` —— 既有 fake 引擎缝零改动续用,实际迁移仅 5 处 graph/suite fake 双绑 `gd.launch`+`gl.launch`;垫片 slot 读写吞掉保持 server_slot=None 工件路由同形);全量 2188+2 绿。**③ 平台侧已落(2026-11-23)**:生产面六处清链(dispatcher 链分支与取消文件通道/graph_dispatch legacy 分支/suites 链取值/executions 读侧口径/config 键)+ gimbal_launcher 剥壳(launch/build_argv/parse_run_result 删,保留 LaunchResult+spawn 原语供 server 会话)+ 测试假引擎缝统一迁 tests/_fake_engine.launch(23 文件)+ 双链等价用例裁单臂 + 真引擎 e2e(r6/对账五形态/契约/debug)转真 ServerSession(conftest real_engine_session)+ PlateMock.m2 可配(真引擎代际门略过);launcher 专属测试三文件随 launch() 删除。全量 2161+2 绿。**md5sign 不随本批**(见 C11 勘误) |
| B7 | yz 认证器真实登录协议未实现(2026-11-20 已修 None-token fail-fast + 清硬编码口令) | 现形态 = 预置 token 直通;docstring 所述 POST 表单→PHPSESSID 协议缺外部系统信息 | 取得 21eline 测试环境协议确认后补实现 | 外部信息 |

## C. 结构性登记(不修,按设计)

| # | 条目 | 影响 | 退出条件 | 归属 |
|---|---|---|---|---|
| C1 | run_dispatcher ~2600 行 / 25 个百行函数 | 新功能易只接一条路径(第 3 类根源) | 重构批次(先抽「执行前置」共用段) | **切片 1 已落(2026-11-23)**:执行前置四缝抽离(`_fanout_auth_preflight` 鉴权预检/`_persist_run_telemetry` 台账写/`_fanout_pool_scaffold` 池脚手架/`_drain_and_finalize` §7 收口序单点)+ `_fanout` 过时双链 docstring 清账;**百行函数 25→5**(dispatch_target 652/_fanout 573/_fanout_graph 403/_row 293/compute_run_fanout 107,余量后续切片分批)。**切片 2 已落(2026-11-23)**:dispatch_target 652→161(主体成为按序流水线),14 缝抽离 —— 校验三(`_reject_unsupported_run_options`/`_validate_step_to`/`_validate_debug_request`)、取用七(exec_cfg/绑定/env 标签链+告警/fanout/场景上下文/carry/凭证池/取用圈定)、门禁三(脱敏/auth_aliases 含 graph 全图闸/行级 @slot)、装配三(`_dispatch_config_json`/`_dispatch_job_payload`/`_persist_dispatch_execution` 建行+幂等单写点,clientRef 预查与回查同条件去重);抽缝不改语义(test_adhoc_run 对拍钉住),ruff 净 -1(顺手消基线 `_eq` 重复导入)。dispatch_target 余 161 行 = docstring + 按序流水线,不为 <100 指标强拆。**切片 3 已落(2026-11-23)**:_fanout_graph 403→161,七缝 —— 恢复预检/收口两缝(at-most-once `_graph_prior_event_count`/`_graph_recover_failed`)、取消装置闭包群收敛为 `_GraphCancelCtl` 类(能力位/下发重试/teardown 单点)、B-1 台账三件套 `_persist_graph_semantics`、事件投影 `_graph_event_projection`、取消收口判定 `_graph_cancel_verdict`、行装配+落库 `_graph_result_rows`/`_persist_graph_rows`;graph 取消域 51 测试对拍钉住(抽缝漏改的 on_session 悬引用被该域当场钉出即修)。**切片 4 已落(2026-11-23)**:`_fanout._row` 嵌套闭包 293→138(_fanout 本体 573→418),七缝 —— 派发头 `_row_dispatch_head`(组合 + case 目录 + 日志行)、convert memo `_row_convert_cached`(P6)、m2_hash 一次回填 `_record_m2_hash_once`(W21)、行事件投影 `_row_event_projection`(P2-04/B3 行归属)、终态推导 `_row_status_from_result`(事件投影 > exit 判定)、registry+DB 收口 `_row_settle_terminal`(T7-Q1/M6/B3)、计数+单 case outputs `_row_count_and_outputs`(P2-4);行任务体只保留编排序。cases 域对拍 91+67 全绿;ruff 画像与基线一致。同批勘误:全量验证此前误用 `-o addopts=""` 关掉了 pyproject 缺省的 xdist `-n auto` 并行(2026-11-21 提速项)—— 单进程 ~18min,缺省并行 **141s**(16 核),后续全量走缺省参数。**切片 5(收口)已落(2026-11-23)**:_fanout 418→389(断点恢复读 `_load_done_rows` + registry 初始化 `_init_row_states` 两缝;gather/收尾序是 §7 不变量本体,保持内联);xdist 满载暴露一例负载敏感测试(composer convert_per_row 固定 2.5s 轮询窗 → 放宽 10s,全库唯一同款)。**✅ 2026-11-23 C1 销问立桩**:五切片全落,大函数 652/573/403/293 → 161/389/161/138,余者均为流水线/内聚终态(dispatch_target 161 按序流水线/_fanout 389 池序+编排/_fanout_graph 161/嵌套 _row 138 编排序/compute_run_fanout 107 算法体)—— 再拆只能凑指标,反伤可读性,终态立桩。新执行面特性接 28 个具名缝,不平铺进主体 |
| C2 | jsonpath 三份实现 | 语义漂移风险 | gimbal-core 拆分 | gimbal-core |
| C3 | legacy 执行链(EXEC_CHAIN) | 测试钉 legacy,server 链覆盖在专项用例 | 自举覆盖 server 链后退役 | **✅ 2026-11-23 已销(B6③)**:legacy 生产链整体删除(dispatcher/graph/suites/EXEC_CHAIN 键/取消文件通道/CLI 逐 case 调用),server 为唯一链且默认被测;台账 chain 键存量 legacy 值仅历史可读 |
| C4 | 未声明修订场景用存储 binding(过渡形态) | C-2 闸后新增即拒;存量已 rs3 回填 | 存量清零后删过渡分支 | 已基本闭合,观察 |
| C5 | CRLF/LF 混存 | diff 噪音 | .gitattributes 统一(一次性大 diff,低峰做) | **✅ 2026-11-24 已落(批 A)**:量级勘误 —— D5 attrs 已覆盖大面,库内真实 CRLF 仅 9 文件,renormalize 一次归一(含两个 CRLF .sh 的 CI 活性风险消除);.gitattributes 补钉缺口扩展名(*.sh/css/html/php/js/mjs/ini/txt/csv/in/lock/example/npmrc/sql + dotfile);新增 .editorconfig 编辑器层兜底;磁盘态 checkout-index 刷新(670 w/crlf→LF,零提交面)。「大 diff 低峰窗」前提勘误:提交面极小,不等窗口 |
| C6 | 宽捕获 ~240 处未逐个审计 | 旁路降级无日志的漏网 | 按第 4 类排查方法扫(主链路已清) | **dispatcher 域已扫(2026-11-23,58 处分类)**:真静默降级 8 处补 warning(env 告警/恢复行留档×2/cancel 结论留档/断点查询/关池×3/事件批冲刷回填);刻意静默 9 处保留(自带注释:取消轮询瞬态/无循环兜底/CancelledError 回填/清理扫描跳过)。余域渐进。**余域第一轮已扫(2026-11-24 批 B)**:routers 全域 + integration_runner/webhook_outbox/access_token/通知与预检降级面 22 处补 logger.warning(「降级必须可见」);「可见性由载荷/返回值/收口结果承载」判例 14 条入 grep 守卫白名单;新守卫 test_grep_guard_wide_except.py 双断言冻结(新宽捕获无 logger 即红)。留观察:plate_client(上游承载)/main.py 启动面/gimbal_server_session close-pass(判例在档)。**引擎树已扫(2026-11-24 批 G)**:src/gimbal 48 文件 122 处全量闭环 —— 补 warning 15(reporter 五旁路/输出快照/事件序列化/调度标注/插件入口)、刻意静默保留 18(8 补注释)、原达标 84;utils/jsonpath.py 镜像豁免 |
| C7 | 主链路注释含历史叙述 | 可读性 | 注释清理批(移提交记录) | **第一切片已落(2026-11-24 批 C)**:ADR-0003 先行补录计划前退场 12 行(13-24,五要素 pickaxe 考据)→ 六文件(run_dispatcher/graph_dispatch/run_prepare/core/config/routers-executions/scenario_store)注释改现在时 —— 日期戳/墓碑/任务编号注记清除(run_dispatcher 日期/勘误/「此前」grep 清零;设计文档名日期是活锚保留)。**第二切片已落(2026-11-24 批 H)**:ADR #25 补录(运行弹窗 prefix/mergePolicy/preset/auths chips,770eea04)→ 后端余域 ≈200 处 + 前端 ≈180 处(87+41+6 文件)改现在时,墓碑引 ADR #13-#25;覆盖外 ≈105 行原样保留列档(D1 数据集路由簇/服务级引用簇/authz C1 簇等,重开 = 各自立项轮)。存疑保留 4 处 —— 其中 user.py 角色取值疑点已勘误(批 J:docstring 改 ``user | admin | super_admin`` 与 0036/列注释对齐),余 3 处见 progress |
| C8 | 静态约束入口校验全量清单未建 | 晚失败(登记类) | 按第 5 类方法列清单核 | **✅ 2026-11-23 已扫**(docs/static-constraint-audit-20261123.md,新口径:信任边界×静态约束×四档判定,三面全量清单化):边界即校验为主旋律,晚失败面高度集中且多为文档化架构决策(plate/执行器为结构权威);**真缺口 4 处本批修复** —— runs/preview serviceBindings 形态 500→422、ck_scope_exactly_one 模型/迁移漂移对齐、REGISTRY_ONLY_* 拼错静默按 off→Literal 启动拒(高危)、死键×4 删除(plugins 三键 + B6③ 遗留 CANCEL_GRACE);挂账 J 区三项(convert 信封/队列配方版本化/share_refs 无模型) |
| C9 | 状态迁移写点全量并发审计未做 | 理论竞态面(已知点已 CAS) | 按第 7 类方法扫 | **✅ 2026-11-23 已扫**(docs/concurrency-write-audit-20261123.md,12 写点清单化):唯一真竞态 promotions 裁决 TOCTOU 本批修复(行锁串行化,grants 双写面收口);revoke_grants 粒度维持 E 区挂账 |
| C10 | account_fields 明文存储(审计 TOK-08b) | 用户存秘密则裸存;F6 拍板:自定义字段明文非密、只经 ${slot.X.field} 消费 | ~~若收紧:敏感键逐值 fernet(写入加密/消费解密),需先拍板~~ **✅ 2026-11-23 销问:维持明文非密,收紧不立项**(重开条件 = 出现实际敏感键使用证据;收尾排布批次 0-4) | 按设计登记(已销问) |
| C11 | md5sign 遗留签名器(审计 TOK-08d) | md5(token+timestamp) 弱签名 | **被测系统协议仿真,不能单方面改**(契约与退役插件逐字节一致,特征化用例钉死);推动场景声明式切 standard.bearer/basic | **勘误(2026-11-23,B6③ 落地时核实)**:md5sign 是 plate 方言 token_type 契约项(_m2/dialect/selfdescribe/m2.schema.json/compiler 校验/签名分派),与平台执行链**零耦合**——平台 legacy 链删除不影响其可达性;真退役 = 方言破坏性变更,m2.schema 契约面再生成依赖 A1 合并后的 main 基线(B1),另批立项(随 D10 真引擎 suite e2e 一并)。**✅ 2026-11-24 拍板保持(销问)**:md5sign = 被测系统协议契约项,与真实 SUT(fin = md5(token+timestamp) 头,15+ 端点 auth: custom 依赖缺省签名器)强耦合,单方面退役断真实集成认证 —— 按设计保持,不立项退役。重开条件 = 真实 SUT 协议迁移确认(外部信息,同 B7 族;届时走「场景声明式切 standard.bearer/basic」→ 方言代际递增全链)。D10 真引擎 suite e2e 已落(2026-11-23),gen_m2 生成器已在位 |
| C12 | 手配自助建条目(凭证治理 §3.3 方案 A,2026-11-20 落) | 普通用户随场景保存可建 username-ref 自用条目 —— 此前条目创建属 alias.write 能力面(W7 导入门同款);范围窄:仅 username-ref 自用形态、base_service 须落主档既有服务(未知系统 422)、目录/部署仍属 admin | 用户未否决视为维持;翻案退路 = 删 `auth_drafts.materialize` 条目创建段(闸与冲突码不动) | **✅ 2026-11-23 追认维持**(待实现批次处理时确认;翻案退路继续在档) |

## D. UI/UX 登记(一期后第一项:信息架构收敛)

| # | 条目 | 影响 | 退出条件 | 归属 |
|---|---|---|---|---|
| D1 | 信息架构收敛为四域(编排/执行/服务与凭证/管理) | 凭证 3 处、服务 4 处、执行入口 4 个 | IA 重构批 | 一期后 |
| D2 | 编排器单页化 | 四步向导重心倒置 | 同上 | 一期后 |
| D3 | 断点手写内部语法/适配页手输 ID | 高门槛操作 | 选择器化 | 一期后 |
| D4 | 占位符像已填值 / 中英混排 / 内部名与设计编号外露 | 新人误导 | 术语表+文案批 | 一期后 |
| D5 | 页面内设计说明文字 | 开发视角泄漏 | 移文档/帮助浮层 | 一期后 |
| D6 | 预填 5 变量触发「死数据」保存警告 | 自造噪音 | 预填变量带 used 标记或警告豁免 | 后续批次 |
| D7 | 未用系统适配页 250 条漂移 6000px | 页面不可用 | 空场景系统折叠 | 后续批次 |
| D8 | 常量池版式居中窄版与其他页不一致 | 视觉不齐 | IA 批顺带 | 一期后 |
| D9 | GET 步骤「query 参数」标签在契约未加载时回落 body 字样 | 瞬时误导(契约加载后正确) | stepMethod 响应式化 | 后续批次 |
| D10 | 自举必须覆盖的路径登记 | 测试≠生产路径 | server 链/空库启动/CLI 退出码/suite 执行(前三已各有测试,补 suite 端到端) | **✅ 2026-11-23 已销**:最后一项补齐 —— `tests/test_suite_real_engine_e2e.py`:编排模式(chain,两单元)经**真 gimbal 引擎**完整执行(composition 落库 → suite_graph 入队 → _fanout_graph → 逐单元 convert → 执行器 server 会话 spawn + SSE),断言 done / kind=suite_graph / 两单元 passed / 桩被测系统各命中一次 / 行台账(图行 + ref 标签单元行)/ 事件(run.finished×1 + scenario.end×2)/ 台账 chain=server。此前编排链只有假引擎覆盖,图物化产物与真执行器方言是否咬合无证据 —— 首跑即过(4/4 稳定,xdist 满载亦绿)。四路径自此全部有真形态测试 |
| D11 | 日面灰字对比度(批次 4 夜间修复时的新观察) | tertiary `#94a3b8` 白底 2.56:1、暖次底 2.31:1(连 large-text 3:1 都不达) | 日面阶梯整体下移一档 | **✅ 2026-11-23 已修**:单改三级不可行 —— 次级 `#64748b` 自己在暖次底 #f5f3ee 也仅 4.29:1,三级达 AA 就不可能比次级浅,单改会把层级压平;故两级同移:secondary → `#526276`(白/米白/暖次底 6.24/5.96/5.62),tertiary → `#607086`(5.05/4.83/4.55,三面全 AA),与夜间阶梯(#9b9b9b/#909090)同构。theme.css + composer.css 两套令牌同改(118 + 164 处使用面);NotificationBell 相对时间直写 `text-slate-400` → `slate-500`(浅底面板内唯一漏网)。另 4 处 `text-slate-400` 在深色外壳图标上(≈7:1),非问题面 |

## E. 挂账观察(无行动项)

- 判例降级可观测性 P2 ×3、catalog 未测 P2、步骤计数口径 P2、模板替换 P2
  (docs/known-issues/ 各档,重开条件在档);
- 测试环境域名硬编码认证器(私有环境拍板豁免,转公开前必须处理);
- 修订台账 working 声明显示「不一致」提示(then=null vs now=working 的
  语义歧义,低频观感问题);
- TOK-07 写面闸只拦新写(2026-11-20 review 登记):存量跨基础服务
  exec-config 行在被编辑前运行时照常生效(precheck 只拦不存在);
  风险面 = 配置属主自用,如需收口:一次性数据清查或运行时补同基校验;
- adhoc/graph 缺槽闸把「账户歧义」并入「未登记」文案(review P2-6
  登记;场景链硬门是 identity_missing/account_ambiguous 分码的);
- 方案绑定「名不在绑定者池 → 告警不阻断」未实施(2026-11-20 阶段 2c
  登记):run_schemes 保存仅硬 422 存在性/同基校验,响应无 warnings
  载体;解析面取不到凭证由派发 auth_aliases_missing 409 / 预检
  account_missing 硬门兜底 —— 补告警需新立载体(增量契约面),缓议;
- ~~声明侧同 base 闸未实施~~ **✅ 已销(2026-11-21 阶段 3a)**:
  `auth_ref_scan.step_auth_refs`(逐步骤 `${auth.*}` + `call.user`)+
  `service_aliases.same_base_violations`(base 口径同
  validate_binding_aliases);enforce 422 `identity_base_mismatch` /
  audit `X-Identity-Base-Warnings` 独立头 / 导入 `identityBaseWarnings`
  键(契约 216 码)。边界:未登记名归存在闸;setup/teardown 无步骤
  锚点不比对(其存在性仍走存在闸);
- **revoke_grants 粒度:按 source_promotion_id 删整行,多 promotion
  共享同条目时过度删除**(2026-11-21 阶段 4 评审 P3 登记):条目 X 经
  promotion A 授权进项目后,另一 promotion B 的场景也引用 X(B 落池
  时幂等跳过,授权行 source 仍 = A)—— 此时若按 B 回滚,整行删除 =
  A 的授权连带被撤。现状态机 approve 终态、reject/withdraw 均在
  pending 态(无授权可删),不可达,``revoke_grants`` docstring 自认
  兜底;**扩展「撤销已批准」前须先修**:按该 promotion 申请时刻的
  analyze 引用条目集 ∩ 自己落的行删,且共享行保留(改挂后续
  promotion 溯源);
- ImportRejected 错误码不在契约提取面(既有缺口:tuple 赋值形态不被
  `_discover_coded_exceptions` 识别,导入侧码仅以 dynamic 位点
  `scenario_import.py:32` 兜底;阶段 0 新码 identity_not_registered
  已以路由侧形态入快照,2026-11-20 登记)。

## 已销(本批,2026-10-14)

- A-1 UI 新建场景无法执行:三根因(tester_a 视图键泄漏/版本声明不落库/
  binding 剥离)全部收口,端到端浏览器验收通过(执行 #226);
- B-3 失败不可诊断:顶层 error + 首屏 Alert + 行状态人话映射;
- A-3 psycopg 依赖声明;C 组布局五项(toast/面包屑/右栏/GET 标签/侧边栏);
- 第 10 类回滚演练;第 13 类交接四件套(本表+概念地图+贡献规范+runbook);
- SQLite 残留注释清尾(5f39bf5f)。
