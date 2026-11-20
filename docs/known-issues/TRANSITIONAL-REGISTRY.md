# 已知问题与过渡态登记表

> 一期交付登记总账(2026-10-14 建档):每条写明影响、退出条件、归属。
> 来源:交付前问题清单(14 类)+ UI 走查 + 各轮复核登记项。
> 处置口径:修复即销条(移到文末「已销」);新登记条目按同表格式追加。

## A. 等待外部决策(阻塞者:用户/团队)

| # | 条目 | 影响 | 退出条件 | 归属 |
|---|---|---|---|---|
| A1 | feat/plate-s1 合入 main | 后续所有基线工作(见 B1)以 main 为准 | 用户拍板合并 | 用户 |
| A2 | GitHub Support 工单(GC 旧对象) | 含凭证旧提交仍可按 SHA 取回 | 提交工单并确认 GC(文案在仓外 D:/Gimbal/github-purge-request…md rev2) | 团队 |
| A3 | 78 处外部系统凭证轮换 | 泄漏凭证若在其他环境复用则有效 | 团队逐个确认轮换(私有环境口令已按拍板豁免) | 团队 |
| A4 | CI 从未实跑 | 本批全部改动未经 CI 验证 | `workflow_dispatch` 触发一轮全绿 | 用户(GitHub 页面) |
| A5 | 两个待裁定 known-issue | P0 候选 normalize-registry-writeback、P1 dollar-brace-backfill | 用户拍板处置口径 | 用户 |
| A6 | exists-property-hole 公开承诺文本 | 对外说明未定稿 | 用户过目 | 用户 |
| A7 | SQLite 时代本地文件 | backend/data/app.db 及 4 个 bak(磁盘,非仓库) | 确认无需回滚后归档删除 | 用户 |

## B. 有明确前置的工程项

| # | 条目 | 影响 | 退出条件 | 归属 |
|---|---|---|---|---|
| B1 | gen_m2 compat 守卫无真实基线 | 不兼容 M2 变更不会被拦(main 无 schema,恒跳过) | A1 合入后首个含 m2.schema.json 的 main 即闭合 | 合并后即闭 |
| B2 | S1.5 质量尾项池 | 快照化/原子重载/ref 多版本/路径可配置等(见 plate-design 修订十) | 合入后按依赖排期 | 后续批次 |
| B3 | 行级失败原因不入库 | 执行详情顶层 error 仅覆盖 dispatcher 级;行级原因在工件(两击可达) | execution_rows 加 run_error 列(迁移+写入+读侧) | 后续批次 |
| B4 | pydantic 无上界 | 依赖漂移风险(2.13 曾与旧代码不兼容) | 钉 `<next-major` 或锁定 | 后续批次 |
| B5 | REST 契约漂移守卫 + 错误码单源化(审计批次⑤治本;**轻量切片 2026-11-20 已落**:`gen_api_contract.py` 快照 openapi.json+error-codes.json(213 码/437 位点/35 动态)双守卫 = plate-ci 步骤 + test_api_contract) | 无意识漂移已被拦;前端 37 api 文件仍手写镜像 ~210 类型、错误码表前端零引用 | 治本全量:codegen 单源化(参照 gen_m2 三侧管线)+ 错误码表前端接入 | 后续批次 |
| B6 | C3 conftest 钉 legacy vs 生产默认 server(2026-11-20 已做死兜底直读对齐) | 28 个测试文件按 legacy 假引擎编写;出厂默认路径非默认被测路径 | 自举:FakeServerSession 对齐假 launch 覆盖面 → 钉位翻 server → 删 legacy 链 | 自举 |
| B7 | yz 认证器真实登录协议未实现(2026-11-20 已修 None-token fail-fast + 清硬编码口令) | 现形态 = 预置 token 直通;docstring 所述 POST 表单→PHPSESSID 协议缺外部系统信息 | 取得 21eline 测试环境协议确认后补实现 | 外部信息 |

## C. 结构性登记(不修,按设计)

| # | 条目 | 影响 | 退出条件 | 归属 |
|---|---|---|---|---|
| C1 | run_dispatcher ~2600 行 / 25 个百行函数 | 新功能易只接一条路径(第 3 类根源) | 重构批次(先抽「执行前置」共用段) | 后续重构 |
| C2 | jsonpath 三份实现 | 语义漂移风险 | gimbal-core 拆分 | gimbal-core |
| C3 | legacy 执行链(EXEC_CHAIN) | 测试钉 legacy,server 链覆盖在专项用例 | 自举覆盖 server 链后退役 | 自举 |
| C4 | 未声明修订场景用存储 binding(过渡形态) | C-2 闸后新增即拒;存量已 rs3 回填 | 存量清零后删过渡分支 | 已基本闭合,观察 |
| C5 | CRLF/LF 混存 | diff 噪音 | .gitattributes 统一(一次性大 diff,低峰做) | 后续批次 |
| C6 | 宽捕获 ~240 处未逐个审计 | 旁路降级无日志的漏网 | 按第 4 类排查方法扫(主链路已清) | 后续批次 |
| C7 | 主链路注释含历史叙述 | 可读性 | 注释清理批(移提交记录) | 后续批次 |
| C8 | 静态约束入口校验全量清单未建 | 晚失败(登记类) | 按第 5 类方法列清单核 | 后续批次 |
| C9 | 状态迁移写点全量并发审计未做 | 理论竞态面(已知点已 CAS) | 按第 7 类方法扫 | 后续批次 |
| C10 | account_fields 明文存储(审计 TOK-08b) | 用户存秘密则裸存;F6 拍板:自定义字段明文非密、只经 ${slot.X.field} 消费 | 若收紧:敏感键逐值 fernet(写入加密/消费解密),需先拍板 | 按设计登记 |
| C11 | md5sign 遗留签名器(审计 TOK-08d) | md5(token+timestamp) 弱签名 | **被测系统协议仿真,不能单方面改**(契约与退役插件逐字节一致,特征化用例钉死);推动场景声明式切 standard.bearer/basic | 随 legacy 链退役 |
| C12 | 手配自助建条目(凭证治理 §3.3 方案 A,2026-11-20 落) | 普通用户随场景保存可建 username-ref 自用条目 —— 此前条目创建属 alias.write 能力面(W7 导入门同款);范围窄:仅 username-ref 自用形态、base_service 须落主档既有服务(未知系统 422)、目录/部署仍属 admin | 用户未否决视为维持;翻案退路 = 删 `auth_drafts.materialize` 条目创建段(闸与冲突码不动) | 待用户确认 |

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
| D10 | 自举必须覆盖的路径登记 | 测试≠生产路径 | server 链/空库启动/CLI 退出码/suite 执行(前三已各有测试,补 suite 端到端) | 自举 |

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
