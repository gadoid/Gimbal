# Suite 成员层、引用分享与浏览镜头 — 权限域二期设计方案

> 状态：**定稿**（2026-10-08，经七轮评审收敛，当日定稿）。评审关闭。
> **实施进度（2026-10-09）：P0 全部落地；P1 全部落地（含两项 UX 尾巴，见 §12 P1 实施记录）；P2/P3 未开工。** 各期实施要点与偏差记录在 §12 各「实施记录」小节；残留核实项见 §13.4，变更走 §15 修订记录追加。
> 作者：Codfish

## 0. 文档定位

本方案以 **suite 成员层 + 引用分享 + 浏览镜头** 三件事回应权限域二期需求，取代同日的《场景组与浏览镜头-设计方案》初稿：不引入「场景组」概念，批量管理与批量执行并入 suite，共享改为场景与 suite 统一的「引用 / 副本」两种分享模式。

- **定位**：权限域二期的目标态设计。本文只写现行结论；全部演进过程与被推翻的中间口径（锁型演进、索引方案、防重范围等）以 §15 修订记录为准追溯。
- **上游**：《用户权限与用户管理-设计方案》（2026-09-20，下称《权限一期》），已全部落地。本文沿用其骨架：三级 RBAC 管平台操作、属主原则管资源、单一判定式管可见性。
- **被取代**：《场景组与浏览镜头-设计方案》初稿（2026-10-08）。其中浏览镜头、graph 授权缺口修复、授权闭包与不变量的论证、服务端循环分发的批量执行被本文吸收；组实体、组授权表被废弃。
- **角色词**：按 0011 更名后的口径 `user < member < admin`。引用《权限一期》原文时保留旧词并随注。

## 1. 背景与三个痛点

1. **admin 的场景库被淹没**。《权限一期》§1.2 让 admin 能看到全员的私有场景，可见性谓词对 admin 直接返回全量（`scenario_query.py:56-64`，`visibility_clause` 对 admin 返回 None）。admin 打开「我的场景」页时，看到的是全员的 private 场景。admin 能看全部是矩阵拍板过的权力，这里出问题的是**默认浏览视角**放错了档位。
2. **跨人共享只有拷贝一条路**。现有两条通道：发布公共库，粒度太粗；handoff 分发（`routers/handoff.py`）只能给 fork 副本，副本此后各自漂移，原件更新无法同步。「把这批回归用例给同事跑，并始终跑最新版」没有正解。
3. **批量执行没有实体**。`Execution.batch_id` 只是归并键（`models/execution.py:53-58`）。「挑 N 条一起跑」是 `Runner.vue` 的前端临时队列，选出的集合不落库、不能复用、不能共享。suite 在执行器侧已有设计，但平台上还没有对应的管理实体。

## 2. 架构总纲

### 2.1 权限三问分层

权限系统回答三个互相独立的问题。把它们混在一起，就会用权限系统去解决偏好问题，痛点 1 的根源就在这里。

| 问题 | 性质 | 机制 | 本方案动作 |
| --- | --- | --- | --- |
| 我能做哪些平台操作 | 政策 | 三级 RBAC（`require_role`） | 结构不动 |
| 我能看到、跑谁的内容 | 政策 | 单一判定式：公开 ∨ 属主 ∨ admin | 增加「引用」分支（§7.6） |
| 我默认以什么视角浏览 | 偏好 | 前端镜头（我的 / 全部），不进入权限判定 | 新增（§5） |

### 2.2 原则沿用与新增原则五

《权限一期》§0 的四条原则继续有效：权限是政策不是偏好；运营看信号、看字段面，不看值面；前端守卫只服务于体验；判定式单点收敛。

**原则五：治理权 ≠ 内容镜头。** admin 的权力通过定向流程行使，包括审计、离职处置、下架、撤销引用。内容浏览的默认视角对所有人（包括 admin）都是「我的」，「看全部」需要显式切换。执行记录对 admin 硬隔离、凭证对 admin 不可见，这两条既有设计早已体现了这个方向。

### 2.3 范式：不换代数

| 候选范式 | 否决理由 |
| --- | --- |
| 细粒度 RBAC（角色→权限包→资源） | 三级角色、十余种资源，加一层权限间接层换来的灵活性没有人用得上 |
| ReBAC（Zanzibar/OpenFGA） | 列表端点要靠 SQL 分页加可见性过滤，最后仍要把关系拼回 WHERE，等于维护两份；全系统只有一个鉴权执行方 |
| ABAC / 策略引擎（OPA/Cedar） | 规则很简单（visibility + 属主 + 角色 + 引用），「策略在外、过滤在 SQL」要两轨维护 |
| 团队 / 组织层级 | 单团队部署用不上；owner_id 改 team_id 是全表迁移；树形结构隐含单一归属 |

**演进触发器**（任一条出现之前不动）：

- 出现第二个鉴权执行方，改为集中式判定服务；
- 出现真实的多团队需求，引入团队归属；
- 出现条件化规则（时间窗、环境限定），考虑 ABAC；
- 直连数据库的数据泄露成为实际风险，上 RLS。

### 2.4 相对初稿的收敛

| 初稿 | 本文 | 理由 |
| --- | --- | --- |
| 新增「场景组」实体 | 并入 suite：suite 的成员层承担「管理、绑定一组用例」 | 组是 suite 聚合模式的子集，两个集合概念并存会互相漂移 |
| 组跑（服务端循环 dispatch + batch_id） | 保留这套机制，挂到 suite 的聚合模式上；非聚合模式交给执行器 | 聚合模式就是「逐个跑成员、无执行策略」，循环分发加 batch_id 是它的完整实现，且下游零改动 |
| 组授权表（只针对组） | `share_refs`：场景与 suite 统一的引用分享 | 分享语义在两种资源上保持一致，避免用「单成员 suite」绕路 |
| scope API 默认 mine | API 默认 all，前端传 mine | 镜头属于偏好，默认值归前端，API 保持向后兼容 |
| 安全边界靠应用层校验 + 读时谓词 | 组合外键在库层约束成员与属主一致 | 非法状态写不进去，转让时不会静默漂移 |

## 3. 目标态一句话

场景库的浏览视角对所有人默认是「我的」，admin 显式切换到「全员视角」。suite 突出「管理、绑定一组用例」的能力，承担批量组织与批量执行。场景和 suite 分享时，由分享者在弹窗里选择**引用**（同步：只读可执行，属主保存即对被分享人生效，属主可撤销、被分享人可退订）或**副本**（非同步、默认：独立拷贝，不可撤回）。引用是唯一新增的 ACL 原语，RBAC 角色体系结构不变。

## 4. 翻案声明

本文正式修订《权限一期》§0.5「小团队不做 per-user 授权」、§4.2「共享（per-user 授权）不做」，以及 handoff v2 方案对 `scenario_shares` 授权表的否决。

**修订为**：允许**显式、逐次、无状态**的引用分享，粒度为场景和 suite（双粒度一步到位）。一期否决的前提是隐式、批量、带状态的授权。本方案的前提不同，原有的三条理由逐条不再成立：

| 一期否决理由 | 本方案下 |
| --- | --- |
| N 场景 × M 用户的授权蔓延 | 每条引用都由分享者在弹窗里主动发起，没有隐式批量通道；`SHARE_REF_CAP` 设上限（§6.3）、团队约 10 人，规模有界；表只存当前生效的引用，撤销与退订即删行，无历史行累积 |
| TTL、撤回的状态管理 | 不做 TTL；撤回、退订都是删一行，下一次请求即失效；授权表只存当前生效的引用 |
| 可见性判定退化为「join 共享表」的组合问题 | 判定只增加固定深度的 EXISTS 分支（直接引用、所在 suite 被引用），不递归 |

**选择双粒度的理由**：只开 suite 粒度时，单个场景的引用分享只能靠「建一个单成员 suite」绕路，会产生大量无意义的 suite，且场景与 suite 的分享体验不一致；双粒度的工程增量只是判定式多一条 EXISTS，`share_refs` 一张表同时承载两种资源。

**不翻的部分**：对外可见性仍然只有「发布 / 下架」一个开关（《权限一期》§2.2）。引用是定向协作通道，不改变资源的 `visibility` 列，公共库和「我的」页的既有语义不受影响。

## 5. 浏览镜头（scope）

浏览镜头是偏好，不是政策：它只改变「我浏览什么」，不改变「谁能看到什么」。默认值放在前端，API 保持向后兼容。

### 5.1 后端

`GET /api/scenarios` 和 `GET /api/suites` 增加 `scope ∈ {mine, all}` 参数，**API 默认 `all`**，与现行行为完全一致。

- `mine`：`owner_id = :me`，即我创建的全部内容，**包括已发布的**。
- `all`：现行可见性上限。admin 为全量；其他角色为公开、自己的和被引用的。非 admin 传 `all` 时静默等价于其上限，不报错。
- 改动两处：`scenario_query.visibility_clause`（admin 分支在 `scope=mine` 时加属主条件）和 SQLite 兜底路径。
- 显式传了 `visibility=public` 时，`scope` 不叠加生效，公共页的行为不变。

### 5.2 前端

- 场景库与 suite 列表默认传 `scope=mine`。admin 多一个显式的「全员视角」开关，对应 `scope=all`。开关状态作为个人偏好记在本地。
- 「我的场景」页改查 `scope=mine`，自己已发布的场景也会列出，行内加 public / private 徽标，发布和下架的管理入口收敛到这一处。这顺带修复了既有缺陷：现状下用例发布后会从「我的」页消失。
- `RunnableScenariosCard` 判定「我的」的口径，由 `visibility !== 'public'` 改为按 owner 判定。
- 「公共场景」页不变；`scenario_filter_groups` 的键空间不变。镜头是查询参数，不是筛选桶。
- 「共享给我的」作为独立分区出现（§7.11），不混入 `mine`。

