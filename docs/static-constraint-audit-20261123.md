# 静态约束入口校验审计(C8)· 2026-11-23

> 登记册 C8:「静态约束入口校验全量清单未建 | 晚失败(登记类) |
> 按第 5 类方法列清单核」。原「第 5 类」方法论源(一期 14 类问题
> 清单)未存档 —— 本批以**新口径**重定义约束面后全量清单化,
> 发现项随批处置。审计基线 = feat/service-registry @ 本批工作树。

## 口径

- **静态约束** = 编码期可声明、不依赖运行时数据的数据形状/值域/关系约束;
- **入口** = 数据跨越信任边界的点:REST 请求体、webhook 入站、令牌
  调用、DB 队列配方回放、plate/引擎响应、导入文件、CLI/server 输入、
  env 配置、DB 列;
- **判定四档**:边界即校验(fail-fast 拒)/ 晚校验(深处显式报错)/
  防御兜底(.get 容错,不误不拒)/ 无校验(裸假设);
- 处置原则:只修「无校验 + 后果不可自愈」的窄面;防御兜底为主链
  设计选择的登记维持。

## 面 1:REST 请求入口(45 路由 / ~126 写端点)

标量/长度/格式约束几乎全部在 pydantic 边界 422 即拦
(`schemas/` 集中建模 + 路由内联 BaseModel,名字/长度/pattern/
validator 纪律良好);名字唯一性单源 `routers/_name_checks.py`。
四个手写 dict 面(scenario_import / runs-preview / user_preferences /
report_definitions)均 fail-fast(413/422)。

**自由 dict 逃逸点追踪**(类型为 dict/Any、内容不经 pydantic 的
字段,19 处):

| 逃逸点 | 内容约束实施处 | 判定 |
|---|---|---|
| ScenarioDraft.definition | plate /convert 唯一权威(保存链不调 convert);写时闸:meta.plate 声明/明文凭证 422/param 槽位 | 晚校验(**设计取舍**) |
| RunRequest.steps(adhoc) | check_structure + check_addresses + dry_run_convert,派发前完成 | 边界即校验 |
| RunRequest.params | validate_inbound_params 五道闸(路由层) | 边界即校验 |
| RunRequest.graph | 形状 pydantic 拦;语义在 materialize_graph(worker 段) | 形状即拦,语义晚校验 |
| suite modeConfig | _validate_composition 结构层 422;变量级(悬空/歧义/成环)推迟执行器编译(docstring 明示) | 部分即拦,变量级晚校验 |
| DataSet.rows | data_set_store undeclared_var/slot 422 | 边界即校验 |
| report definition 四件套 | _m2.ReportDefinition extra=forbid 422 | 边界即校验 |
| PrefIn.value | 路由白名单 _MODELS + model_validate + 体积护栏 | 边界即校验 |
| GroupIn.filters | 仅体积护栏(注释声明不透明 JSON) | 无内容校验(有意) |
| environments lines | _validate_lines;plate 不可达跳过(执行期门仍在) | 有条件即拦 |
| assertion_registry / ui | 无入口校验,消费侧 .get | 无校验 + defensive |
| account_fields | 无入口校验,run_materialize .get(C10 明文非密已销问) | 无校验 + defensive |
| carry bindings/defaults 键 | 无校验,消费 defensive | 无校验 + defensive |
| adaptations payload | apply 时 adaptation_ops 物化(defensive) | 晚校验 + defensive |
| constants value/spec | model_validator 互斥/原语 422 | 边界即校验 |
| DebugCommand.value | 形状成对红线 422;值运行期生效(交互调试设计) | 形状即拦 |
| RunScheme.options | scheme_store.normalized 整形,dispatch 段消费 | 晚校验 |
| resolve-paths body sample | plate 权威(代理 422) | 边界外置 |
| auth_drafts(Orchestration) | ≤16 + store 物化 422/409 | 边界即校验 |

## 面 2:非 REST 信任边界

| 边界 | 约束 | 判定 |
|---|---|---|
| webhook 入站 | Bearer 令牌 hash 401 链(吊销/失效/到期/属主);入站即 pydantic RunRequest;配方/adhoc 禁令 422;范围闸 403 在建执行行前;clientRef 幂等预查 + 0056 部分唯一索引竞态兜底 | 边界即拦(无 HMAC,依赖令牌保密本身) |
| access token 调用面 | authenticate 401 fail-fast;check_scope 级行级联消失即失效;范围收紧后的运行期 #6 复核(注释自认的晚校验窗口);回调白名单空白名单=全拒(fail-closed) | 边界即拦 + 一处文档化晚校验 |
| DB 队列配方(job payload) | 写入单点 _dispatch_job_payload;解包缺键 → KeyError → 执行 failed 收口;**旧配方缺键全部语义缺省**(skip_carry=False 等,注释明示) | 自产自销 + 跨版本回放(见挂账 J-2) |
| plate convert 回包 | 信封 ok 校验;**converted 缺失 → `get("converted") or {}` 全链静默空**(run_dispatcher/_row_convert_cached、integration_runner 同款);m2 缺失仅台账跳过 | 防御兜底(见挂账 J-1) |
| 引擎 SSE 输出 | 帧解析防御(JSON 失败降级 _unparsed 事件);无 run.finished 显式 RuntimeError;事件字段全 .get 柔取,attempts 缺省回退 | 防御兜底(台账面,维持) |
| settings/env | DATABASE_URL/FERNET/JWT 缺失启动拒(非静默);REGISTRY_ONLY_* 本批 Literal 化;死键本批删 | 本批修复 ×2(见处置) |