### 5.3 与原则一的边界

「权限是政策不是偏好」反对的是把**可见性政策**做成个人开关。镜头不改变任何人的可见集合：任何人在 `scope=all` 下拿到的集合都与其可见性上限严格一致，权限矩阵一个字没动。

## 6. Suite 成员层

suite 的本体是「一组用例的管理与绑定」，编排方式是附加在上面的配置。这与执行器侧已定的「默认聚合，其他编排靠切换模式」一致，只是把重心从模式移到成员上。第一期只做**聚合模式 + 静态成员**，并在同一期交付聚合模式的批量执行（§6.6）。

### 6.1 两层模型

| 层 | 内容 | 性质 |
| --- | --- | --- |
| 成员层 | 包含哪些场景、顺序、加入时间 | 稳定的数据，由平台管理，独立增删 |
| 模式层 | 怎么跑：聚合（默认）、1:N、拼接、地图…… | 配置，用 id 引用成员，不内嵌成员 |

- **切换模式不影响成员。** 模式专属的角色（如 1:N 的前置和变体）写在模式配置里，按 id 引用成员，不在成员表上加列。
- **成员与模式引用的口径。** 管理上，成员是「被执行、被统计的用例」；地图模式注入的 setup/teardown 前置用例属于「模式引用」。权限上两者都算：属主一致约束和引用闭包都要覆盖模式引用。地图等模式上线时，模式引用要写入同一个可查询的成员面（见 §13.2 待决）。
- **成员声明**：第一期只用静态清单。「路径 + 筛选器」延后；如果要提前，平台在保存时把筛选结果固化成清单，不允许动态成员。

### 6.2 结构与值的归属

suite 的结构定义归 plate，值归 platform。平台侧的值按性质分两种存储，**不双写**：

- **成员关系只存 `suite_members` 关系表**，它是成员的唯一真相源，供列表、反查、级联、权限判定和执行使用。
- **模式配置以 JSON 存在 `suites.mode_config`**，按 id 引用成员，不在 JSON 里重复存成员清单。
- 平台向执行器提交 suite 结构时，从成员表读取成员，再合并模式配置拼装。
- 写入 `mode_config` 时校验其引用的 id 必须是当前成员；移除成员时，在同一事务内清理 `mode_config` 中对它的引用。第一期只有聚合模式，`mode_config` 为空，这条规则在非聚合模式上线时生效。

### 6.3 数据模型与约束

```
suites(
  id               BIGSERIAL PK,
  name             VARCHAR(128) NOT NULL,
  description      VARCHAR(512) NOT NULL DEFAULT '',
  owner_id         INT NOT NULL REFERENCES users(id),        -- 不加 ON DELETE：未处置的用户删不掉
  visibility       VARCHAR(16) NOT NULL DEFAULT 'private',   -- 与场景同口径
  mode             VARCHAR(32) NOT NULL DEFAULT 'aggregate',
  mode_config      JSONB NOT NULL DEFAULT '{}',             -- 按 id 引用成员，不存成员清单
  forked_from_id   BIGINT NULL, forked_from_owner_name VARCHAR(128) NULL, forked_from_at TIMESTAMPTZ NULL,
  created_at, updated_at,
  UNIQUE (owner_id, name),
  UNIQUE (id, owner_id)                                     -- 组合外键目标
)

composer_scenarios:  + UNIQUE (scenario_id, owner_id)       -- 组合外键目标
                     + forked_from_id / forked_from_owner_name / forked_from_at（handoff 已有则复用）

suite_members(
  suite_id     BIGINT NOT NULL,
  owner_id     INT NOT NULL,
  scenario_id  VARCHAR(128) NOT NULL,
  sort         INT NOT NULL DEFAULT 0,
  added_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (suite_id, scenario_id),
  FOREIGN KEY (suite_id, owner_id)    REFERENCES suites(id, owner_id)
      ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY (scenario_id, owner_id) REFERENCES composer_scenarios(scenario_id, owner_id)
      ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
  INDEX (scenario_id)                                       -- 反查「场景在哪些 suite」
)
```

- **组合外键是唯一的安全设计点。** suite 里只能放属主自己的场景，由库层保证，admin 也不例外。应用层先校验并返回 404（不泄露存在性），库约束兜底。
- **约束延迟到提交时检查**，是为了配合离职的转让路径：suite、场景、成员表三处的 owner_id 在同一个事务内一起改写。如果有人只转让 suite 里的某一个场景，提交会失败，迫使流程整体处理。
- **公共化路径的顺序要求**：`publicize` 会把场景的 `owner_id` 置空（`users.py:430-437`），此时仍挂在成员表上的行会让组合外键失配。因此处置事务必须**先删除该用户的 suite**（成员行随之级联），再置空场景属主（§7.10）。
- **`suites.owner_id` 不加 `ON DELETE`**：用户在处置完成前删不掉，作为「必须先走处置」的兜底。
- **数量上限与配置**（放进 `core/config.py`，取值待定，超出返回 409）：每人 suite 数 `SUITE_CAP`、每个 suite 的成员数 `SUITE_MEMBER_CAP`、单次 suite 运行的总 runs 数 `SUITE_RUN_TOTAL_CAP`、防重时效窗口 `SUITE_RUN_STALE_HOURS`（§6.6）、每人发出的引用数 `SHARE_REF_CAP`。

### 6.4 级联与运行快照

- 场景删除时，成员行随外键级联删除，场景自动退出 suite。
- suite 删除时，成员行一并删除，场景不受影响。
- 运行开始时一次性读取成员清单作为快照；运行过程中编辑成员，不影响正在跑的这一次。

### 6.5 管理交互

- 场景库支持批量选中后「加入 suite」；场景详情里能反查它属于哪些 suite。
- suite 页分两个页签：成员（列表、排序、移除）和模式配置；页头有「运行」按钮，运行后跳转到批次视图。
- 一个场景可以同时属于多个 suite，例如同时在冒烟集和回归集里。

### 6.6 运行

**聚合模式（第一期）：平台侧循环分发 + batch_id 归并。** 聚合模式的语义就是「逐个跑成员、没有执行策略」，所以服务端循环分发加 batch_id 归并是它的完整实现，不是过渡方案，也不必等执行器侧的 suite 能力。

- `POST /api/suites/{sid}/run`：先过 `can_run_suite`（P1 期 ≡ `ensure_owner` 属主∨admin——suite 恒 private 下两者严格等价，完整判定式含 share_refs 分支随 P2 落 `_ownership.py`）；读取成员快照，按 `sort` 遍历，对每个成员检查 `can_run_scenario` 后逐个调用 `run_dispatcher.dispatch_run`（复用全部既有校验：数据集、注入条目、step_to、`MAX_RUNS_PER_EXECUTION=200`），共享一个服务端生成的 batch_id（格式见防重条目）。
- **每成员的执行配置（已核实口径，§13.3-2）**：服务端加载该成员的**默认运行方案**（每场景一个默认方案，`composer_run_schemes`），把方案参数（数据集行选、注入条目、服务绑定、stepTo、nRuns、parallel）内联进该成员的 RunRequest；无默认方案则裸基线（无数据集行、无注入）。这与前端「在场景库直接点击执行」完全同口径——前端正是读默认方案后内联发送。按成员指定方案或数据集的能力，留给模式配置。**服务绑定对被分享人的可用性（已核实，§13.3-5）**：`serviceBindings.authAlias` 与别名表 credential_alias 默认最终都经 `_resolve_exec_auths` 的 owner 过滤按**执行者本人**凭证池解析，解不到即告警跳过、不存在借用属主凭证的通道——被分享人缺某条凭证时，其成员执行照常发起并在运行期以明确原因失败，不连坐他人。
- **失败语义**：
  - **循环前物化**：成员快照与各成员的默认方案参数在循环开始前**取成纯值**（scenario_id、sort、方案参数 dict），循环内不再触碰 ORM 实例——`rollback()` 会让 Session 内**所有已加载实例过期**（与 `expire_on_commit=False` 无关，rollback 总是触发过期），async 下访问过期属性触发懒加载直接抛 `MissingGreenlet`，一个成员出错会让后续成员**全部连锁失败**。物化同时天然满足 §6.4 的「运行快照」语义。
  - **逐条 try/except**：校验类失败（校验不通过、无权执行、已被删除）与**基础设施异常**（数据库/入队报错；`enqueue` 自决 commit 的设计本会让单场景请求整体 500，`execution_queue.py:60-63`）都捕获；**except 分支先 `rollback`、再归类、再继续**。
  - **归类按落库事实，不按异常位置**：rollback 后**重查** `executions` 中该成员在本 batch_id 下的执行行是否已存在（`enqueue` 已提交的行不受 rollback 影响，重查结果也只取纯值）——**已存在 → 归 `started` 并附分发异常警告**（该执行已入队、之后会照常跑，用户不能看到「跳过」结果却跑了）；**不存在 → 才归 `skipped`**。当前 `dispatch_run` 在 enqueue 提交之后仅剩 `ensure_workers()` 与响应构造（`run_dispatcher.py:873-876`，§13.3-9），错位窗口极小但非零，将来若加通知/事件写入还会扩大——按落库事实重查对代码演化鲁棒，不依赖「异常发生在哪一步」的推断。
  - 最终正常返回部分结果 `{batchId, started: [executionId...], skipped: [{scenarioId, reason}]}`——不出现「前半已入队、请求却 500、前端拿不到 batchId」的半态。`started` 为空时响应仍正常返回，前端按全失败展示 skipped 明细。**找回闭环**：即便响应在网络层丢失，用户重试会命中防重 409 并附本人批次深链，不会重复跑。
- **总量上限**：分发前预计算全部成员的 runs 总数（行 × 注入族），**复用 `dispatch_run` 的 total_runs 同一份计算实现**（`run_dispatcher.py:715-723` 的交叉矩阵口径），避免两处算法漂移出现「预检通过、单成员 409」的边缘；超过 `SUITE_RUN_TOTAL_CAP` 时整体返回 409。
- **防重**：不做 Idempotency-Key 设施——仓内无先例，单场景 `POST /api/runs` 同样未做，单独引入通用幂等（key 存储、有效期、同 key 并发语义）不成比例。规则与边界：
  - **判定范围是 (suite, 发起人)，不是整个 suite**：当前用户在该 suite 上存在未终态批次时返回 409 `suite_run_in_progress`，响应只附**本人**现有批次的 batchId 与深链。引用分享后同一 suite 有多个执行人——锁整个 suite 会让他们互相阻塞几小时，且 409 附他人批次深链等于暴露他人执行，直接违反 §7.5 不变量 2；范围按人之后两个问题同时消失。
  - **查询形状（不需要前缀索引）**：`WHERE owner_id = :me AND status IN ('queued','running') AND created_at > now() - 窗口` 先把范围收窄到本人未终态执行——走既有 `ix_executions_owner_id(owner_id, id)` 复合索引（`models/execution.py:38-41`，0005 升级）；再在（极少量的）结果上匹配 `suite-<sid>-` 前缀（应用层或 SQL 皆可）。单人同时未终态的执行本就稀少，不需要前缀索引，PG 与 SQLite 查询写法一致，也省掉「前缀 LIKE 能否走索引」的方言问题。状态枚举已核实为五值 `queued/running/done/failed/canceled`（`models/execution.py:26-31`），无 pending/dispatching 之类中间态，`{queued, running}` 即全部未终态。
  - **batch_id 生成格式**：`suite-<sid>-<uid>-<uuid 短码>`。范围按人之后，纯时间戳后缀会让两个用户在同一秒对同一 suite 发起时撞出相同 batch_id；带 uid + uuid 后缀后，前缀 `suite-<sid>-<uid>-` 即防重判定的匹配面。
  - **时效窗口 `SUITE_RUN_STALE_HOURS`（默认 24h，config 可调）**：只计入窗口内创建的未终态执行，卡死批次不会把某人对该 suite 永久锁死。手动出路存在但按条：取消是逐执行端点（`POST /api/executions/{id}/cancel`，`executions.py:595`；重启僵尸在该端点也会收敛为 canceled），**没有批次级取消入口**，大批次场景靠时效窗口兜底；批次级取消若成为高频诉求再加端点。**配置注释必须写明「窗口应大于预期的最长批次耗时」**——单 worker 下 50 成员 × `MAX_RUNS_PER_EXECUTION=200` 的极端量级可能真跑超 24h，超窗后允许再发起一批属可接受降级（旧批仍在跑、新批排队，不损正确性），但调参的人必须知道这个耦合。
- **竞态（不加服务端锁，接受良性竞态）**：检查与分发之间存在窗口，前端防抖挡不住双标签页同提交。**两级 advisory lock 在本代码库的提交与池化模式下都不可用**：事务级在首个成员自决 commit 后即释放（§13.3-6）；会话级绑定的是**数据库连接**而非 Session 对象——本代码库的 `async_sessionmaker` 为默认池化形态（PG 侧 QueuePool `pool_size=10, max_overflow=20`，`app/core/db.py:20-31`；§13.3-8），Session 在 commit 后归还连接、下条语句可能取到另一条连接，`finally` 的 unlock 落在错误连接上返回 false，原连接上的锁**泄漏**——之后取到该连接的请求可重入、其余被永久挡住（又一次「永久锁死」）；部署链路若有 pgbouncer transaction 池化，会话级锁直接失效（当前部署直连 PG 无此层，方案按可移植性排除）。**拍板：PG 与 SQLite 同一降级口径——不加锁**。竞态后果只是多出一个批次（两个批次各自记账、通知按批聚合，不损任何不变量）；防重 409 仍拦得住绝大多数场景——第二次提交发生在首次提交落库之后的全部情况；双标签页同一瞬间提交属自伤型边缘。真要防，唯一正确形态是**专用锁连接**（`async with engine.connect()` 持锁覆盖整个循环、与分发 Session 分离，代价是每次运行多占一条连接）——为一个良性竞态引入连接级锁管理不成比例，与「砍幂等键、不做前缀索引」同款取舍，入 §14 不做表。
- **并发与下游零改动**：`EXEC_WORKERS=1` 的持久化 FIFO 队列天然串行消化；`GET /api/executions?batch_id=` 过滤、批次 chip、`execution_finished` 按批聚合的通知全部现成可用。

**非聚合模式（P3）**：1:N、拼接、地图等模式需要执行器的编译、调度、判定链路，届时接入执行器，并决定是否引入父子执行记录模型（§13.2 待决 1）。

### 6.7 与 graph 的关系

平台已有的 graph 编排（compose/chain/gates）与 suite 的拼接、地图模式高度重叠。需要定下：graph 将来被 suite 的模式吸收，还是两者分别负责「一次性编排」和「常驻集合」（§13.2）。在此之前，graph 的授权缺口照修（§8.2）。

## 7. 分享

场景和 suite 共用一套分享机制：分享时弹窗确认，由分享者选择**副本**（默认）或**引用**。副本复用现有的 handoff 语义；引用是唯一新增的授权原语，只能读、能执行，属主可撤销，被分享人可退订。

### 7.1 两种模式

| | 副本（非同步，默认） | 引用（同步） |
| --- | --- | --- |
| 被分享人拿到 | 自己名下的一份独立拷贝 | 访问分享者资源的权利，不产生新资源 |
| 原件后续修改 | 不同步 | 属主保存即生效 |
| 被分享人能否编辑 | 能，副本完全归自己 | 不能，只读可执行 |
| 能否撤回 | 不能 | 属主可撤销，被分享人可退订，下一次请求即失效 |
| 能否再分享 | 能（副本是自己的资源） | 不能；可先「转为副本」再分享 |

- 交互用**模态对话框**，不用吐司。默认选中「副本」。对话框写明两种模式的后果，尤其是副本不可撤回、引用会实时跟随属主的修改。
- 同一资源可以同时存在两种分享：有人拿引用，有人拿副本。对同一接收人重复选择引用是幂等的；已有引用的人再拿一份副本也允许。
- 公开发布（visibility）与这个对话框无关，仍然只有发布 / 下架一个开关。

### 7.2 数据模型

```
share_refs(
  id               BIGSERIAL PK,
  grantee_user_id  INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  scenario_id      VARCHAR(128) NULL REFERENCES composer_scenarios(scenario_id) ON DELETE CASCADE,
  suite_id         BIGINT NULL REFERENCES suites(id) ON DELETE CASCADE,
  granted_by_name  VARCHAR(128) NOT NULL,     -- 快照，人走字留
  granted_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((scenario_id IS NULL) <> (suite_id IS NULL)),   -- 恰好指向一种资源；PG 与 SQLite 双方言通用
  UNIQUE (grantee_user_id, scenario_id),
  UNIQUE (grantee_user_id, suite_id),
  INDEX (grantee_user_id), INDEX (scenario_id), INDEX (suite_id)
)
```

- 两个可空外键加一个 CHECK，保证每行恰好指向一种资源，同时保留外键级联，不退化成多态 id。CHECK 不用 PG 专有的 `num_nonnulls`，以兼容 SQLite 兜底路径。
- **不存 `owner_id`**。分享者由资源的当前属主推导，因此离职处置转让时引用天然跟随资源（§7.10），无需改写这张表。
- 只存当前生效的引用：撤销、退订都是删行，不做软删除、不存日志。判定式依赖这张表，混入历史行就要在每处判定加过滤条件，漏写一处就是越权。

### 7.3 标记口径

同步与否是「这一次分享行为」的属性，不是资源的属性，因此**不在场景表或 suite 表上加 `share_mode` 列**。同一个场景可以同时被 A 引用、被 B 拷贝。

| 模式 | 标记载体 | 说明 |
| --- | --- | --- |
| 引用 | `share_refs` 的行本身 | 行在即有引用，删行即撤销或退订；「共享给我的」直接由这张表推导 |
| 副本 | 副本上的 `forked_from_id` / `forked_from_owner_name` / `forked_from_at` | 用于显示「副本 · 来自某人」，也为以后「对比原件」「重新同步」留依据 |

副本的分享行为记入 `activity_events` 时间线，不进 `share_refs`。

### 7.4 引用的授权闭包

平台现状没有独立的「已保存版本」：场景的 payload 就是 draft 容器（`composer_scenarios.py:82`），定义只有一份。引用读到的就是属主当前保存的定义。

数据集和运行方案的权限挂在父场景上（`routers/run_schemes.py:33-34`、`routers/data_sets.py:56`）。如果引用只覆盖场景本体，被分享人能读定义却读不到方案和数据集，执行就无从谈起。闭包定义如下：