## 面 3:持久层与写档

- **DB 硬约束在位**(边界即校验):token kind CHECK、账户属主 XOR
  CHECK + NULLS NOT DISTINCT 唯一、client_ref 双 partial unique、
  行/步/事件 seq 唯一、suites 成员复合 PK + 同区触发器(0042)、
  公共项目 partial unique、meta 投影 STORED 生成列(写漂移物理不可能)。
- **status 值域无 DB CHECK**(Execution/Job/Row/WebhookDelivery/
  IntegrationTask 状态族全自由 str):全仓一贯口径 —— 服务层常量单源
  (ActivityEvent/User.role 注释显式声明「DB 不设 CHECK」)。
  **维持口径**:新写入点必须走常量族,绕过 ORM 的写自担。
- **ck_scope_exactly_one 模型/迁移漂移**(只活在 0033,模型侧零
  表达)→ **本批修复对齐**。
- 场景 definition 落库无本地结构闸(POST/PUT 不调 convert;导入链是
  例外,land 内强制 convert 422)→ 与面 1 同一设计取舍,维持。
- 引擎 CLI/server:normalize_input 收口(2026-11-23 批次 4)、
  **RunUnion(m2.schema 生成)校验前移到 dry-run 前** = 方言契约
  边界即校验;m2 代际门失配放行档(兼容设计)维持。

## 发现与处置

**本批修复(窄面 ×4,均带测试)**

| # | 发现 | 处置 |
|---|---|---|
| C8-1 | `/runs/preview` serviceBindings 非 dict 形态(list/标量)→ `.items()` AttributeError **500**,应 422 | 手写 dict 入口加形状门(routers/runs.py);+ 测试 3 形态断言 |
| C8-2 | `ck_scope_exactly_one` 只在迁移 0033,models/access_token.py 零表达 —— fresh 库(测试)与迁移库约束漂移 | CheckConstraint 对齐进模型 __table_args__(模型/迁移从此同形);+ IntegrityError 测试 |
| C8-3 | `REGISTRY_ONLY_IDENTITIES/SERVICES` 拼错仅消费侧告警后**按 off 处理**(生产以为开了 enforce 实则全放行,静默失效高危) | config.py Literal["off","audit","enforce"] 化 —— 启动期 ValidationError 即拒(消费侧告警分支转为不可达防御保留);+ 测试;开发 .env 实值 enforce 合法不受影响 |
| C8-4 | 死配置键:GIMBAL_PLUGINS_DIR/PLUGINS/PLUGIN_CONFIGS(平台 Settings 零消费;引擎侧同名 env 是引擎自己的进程环境契约,由部署层直传,不经平台 Settings)+ GIMBAL_CANCEL_GRACE_SEC(B6③ legacy 取消通道退役后零消费) | 删字段留墓碑注释(env 残留由 extra=ignore 消化,同 EXEC_CHAIN 先例) |

**挂账(J 区,后续批)**

| # | 项 | 说明 |
|---|---|---|
| J-1 | plate convert 回包 ok 但缺 converted → 全链 `.get or {}` 静默空,半畸形响应以空场景走到引擎才炸;PlateMock 恒回灌有效形状 = 测试盲区 | 修复方向:plate_client.convert 信封断言(converted 必须 dict,违约显式报错并归类)—— 涉及异常分类学,不随审计批顺手改 |
| J-2 | 队列旧配方缺键语义缺省:升级前入队的配方升级后跑,skip_carry 缺键=False = **多做 carry 注入**(对被测系统多打副作用);兼容取向「多做事」而非拒绝,无版本标记 | 与配方版本化一并立项(若立);当前窗口 = 单次升级瞬态 |
| J-3 | share_refs 表无 ORM 模型、裸 SQL 读写,其 CHECK/unique 仅活在迁移(0013/0049)—— 模型侧零表达 | E 区挂账(退役路径基建,动它须先有消费者) |

**维持口径(设计取舍,登记不修)**

- definition/modeConfig 变量级/graph 语义以 plate/执行器为结构权威的
  晚校验:schema docstring 自认,preview-plate / suites validate 是可选
  前置面 —— 架构决策,不改;
- status 值域应用层常量单源(全仓一贯);
- environments lines plate 不可达跳过(执行期门仍在);
- SSE/事件/台账面的防御兜底(ingester 语义);
- IntegrationTask 状态族宽(N2 归一注释在案);
- ExecutionEvent.seq 双轴语义(event 单调/log 负数令牌)按 (ts,id)
  排序纪律在注释;
- token 范围收紧运行期复核窗口(注释自认);
- CALLBACK_HOST_ALLOWLIST 空=全拒无提示(fail-closed 正确,仅静默);
  EXEC_INGEST_LOG_LEVEL 拼错低级别日志静默不入库;保留期类误配 0=
  禁用清扫语义反转 —— 三项为低危观察,不动。

## 结论

三面合判:**边界即校验为主旋律,晚失败面高度集中且多为文档化的
架构决策**(plate/执行器为结构权威),真正的无校验缺口本批修尽
(4 处,2 处静默失效高危:REGISTRY_ONLY 拼错、CHECK 约束漂移)。
余 J 区三项挂账;「第 5 类」方法论以本档口径替代存档。