- **读**：场景定义（现有定义读取端点 `GET /{id}/draft`）、preview-plate、数据集与运行方案的读端点；suite 的定义与成员摘要。
- **执行**：单场景执行、run suite、rerun 自己发起的执行记录。
- **不开放**：场景、suite、方案、数据集的一切写操作；把引用再分享出去。
- **suite 引用覆盖成员**：引用一个 suite，即可读、可执行它的全部成员（地图模式上线后还包括模式引用）。反过来，引用某个场景不会带来对它所属 suite 的访问。

### 7.5 不变量

1. **凭证永不跟随**：被分享人执行时按自己的凭证池解析（`run_dispatcher._resolve_exec_auths` 已按执行者过滤）——**默认方案里的服务绑定（serviceBindings.authAlias）与别名表 credential_alias 默认同样只取执行者本人池中的凭证**（§13.3-5），缺失时告警跳过并给出明确原因，不存在借用属主环境凭证的通道。
2. **执行台账归执行人**：被分享人跑出的执行记录归被分享人，属主看不到谁跑了自己的资源，对 admin 同样不可见。
3. **撤销即时生效**：判定不进 token、不走缓存，每次请求查库。
4. **引用是 live link**：属主保存即对被分享人生效，这正是需求本意。防误伤的主要手段是保存提示（§7.11，必做）。
5. **运行快照**：suite 运行开始时固定成员清单。
6. **成员同属主**：suite 成员必须属于 suite 属主，由组合外键保证（§6.3）。
7. **公共资源的执行规则不放松**：非属主跑公共场景或公共 suite 仍需先 fork。引用才是「不拷贝也能跑」的唯一通道。

### 7.6 判定式

```
ref(u, s) ≡ ∃ r ∈ share_refs: r.grantee_user_id = u.id ∧ r.scenario_id = s.scenario_id
          ∨ ∃ r ∈ share_refs, m ∈ suite_members:
                r.grantee_user_id = u.id ∧ r.suite_id = m.suite_id ∧ m.scenario_id = s.scenario_id

can_read_scenario(u, s) ≡ s.visibility = 'public' ∨ s.owner_id = u.id ∨ u.role = 'admin' ∨ ref(u, s)
can_run_scenario(u, s)  ≡ s.owner_id = u.id ∨ u.role = 'admin' ∨ ref(u, s)

can_read_suite(u, t) ≡ t.visibility = 'public' ∨ t.owner_id = u.id ∨ u.role = 'admin'
                     ∨ ∃ r ∈ share_refs: r.grantee_user_id = u.id ∧ r.suite_id = t.id
can_run_suite(u, t)  ≡ t.owner_id = u.id ∨ u.role = 'admin'
                     ∨ ∃ r ∈ share_refs: r.grantee_user_id = u.id ∧ r.suite_id = t.id
                     （运行时再对每个成员逐个检查 can_run_scenario）

写权限：属主 ∨ admin，不变。
```

- **两层检查是交集关系**：先过 `require_role`，确认这个角色能不能做这类操作；再过对象级判定。引用只授予对象级能力，不抬高角色。`user` 角色的权限暂不变。
- **单点收敛**：全部判定集中在 `app/routers/_ownership.py`，禁止在各 router 里自写引用判断。
- **三处同步落地**，缺一处都不算完成：PG 的 `scenario_query.visibility_clause`（加两条 EXISTS；admin 分支仍为 None）、SQLite 兜底路径（`routers/scenarios.py:474-496` 逐行判定随 `_ownership.py` 同步，需补测试钉住）、security_invoker 视图（G5 标准式更新）。suite 列表查询同样要加对应谓词。
- 引用判定的驱动面是 `share_refs(grantee_user_id)` 和 `suite_members(scenario_id)` 两个索引，深度固定、不递归。

### 7.7 发起、撤销与退订

- **只有属主能发起分享**，引用和副本都如此。admin 不能替他人分享内容，防止 admin 借分享把 A 的内容转给 B。
- 发起分享的角色门槛与「能创建内容」的门槛一致。
- 接收人必须是活跃用户，且不能是自己；人员选择器复用 `GET /api/users/roster`。
- 引用采用幂等 upsert；超过 `SHARE_REF_CAP` 时返回 409。
- **撤销**：属主可以撤销自己资源上的任何引用；admin 也可以撤销（属于收缩操作，入审计）。撤销会通知被分享人。
- **退订**：被分享人可以删除自己的引用行，不需要属主操作，也不通知属主；属主分享弹窗里的这一条随之消失。属主想再分享时重新发起即可。
- **转为副本**：被分享人可以把引用转成一份自己的副本，原引用保持不变。副本完全归被分享人，可以再分享。

### 7.8 副本流程

- **场景**：复用现有 handoff。数据集和运行方案按现有规则跟随，凭证永不跟随，副本写入来源字段。
- **suite**：单事务深拷贝，suite 本体和全部成员都复制到接收人名下；`mode_config` 里的成员 id 重映射到新副本；每个副本写入来源字段；成员数受 `SUITE_MEMBER_CAP` 约束；任何一步失败就整体回滚。
- 重复拷贝会产生多份副本，与场景 handoff 的现有行为一致，接受。

### 7.9 发布联动（公共库）

- **数据集随场景可见性公开**，维持《权限一期》口径。
- **发布 suite**：弹窗逐条列出尚未发布的成员，并写明「这些成员及其数据集将一并公开」，确认后级联发布，不做静默级联。
- **往公共 suite 加私有成员（不变量的第二个入口）**：`POST /api/suites/{sid}/members` 在目标 suite 为 public 时，对未发布成员**不直接拒绝，复用发布确认框**——弹窗列出待加入的私有成员并写明「这些成员及其数据集将一并公开」，确认后成员发布 + 入组同事务完成，取消则整个加入不发生。「公共 suite ⇒ 成员全 public」由此在**加入与下架两个入口**都闭合。P1 无 suite 发布入口（visibility 恒 private），本规则随 P2 发布联动生效。
- **属主下架某个成员**：所属的公共 suite **连带下架**（与 admin 路径同规则）——「公共 suite ⇒ 成员全 public」这条不变量不能只靠可忽略的提示守。属主即 suite 属主（组合外键保证），自下架不通知；成员只在未发布 suite 里时无联动。
- **admin 下架某个成员**：所属的公共 suite 自动下架，并通知 suite 属主（与「admin 下架须通知原作者」口径一致）。
- 公共页增加「按所属 suite 归组 / 筛选」，避免一次级联发布把公共库冲淡。

### 7.10 与既有流程的联动

**删除**：资源删除时引用随外键级联删除。删除流程要在级联发生**之前**通知被分享人，否则级联后就查不到该通知谁。

**离职处置**：suite 的命运跟随处置路径。

| 处置路径 | suite | 场景引用（`share_refs.scenario_id`） | suite 引用（`share_refs.suite_id`） |
| --- | --- | --- | --- |
| transfer（转让） | 随成员整体转给新属主，不可拆分，否则组合外键在提交时拒绝 | 随资源转给新属主，无需改写数据 | 同左 |
| publicize（公共化） | **先**删除该用户的全部 suite（成员行级联），**再**置空场景属主 | 删除指向这些场景的引用：场景已公开，读权限不受影响，但无主资源上不应挂着「可执行」引用 | 随 suite 删除级联 |
| purge（清除） | 删除该用户的全部 suite 与场景 | 随场景删除级联 | 随 suite 删除级联 |

- 三条路径中，凡是导致引用消失的，都在级联或删除之前通知被分享人（publicize 的通知文案区分「已公共化」与「已删除」，见 §10）。
- 转让路径通知新属主「你接手了 N 条已分享出去的引用」，同时通知被分享人「分享者已变更为某人」。

**账号停用**：被分享人停用后，登录态失效，引用自然不可用，注销后随外键清理；分享者停用后，引用在处置完成前保持有效。

### 7.11 呈现

- **分享弹窗**：再次打开时列出该资源现有的引用（现查 `share_refs`），每条可撤销。admin 治理时也在这里撤销。
- **列表徽标**：属主自己的资源若正被引用，显示「已引用分享」，只是一个布尔标记，不显示人数。查询时用 EXISTS，**包括经由所属 suite 的间接引用**。
- **保存提示（必做）**：保存一个正被引用的资源时，提示「此资源正被引用分享，保存后对方立即生效」，并列出被分享人名单，同样包括间接引用。引用是 live link，这是防误伤的主要手段。
- **被分享人一侧**：场景库和 suite 列表有「共享给我的」分区，徽标分别为「引用 · 来自某人」和「副本 · 来自某人」。引用资源隐藏编辑入口，提供「转为副本」和「退订」。这些只是体验层面的处理，权限以后端为准。
- **不单独做分享记录页，不维护人数计数**：`share_refs` 本身就是名单。需要跨资源批量管理时再加独立页面（§14）。

## 8. 权限矩阵增量与端点改造

### 8.1 权限矩阵增量（对一期 §2.1 的增量行）

副本持有人就是副本的属主，不单独成列。

| 资源 / 操作 | 属主 | 引用的被分享人 | 其他 user / member | admin |
| --- | --- | --- | --- | --- |
| 场景 / suite 读（定义、方案、数据集、成员摘要） | ✓ | ✓（新增） | 公开的可读，否则 404 | ✓ |
| 场景 / suite 写（含方案、数据集、suite 成员） | ✓ | ✗ 403 | ✗ | ✓（治理） |
| 场景执行 / run suite / rerun 自己的执行 | ✓ | ✓（新增，唯一新开的执行通道） | ✗（公开的需先 fork） | ✓ |
| 发起分享（引用 / 副本） | ✓ | ✗（可先转为副本） | ✗ | **✗（不可代他人分享）** |
| 撤销引用 | ✓ | — | ✗ | ✓（入审计） |
| 退订引用 | — | ✓（仅自己的） | — | — |
| 转为副本 | — | ✓ | — | — |
| 执行记录 | 归执行发起人 | 归执行发起人 | — | owner 硬隔离（不变） |

一期矩阵其余各行原样有效。所有操作在对象级判定之前，先过角色门槛（`require_role`）。

### 8.2 端点权限检查替换

| 位置 | 改动 |
| --- | --- |
| 场景详情、定义读取（`GET /{id}/draft`）、preview-plate、数据集与运行方案的读端点 | 改为 `can_read_scenario`。定义读取端点不收紧：公共读者的行为不变，引用者新增可读，前端调用面不变 |
| `routers/runs.py:62-69` 执行入口 | `ensure_owner` 改为 `can_run_scenario` |
| `routers/executions.py:570-577` rerun | 执行属主不变，场景检查改为 `can_run_scenario` |
| `run_dispatcher` 内部校验 | **无需改动（已核实，§13.3-1）**：数据集仅按父场景归属校验（`run_dispatcher.py:660-666`），run scheme 不在 dispatch 时加载，凭证按执行者本人池解析——被分享人执行不会被内部校验拦截 |
| run suite 入口 | `can_run_suite`；循环分发时对每个成员检查 `can_run_scenario`，不通过则跳过并记录原因 |
| `graph_dispatch.resolve_graph_units`（`graph_dispatch.py:37-70`） | **必修缺口**：现状只检查 unit 场景是否存在，不检查归属，任何登录用户都能经 graph 跑他人的私有场景。`materialize_graph` 物化每个 unit 时对发起人逐个检查 `can_run_scenario`，不通过则抛 `GraphDispatchError`，按 404 口径返回 |
| 处置流程（`users.py:430-437` publicize 等） | 按 §7.10 调整顺序：先删 suite 与相关引用、发通知，再置空场景属主 |
| 全部写端点 | 不改；补测试确认没有写端点误用 `can_read_*` |

错误口径沿用仓规：不可见返回 404，可见但不可写返回 403。

## 9. API 清单

```
# 浏览镜头
GET    /api/scenarios?scope=mine|all          # 默认 all；visibility=public 时 scope 不叠加
GET    /api/suites?scope=mine|all

# suite 成员层
GET    /api/suites/{sid}                      # 详情(含成员全列表;前端详情页即消费全量)
POST   /api/suites                            {name, description}                → 201
PATCH  /api/suites/{sid}                      {name?, description?}
       # mode/modeConfig 随 P3 非聚合模式开放(P1 恒 aggregate,无消费方)
DELETE /api/suites/{sid}                      # 成员行一并删除，场景不动
POST   /api/suites/{sid}/members              {scenarioIds: [...]}
       # 批量加入；他人场景 → 404；公共 suite 加未发布成员走发布确认框（§7.9）
PATCH  /api/suites/{sid}/members/order        {scenarioIds: [...]}
DELETE /api/suites/{sid}/members/{scenarioId}
GET    /api/scenarios/{id}/suites             # 反查所属 suite

# suite 发布
POST   /api/suites/{sid}/publish              # 级联发布未发布成员（确认框，§7.9）
DELETE /api/suites/{sid}/publish              # 下架 suite 本体；成员各自的 public 状态独立保留

# suite 运行（聚合模式）
POST   /api/suites/{sid}/run
       → {batchId, started: [executionId...], skipped: [{scenarioId, reason}]}
       # 409：总 runs 超 SUITE_RUN_TOTAL_CAP（too_many_runs）；
       #      或当前用户在该 suite 已有未终态批次（suite_run_in_progress，附本人现有 batchId 与深链）

# 分享（场景与 suite 统一）
POST   /api/shares                            {resourceType: scenario|suite, resourceId, granteeUserId, mode: ref|copy}
GET    /api/shares?direction=out|in&resourceType=&resourceId=   # 只返回引用；副本历史见 activity_events
DELETE /api/shares/{id}                       # 属主 / admin 撤销，或被分享人退订
POST   /api/shares/{id}/fork                  # 被分享人转为副本，原引用保留
```

- 对象级权限：suite 的写、成员增删、发起分享 = 属主（发起分享时 admin 也不行）；suite 的读、执行 = 按 §7.6 判定；`DELETE /api/shares/{id}` = 属主 ∨ admin（撤销）∨ 被分享人本人（退订）。
- `mode=copy` 时，场景走现有 handoff，suite 走 §7.8 的深拷贝；`mode=ref` 时 upsert `share_refs`。
- 分页信封、字段投影按 M4 的既有口径。

## 10. 通知、审计与时间线

| 事件 | 通知对象 | 通知类型 | 审计 |
| --- | --- | --- | --- |
| 收到引用 | 被分享人 | `share_ref_received`（新增，带资源深链） | 不入 |
| 收到副本 | 被分享人 | 复用 handoff 现有通知 | 不入 |
| 属主撤销引用 | 被分享人 | `share_ref_revoked`（新增） | 不入 |
| admin 撤销引用 | 被分享人、属主 | `share_ref_revoked` | **入**（特权写） |
| 被分享人退订 | 不通知 | — | 不入 |
| 被引用的资源被删除（含处置 publicize / purge 导致的引用消失） | 被分享人（在删除或级联之前发出） | `share_ref_resource_deleted`（新增；**单 type 双文案**：publicize = 「资源已公开至公共库，可从公共库访问」，purge/删除 = 「资源已被删除」） | 按删除、处置的既有口径 |
| 处置 transfer，引用随资源转移 | 新属主、被分享人 | `share_ref_owner_changed`（新增，两侧文案不同） | 随处置流程的既有口径 |
| admin 下架公共 suite 的成员，suite 自动下架 | suite 属主 | 复用「admin 下架」的既有通知 | 入（既有口径） |
| admin 下架公共 suite 本体（`DELETE /api/suites/{sid}/publish`） | suite 属主 | 复用「admin 下架」的既有通知（与「admin 下架他人内容须通知原作者」口径一致） | **入**（特权写） |
| 属主下架公共 suite 的成员，suite 连带下架 | 不通知（自下架） | — | 不入 |
| suite 运行完成 | 执行人 | `execution_finished`（既有，按 batch_id 聚合为一条） | 不入 |

- 审计维持「只记特权写和用户管理写」的口径。属主处理自己资源的分享，与「发布 public 不入审计」同类。
- `activity_events` 记录全部分享事件（引用和副本）、撤销、退订、转为副本。副本的分享历史只存在这里。
- 服务画像的信号层维持平台视角，不按 owner 过滤（服务画像方案 §2.4 槽③），浏览镜头只作用于场景库和 suite 列表。

## 11. plate 管道配套产出

按「管理员管理成员」切片的既有流程：PRD → 用户故事 → 词条 → 端点描述 → 评审入库 → 渲染进 catalog。

- `systems/platform/deliverables/prd-suite-and-sharing.md`
- 用户故事：`story-owner-binds-scenarios-to-suite.md`、`story-owner-runs-a-suite.md`、`story-owner-shares-by-reference.md`、`story-owner-shares-a-copy.md`
- 词条：`dictionary/suite.md`（`entity:suite`、`entity:suite_member`、`cap:suite.run`），`dictionary/share.md`（`entity:share_ref`、`cap:share.ref`、`cap:share.copy`、`cap:share.revoke`、`cap:share.unsubscribe`、`outcome:share.received`）
- 端点：`systems/platform/endpoints/platform.suites.*.md`、`platform.shares.*.md`，以及 `platform.scenarios.list` 的 scope 参数
- 字典和端点描述里的角色词一律用新口径（user/member/admin），与 §15 的角色口径债一起清偿。

## 12. 分期与验收

P0 与其余各期都无依赖，先做。批量执行随 P1 交付，不再挂在执行器侧能力上。**进度：P0 ✅、P1 ✅（含两项 UX 尾巴，2026-10-09 全部收口）、P2/P3 未开工。**

### P0 浏览镜头 + graph 缺口（无 schema 变更）✅ 已实施（2026-10-09）

- [x] `scope=mine|all` 参数（API 默认 all），`visibility_clause` 与 SQLite 兜底两处改造
- [x] 前端：场景库镜头默认 mine，admin「全员视角」开关；「我的场景」页包含已发布场景并显示徽标；Runnable 口径改为按 owner 判定
- [x] `graph_dispatch` 的 unit 逐个检查 `can_run_scenario`（此时 = 属主 ∨ admin）
- [x] graph 修复的回归面：GraphSpec 已确认不落库（RunRequest 请求体即全部）—— 无存量可扫，回归测试覆盖
- [x] plate 字典 `user.md` 的旧口径与端点描述的旧角色词同步

**验收**：admin 打开场景库默认只见自己的内容，切换「全员视角」后恢复全量；member 在两种镜头下的集合与改造前一致；公共页行为不变；graph 编排中含他人私有场景时返回 4xx。

**实施记录（2026-10-09）**：
- **facets 同口径补齐**：设计正文只写了列表端点，实施时 `scenario_facets` 一并接 scope（否则「我的」页筛选侧栏计数按全量算，与列表口径背离）。
- **graph 闸落位修正**：§8.2 原文写「`materialize_graph` 物化时检查」；核实发现 `req.graph` 在 dispatch 时只进任务 payload、unit 物化全部发生在 **worker 侧**（无法回 4xx）——闸门实际落在**请求侧** `runs.py`（覆盖 units + before/after 三括号，去重后逐个过闸）。rerun 不重放 graph（config 重放构造无 graph 字段），runs.py 即唯一入口。错误契约与顶层闸一致：不存在 → 404，非属主非 admin → 403 `not_owner`。
- **Runner 选择器与 Runnable 工作台卡**的「我的」口径同步改 `scope=mine`——顺带修复 admin 的「我的可执行」卡此前列全员 private 的同款淹没问题，且 member 现在能选择并运行自己已发布的场景（owner 语义修正）。
- §13.4 顺手关闭两条（GraphSpec 不落库、draft 前端调用面 = `api/scenario-composer.ts:107` 编辑流）。

### P1 suite 成员层 + 聚合模式运行 + 处置路径 ✅ 已实施（2026-10-09；两项 UX 尾巴同日收口）

- [x] 迁移：`suites`、`suite_members`、`composer_scenarios` 组合唯一键、来源字段、上限与窗口配置（`SUITE_CAP=50`、`SUITE_MEMBER_CAP=100`、`SUITE_RUN_TOTAL_CAP=1000`、`SUITE_RUN_STALE_HOURS=24`）—— 0012_suites 已落开发 PG
- [x] suite 的增删改查与成员管理端点、反查端点（`GET /api/scenarios/{id}/suites` 后端就绪）
- [x] `POST /api/suites/{sid}/run`：循环分发、batch_id（`suite-<sid>-<uid>-<uuid>`）、**循环前物化成员快照与方案参数为纯值**、逐成员 try/except（**except 先 rollback、再按落库事实重查归类：已入库归 started 附警告、未入库归 skipped**）、总量上限（复用 total_runs 计算）、进行中批次 409（按 (suite, 发起人) 判定 + 时效窗口；**不加服务端锁**）；前端运行按钮防抖（disabled 守卫）
- [x] 处置流程三条路径的 suite 处理（transfer 整体转让、publicize 先删 suite 再置空属主、purge 全部删除）
- [x] 前端：suite 管理页（列表/新建）+ 详情页（成员/模式两页签、成员选择器 scope=mine、排序/移除）、运行按钮跳转批次视图、路由与侧栏接线
- [x] **尾巴①**：场景库批量勾选 →「加入 suite」（多选 + 选组弹窗；加成员能力已由详情页选择器覆盖，此为库侧入口增强）
- [x] **尾巴②**：场景详情页「所属 suite」反查展示（后端端点已就绪，前端未接）

**验收**：

- 属主把他人场景加入 suite 时被 404 拒绝，绕过应用层直写数据库也被约束拒绝（后者 PG 生效；SQLite 测试库不强制 FK，测试以应用层 404 断言为准——仓内既有口径）。
- 场景删除后自动退出 suite；单独转让 suite 内的场景时事务失败。
- 三条处置路径的事务都能成功提交；publicize 后该用户的 suite 已删除；未处置的用户无法被删除。
- run suite 产生一个批次，批次通知聚合为一条；单个成员校验失败时跳过并返回原因；超过总量上限返回 409。
- **一个成员数据库异常后，后续成员不受连锁影响**（快照已物化，循环内无 ORM 懒加载）。
- **异常归类不错位**：模拟 enqueue 提交后抛错（如 monkeypatch `ensure_workers`）——该成员归 `started` 且附分发异常警告、执行照常跑；模拟提交前/提交中失败——归 `skipped`；响应一律正常返回部分结果（不 500），重试命中 409 并附本人批次深链。
- 防重按人：**同一用户**在同 suite 存在未终态批次时再次发起返回 409，且深链只指向本人批次；**另一用户同时对同一 suite 发起不受影响**；前一批次全部终态（或超出 `SUITE_RUN_STALE_HOURS` 窗口）后可再次发起。

**实施记录（2026-10-09）**：
- **迁移顺序修正（真实 PG 暴露）**：`composer_scenarios` 的组合唯一索引必须**先于** `suite_members` 建表——PG 要求 FK 目标列在建 FK 时已有唯一约束（SQLite 测试不强制 FK，测不出该顺序问题）。
- **fanout 计算抽出共用**：`dispatch_run` 内的行选择合并/注入过滤/交叉矩阵抽出为 `compute_run_fanout` + `fanout_total`，总量预检与 dispatch 共用同一份实现（防「预检通过、单成员 409」漂移）；行为等价由 93 条执行链测试回归确认。
- **响应 shape 扩展**：run suite 返回含 `dispatchWarnings` 字段——「提交后异常归 started 附警告」的载体（§6.6 语义的实现形态）。
- **成员 RunRequest 不传 preloaded_scenario**：except 分支 rollback 后 ORM 实例过期（async 懒加载抛 `MissingGreenlet`），改为让 `dispatch_run` 每成员自查一行（PK 查询）；发起人 id/角色同样先取纯值。
- **路由让位**：既有一次性 graph 编排页 SuiteComposer 迁至 `/suites/composer`，`/suites` 让位给用例组管理页（列表 `/suites`、详情 `/suites/:id(\d+)`）；侧栏拆「用例组」「Suite 编排」两入口，后者置灰标注正交待 §13.2-2 拍板。
- **SQLite 双方言兜底**：`scenario_store.delete` 显式清 `suite_members`（PG 上 CASCADE 已处理，与 user_stars 的 Python 兜底同款理由）。
- **测试纪律**：函数级 `monkeypatch.undo()` 会把 `fresh_db` 借同一实例做的引擎置换一并撤销（后续请求穿透到全局库）——打补丁一律用独立 `MonkeyPatch.context()`；防重测试用直插在途执行行伪造（测试环境 dispatch 惰性起 worker、执行对 plate 503 秒级终态，真实发起复现不了窗口）。
- **尾巴①②收口（2026-10-09）**：①库侧批量加入 = `ScenariosMine` 勾选列（仅「我的」镜头开放——全员视角含他人场景，加入自己的 suite 必 404，勾选列整体隐藏）+ `AddToSuiteDialog`（`scope=mine` 单选目标、空态引导去用例组新建、404/409 透出后端人话；挂载即开需 `immediate: true`，否则 watch 不触发）；②详情页 `meta-grid` 增「所属 Suite」徽章行（反查端点并行加载、非属主 403/空集整行不渲染，徽章直达 `/suites/{id}`）。测试 3+1 条（弹窗真实 teleport 按 ScenarioExportMenu 惯例 `attachTo body + document.querySelectorAll`）。

### P2 分享（场景与 suite 双粒度）⬜ 未开工

<!-- P2 清单维持原样;开工时逐项勾选并附实施记录。 -->

- [ ] 迁移：`share_refs`（双方言 CHECK）
- [ ] `_ownership.py` 判定扩展，三处同步（PG 谓词、SQLite 兜底、security_invoker 视图）
- [ ] §8.2 全部端点检查替换（含定义读取端点；`run_dispatcher` 内部已核实无需改动）
- [ ] 分享端点、suite 深拷贝、转为副本、退订
- [ ] 处置流程中引用的处理与通知（§7.10，publicize 双文案）
- [ ] 发布联动（suite 发布端点、级联确认并提示数据集一并公开、公共 suite 加未发布成员走发布确认框、属主/admin 下架成员连带公共 suite 下架——admin 下架通知属主、属主自下架不通知；admin 下架 suite 本体通知属主并入审计）
- [ ] 通知类型接线、activity_events、admin 撤销入审计
- [ ] 前端：分享弹窗、徽标、保存提示（必做）、「共享给我的」分区、退订入口
- [ ] plate 管道产出（§11）

**验收**：

- 被分享人能读定义、方案、数据集，能执行单场景、能 run suite、能 rerun 自己的执行；写操作返回 403，再分享引用被拒。
- 被分享人缺凭证时执行仍可发起，运行期以明确原因失败（凭证按本人池解析，不借用属主凭证）。
- 属主保存后，被分享人立即读到新定义；保存时属主看到提示和被分享人名单（含经由 suite 的间接引用）。
- 撤销后下一次请求即失效，被分享人收到通知；退订后被分享人不再可见，属主的分享弹窗里该条消失，属主不收到通知。
- 资源删除、publicize、purge 导致引用消失时，被分享人收到通知（publicize 文案为「已公共化」）；transfer 后引用仍然有效，新属主和被分享人都收到通知。
- admin 发起分享被拒；admin 撤销引用产生审计记录；admin 下架公共 suite 本体，属主收到通知且审计有记录。
- 引用 suite 能读、能执行其全部成员；引用单个场景不带来所属 suite 的访问。
- 往公共 suite 加入私有成员时弹发布确认框：确认后成员发布并入组，取消则不加入；加入后公共 suite 内无未发布成员。
- 属主下架公共 suite 的成员后，该 suite 连带下架、不再出现在公共库；admin 下架同规则且通知属主。
- suite 深拷贝中途失败时整体回滚，模式配置的成员引用指向新副本。

### P3 非聚合模式接入执行器 ⬜ 未开工（前置:§13.2 待决 1/2 先拍板）

- [ ] 父子执行记录模型拍板（§13.2 待决 1）
- [ ] 1:N、拼接、地图等模式接入执行器的编译、调度、判定链路
- [ ] suite 与 graph 的关系拍板（§13.2 待决 2）

**验收**：非聚合模式运行时，执行记录和通知只归执行人；运行中编辑成员不影响本次运行。

## 13. 决策、待决与待核实

### 13.1 已决（现行口径，全部决策）

| # | 事项 | 结论 |
| --- | --- | --- |
| 1 | 处置三路径下 suite 与引用的命运 | transfer 整体转让，引用随行；publicize 先删 suite 与场景引用再置空属主；purge 全部删除。引用消失前通知被分享人（§7.10） |
| 2 | draft 端点与「已保存版本」 | 现状 payload 即定义，没有独立的已保存版本。**不收紧**定义读取端点，接入 `can_read_scenario` 即可；不采用「收紧 draft 端点另开只读端点」的替代案——两个端点会返回同一份数据，还要改动前端与公共读者行为。引用明确为 live link，保存提示必做 |
| 3 | 批量执行的交付时点 | 聚合模式在平台侧循环分发 + batch_id，随 P1 交付；非聚合模式在 P3 接入执行器 |
| 4 | 引用粒度 | 场景与 suite 双粒度一步到位（理由见 §4） |
| 5 | 数据集随发布 | 随发布公开，维持《权限一期》口径；发布确认框写明数据集一并公开 |
| 6 | 被分享人退订 | 允许：删行，不通知属主 |
| 7 | `share_refs` 的 CHECK | `(scenario_id IS NULL) <> (suite_id IS NULL)`，双方言通用 |
| 8 | 成员关系存储 | 单一真相源 `suite_members`，`mode_config` 只存模式配置不存成员清单，不双写（§6.2） |
| 9 | run suite 防重 | 不做通用幂等键（前端防抖 + 后端判定）；判定范围 **(suite, 发起人)**，409 深链只指本人；batch_id `suite-<sid>-<uid>-<uuid>`；查询按 `owner_id + status + created_at 窗口` 先收窄（走既有 `ix_executions_owner_id` 复合索引）、前缀匹配放应用层、**不做前缀索引**；时效窗口 `SUITE_RUN_STALE_HOURS`（配置注释写明应大于最长批次耗时）；状态枚举五值无中间态，`{queued, running}` 即全部未终态 |
| 10 | run suite 竞态 | **不加服务端锁，接受良性竞态**：事务级锁在逐成员自决 commit 下提前释放、会话级锁与连接池冲突（泄漏即永久阻塞，§13.3-6/8）、专用锁连接不成比例——PG/SQLite 同一降级口径（§6.6；专用锁连接方案在 §14） |
| 11 | 循环实现纪律 | **循环前物化**成员快照与方案参数为纯值，循环内不触碰 ORM 实例——`rollback()` 总是使 Session 内已加载实例过期（`expire_on_commit=False` 只管 commit），async 下访问过期属性触发懒加载抛 `MissingGreenlet`，一个成员出错会让后续成员连锁失败 |
| 12 | 循环异常语义 | **逐成员 try/except**；except 先 rollback、**再按落库事实重查归类**（该成员在本 batch_id 下的执行行已存在 → `started` 附分发异常警告；不存在 → `skipped`）；正常返回部分结果，`started` 为空也正常返回；网络层丢响应由「重试 → 409 附本人批次深链」兜底 |
| 13 | 属主下架公共 suite 的成员 | **连带下架**所属公共 suite（守「公共 suite ⇒ 成员全 public」不变量；属主即 suite 属主，自下架不通知） |
| 14 | 公共 suite 加入私有成员 | **不拒绝，复用发布确认框**：确认后成员发布 + 入组同事务；不变量在加入与下架两个入口闭合。P1 无 suite 发布入口，随 P2 生效 |
| 15 | publicize 导致引用消失的通知 | 单 type `share_ref_resource_deleted` 双文案：已公共化（可从公共库访问）/ 已删除 |
| 16 | admin 下架 suite 本体 | 通知 suite 属主 + 入审计（与「admin 下架他人内容须通知原作者」口径一致） |
| 17 | `SUITE_RUN_TOTAL_CAP` 预计算 | 复用 `dispatch_run` 的 total_runs 同一份计算实现（`run_dispatcher.py:715-723`），防两处算法漂移 |

### 13.2 待决（需要拍板）

| # | 事项 | 影响 | 何时必须定 |
| --- | --- | --- | --- |
| 1 | 非聚合模式的执行记录模型：父记录 + 子记录，还是继续沿用 batch_id 归并 | 队列、通知聚合、报告、平台执行链 | P3 开工前 |
| 2 | suite 与 graph 的关系：graph 被 suite 模式吸收，还是分别负责「一次性编排」与「常驻集合」 | 是否会出现两个编排概念 | 拼接 / 地图模式上线前 |
| 3 | 地图模式的模式引用如何写入成员可查询面（例如成员表加 kind 区分成员与引用，或单独的引用表） | 属主约束与引用闭包能否覆盖注入的前置用例 | 地图模式上线前 |
| 4 | 「路径 + 筛选器」形式的成员声明是否在平台开放，以及如何固化为静态清单 | 动态成员会让引用的覆盖面随时间变化 | 筛选器上线前 |

### 13.3 已核实（以代码为准，已关闭）

| # | 原疑问 | 结论（证据） |
| --- | --- | --- |
| 1 | `dispatch_run` 内部对数据集、运行方案是否按属主校验 | **不校验属主**。数据集只按父场景归属校验（`ds.scenario_id != scen.scenario_id` → 404，`run_dispatcher.py:660-666`）；run scheme 不在 dispatch 时加载（`scheme_id/scheme_name` 仅溯源记录）。§8.2 该行关闭为「无需改动」，P2 因此变轻 |
| 2 | 场景「直接执行」的默认执行配置口径 | 空选 = 裸基线（`fanout_datasets` 退化为单行空字典）；「直接执行」= 前端读该场景默认 run scheme 后内联发送。服务端 suite 跑复刻同口径（§6.6） |
| 3 | 用户注销是硬删除还是软删除 | `DELETE /api/users` 走处置三选一后**硬删**；`is_active=false` 是停用，不触发任何级联——§7.10「账号停用」行写法正确 |
| 4 | `composer_scenarios.scenario_id` 唯一性 | `unique=True, index=True`（`composer_scenario.py:68-69`），`share_refs` 外键前提成立 |
| 5 | 默认方案的服务绑定在被分享人执行时如何解析；是否指向属主私有配置 | **不会用到属主的凭证**：`serviceBindings.authAlias`（`run_dispatcher.py:734-736`）与别名表 credential_alias 默认（`service_aliases.py:108-126`，查询**无 owner 过滤**、`alias_name` 为全局唯一 PK）最终都汇入 `_resolve_exec_auths` 的**执行者本人**凭证池解析（`run_dispatcher.py:2075-2104`），解不到 → 告警跳过（`:2082` 口径）。别名行（含 base_url、credential_alias 名字）本就是 CurrentUser 可读资产（`GET /api/service-aliases`），执行期命中不构成新暴露面，不收紧；base_url 属路由信息非凭证，按既有三层链口径处理 |
| 6 | dispatch 路径的事务提交边界 | **逐成员自决 commit**：`_create_execution` 建行 `flush`（不提交，快照同事务），随后 `execution_queue.enqueue` 内部 `await db.commit()`（`execution_queue.py:60-63`，注释明示「服务内自决 commit；失败整个请求 500，不留『有执行无任务』的半态」）。suite 循环分发时每个成员各提交一次——事务级 advisory lock 在首个成员提交后即释放 |
| 7 | Execution 状态枚举完整性与 owner 侧索引 | 五值 `queued/running/done/failed/canceled`（`models/execution.py:26-31`），无 pending/dispatching 中间态；owner 侧有 `ix_executions_owner_id(owner_id, id)` 复合索引（`:38-41`，0005 升级），防重查询按 owner 先收窄即可走索引，无需前缀索引 |
| 8 | 会话级 advisory lock 与连接池的相容性 | **不相容**。`async_sessionmaker(engine, expire_on_commit=False)`（`app/core/db.py:31`）为默认池化形态：Session 每事务借出连接、commit 后归还，下一条语句可能取到另一条连接——`finally` 的 unlock 会落在错误连接上（返回 false），原连接上的锁**泄漏**；PG 侧 QueuePool `pool_size=10, max_overflow=20`（`db.py:20-29`）下，被泄漏锁的连接会被循环复用，取到它的请求可重入、取不到的被永久挡住。当前部署直连 PG、无 pgbouncer（transaction 池化会使会话级锁直接失效），但方案按可移植性排除 |
| 9 | `dispatch_run` 在 enqueue 提交之后是否还有写入步骤（异常归类的事实基础） | **无写库步骤，但窗口非零**：`await _eq.enqueue(...)`（内部 `db.commit()`，`execution_queue.py:58-63`）之后只剩 `_eq.ensure_workers()`（惰性起 worker，`run_dispatcher.py:874-875`）与 `RunResponse` 构造（`:876`）。`ensure_workers` 理论上可抛——异常发生在 commit 之后时执行已入队会照常跑，故异常归类必须按**落库事实重查**而非异常位置（§6.6） |

### 13.4 待核实（以代码为准，实现期顺手确认，不阻塞开工）

- ~~handoff 是否已经记录副本来源；有则复用，不新增来源字段。~~ → **已核（2026-10-09，实现 review）**：`copy_scenario` 不写来源（仅在 meta.name 加「(副本)」后缀）；`forked_from_*` 三列存在于 `suites` 表但 `composer_scenarios` **无此列**——P2 需为 `composer_scenarios` 补三列（场景副本与 suite 副本共用一套来源字段），随 0013 迁移落地。
- ~~GraphSpec 是否落库（决定 P0 graph 修复回归面的检查方式）~~ → **已核（2026-10-09，P0 实施时）**：不落库，RunRequest 请求体即全部 —— 无存量可扫，graph 回归靠测试覆盖。
- ~~定义读取端点 `GET /{id}/draft` 的前端调用面，确认接入 `can_read_scenario` 后无需改前端~~ → **已核（2026-10-09）**：调用面 = `api/scenario-composer.ts:107`（CaseComposer/SchemeWorkbench 编辑流）；P2 接入 `can_read` 时公共读者/引用者的行为面不变，前端无需改动。

## 14. 明确不做与重评触发器

| 项 | 理由 | 重评触发器 |
| --- | --- | --- |
| 「场景组」实体 | 被 suite 成员层与 run suite 覆盖，两个集合概念并存会互相漂移 | — |
| 收紧 draft 端点并另开只读端点 | 平台没有独立的已保存版本，两个端点会返回同一份数据 | 平台引入真正的草稿 / 发布双版本时，引用与公共读者的可读范围收紧到发布版本 |
| 版本快照式引用（被分享人锁定在某个版本，属主点击后才同步） | 依赖 plate 的 release / 版本管理，「冻结快照」与「用例变更插件按 release 迁移」之间的冲突要等版本机制定下后才能解 | plate release 落地后，引用升级为「分享 suite / 场景的某个 release」 |
| 通用幂等键（Idempotency-Key）设施 | 仓内无先例；单场景执行同样未做，单独为 suite 跑引入不成比例；防重由前端防抖 + 按 (suite, 发起人) 的未终态批次 409 承担（§6.6） | 跨端重试 / 重复提交成为真实问题 |
| run suite 的服务端竞态锁（advisory lock / 专用锁连接） | 双标签页同瞬提交的后果只是多出一个良性批次，不损任何不变量；事务级锁在逐成员 commit 模式下提前释放、会话级锁与连接池冲突（泄漏即永久阻塞，§13.3-6/8），专用锁连接为此引入连接级管理不成比例——与砍幂等键、不做前缀索引同款取舍 | 双开提交成为真实问题 / 观察到重复批次造成实际困扰 |
| 批次级取消入口 | 逐执行取消已可用（含重启僵尸收敛），大批次卡死靠 `SUITE_RUN_STALE_HOURS` 窗口兜底 | 批次级取消成为高频诉求 |
| 引用的多档权限（只读档、可再分享档） | 一档够用；可再分享是权限蔓延的入口 | 出现稳定的「只给看不给跑」需求 |
| 引用的二次分发 | 同上；需要时先转为副本 | — |
| 独立的分享记录页 | 管理分享几乎都从具体资源出发，分享弹窗、徽标、通知、时间线已覆盖 | 出现跨资源批量管理需求（交接时批量撤销、admin 全员分享关系治理） |
| 被引用人数计数 / 冗余名单 | `share_refs` 本身就是名单；对属主有用的是「正被引用」这个布尔信号 | — |
| 资源表上的 `share_mode` 列 | 同步与否是分享行为的属性，不是资源属性 | — |
| suite 嵌套、组织层级、团队模型 | 授权判定会变成递归；单团队部署用不上 | 真实多团队需求 |
| 平台侧的批级执行策略（串行、失败即停） | 聚合模式没有执行策略；有策略的执行归执行器的 suite 模式 | — |
| 用 GraphSpec aggregate 承载 run suite | 会产出一个巨型单 Execution，而现有列表与通知按「多 Execution + batch_id」设计，反而要改下游 | — |
| 同一 (suite, 发起人) 并行发起多个批次 | 单 worker FIFO 下误触双批塞满队列；防重按 (suite, 发起人) 拒绝，**不同执行人互不影响**；同瞬双开的窗口期漏网属良性竞态，不加锁（§6.6） | 出现真实的同人多开需求 |
| RBAC 结构调整、细粒度权限、ReBAC、ABAC、RLS 重档 | §2.3 的触发器未出现 | 见 §2.3 |
| 镜头进入权限判定、「全员视角」落审计 | 镜头是偏好不是政策；admin 全量可见本就是矩阵拍板的权力 | — |

## 15. 顺手收掉的债与修订记录

### 顺手收掉的债

1. **graph 链的授权缺口**（`graph_dispatch.py:37-70`，§8.2）：P0 强制修复，与分享无关。
2. **plate 侧的角色口径债**：`user.md` 字典「admin/member 两级」的旧口径，以及各端点描述里 operator/member 的旧词，随 P0 清偿。
3. **「我的场景」页丢失已发布用例**的体验缺陷，随 P0 的镜头改造修复（§5.2）。

### 修订记录

| 日期 | 版本 | 内容 |
| --- | --- | --- |
| 2026-10-08 | 初稿 | 《场景组与浏览镜头》：组实体、组跑、组授权、浏览镜头 |
| 2026-10-08 | 第一轮 | 评审后收敛：组并入 suite 成员层；组授权改为场景与 suite 统一的引用 / 副本分享；镜头默认值移到前端；安全边界改为库层组合外键；引用随处置转让、撤销通知、副本可再分享；不做分享记录页与人数计数；RBAC 结构不变，`user` 权限暂不变 |
| 2026-10-08 | 第二轮 | 吸收外部评审 B1–B3、D1–D6：补齐处置三条路径（publicize 先删 suite 再置空属主）；纠正 draft 口径，引用明确为 live link，保存提示升为必做；聚合模式运行改为平台循环分发 + batch_id 并提前到 P1（带总量上限与幂等键）；维持场景与 suite 双粒度引用；数据集随发布公开；允许被分享人退订；CHECK 改为双方言写法；取消 JSON 与成员表双写 |
| 2026-10-08 | 第三轮 | 砍除 Idempotency-Key（改为前端防抖 + **同 suite 整体**未终态批次 409）；属主下架公共 suite 成员改为连带下架；四条待核实关闭；publicize 通知单 type 双文案；总量上限预计算复用 total_runs；§4 授权蔓延对冲措辞修正。文档自 Downloads 迁入仓内 |
| 2026-10-08 | 第四轮 | 防重 409 范围收窄为 (suite, 发起人)（第三轮的「同 suite 整体」口径废弃——会互相阻塞并泄露他人执行）；batch_id 改 `suite-<sid>-<uid>-<uuid>`；加 `SUITE_RUN_STALE_HOURS` 时效窗口（核实无批次级取消入口）；**事务级 pg_advisory_xact_lock 消竞态 + text_pattern_ops 前缀索引**（后两者均被推翻，见第五、六轮）；公共 suite 加私有成员走发布确认框；§9 补 suite publish/unpublish 端点；服务绑定待核实关闭；`forked_at` 统一为 `forked_from_at` |
| 2026-10-08 | 第五轮 | advisory lock 改**会话级**（核实 `enqueue` 自决 commit，事务级在首个成员提交即释放——会话级方案后又被第六轮推翻）；防重查询简化、text_pattern_ops 索引取消（owner 先收窄走既有复合索引——**第四轮的索引方案就此废弃**）；§10 补 admin 下架 suite 本体的通知 + 审计行；状态枚举核实五值无中间态；`SUITE_RUN_STALE_HOURS` 配置注释加调参耦合说明 |
| 2026-10-08 | 第六轮 | **会话级锁也被推翻：与连接池冲突**——Session 在 commit 后归还连接（`app/core/db.py:20-31`，QueuePool 10+20），unlock 落错连接致锁泄漏、被池复用的连接永久挡住他人，pgbouncer transaction 模式下会话级锁直接失效；连同事务级两级均不可用，终局拍板 **PG/SQLite 同一降级口径不加锁、接受良性竞态**，专用锁连接方案入不做表。异常语义补全：循环内逐成员 try/except，基础设施异常与校验失败同入 skipped，正常返回部分结果；§13.4 三条标注为实现期顺手确认 |
| 2026-10-08 | 第七轮 | **循环前物化**：`rollback()` 总是使 Session 内已加载实例过期（`expire_on_commit=False` 只管 commit），async 下访问过期属性触发懒加载抛 `MissingGreenlet`——成员快照与方案参数必须循环前取成纯值。**异常归类按落库事实**：核实 `dispatch_run` 在 enqueue 提交后仅剩 `ensure_workers()` 与响应构造（`run_dispatcher.py:873-876`），窗口非零——except → rollback → 重查该成员在本 batch_id 下的执行行：已存在归 `started` 附警告，不存在才归 `skipped`。P1 清单与验收同步 |
| 2026-10-08 | 定稿 | **去轮次化整理**：正文与 §13.1 只保留现行结论，删除全部轮次标注与被推翻的中间口径行（防重整体范围、事务级/会话级锁、text_pattern_ops 索引、退订作为蔓延对冲等——演进以本表第三至七轮为准追溯）；§13.3 去轮次标记；§13.1 重编为 17 条现行决策。评审关闭，开工 P0 |
| 2026-10-09 | 实施进度 | **P0/P1 落地**：P0 全项 + P1 除「场景库批量加入」「场景详情反查展示」两项 UX 尾巴外全部实现（§12 各期实施记录）；0012_suites 迁移已上开发 PG（含迁移顺序修正：组合唯一索引先于 FK 建表）；fanout 计算抽出为 dispatch 与预检共用；SuiteComposer 迁至 /suites/composer、/suites 让位用例组管理页；§13.4 关闭两条。回归：后端 802/802、前端 1141/1141、typecheck 干净。P2/P3 未开工 |
