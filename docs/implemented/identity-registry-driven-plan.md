# 调用身份注册表驱动改造方案(引用即登记 · 圈定即承诺 · 共享即授权)

- **定稿日期**:2026-11-20
- **分支/基线**:`feat/service-registry` @ `916926aa`(+ 未提交 P3 清理:merge_carry_tiers 单源化等)
- **状态**:设计定稿;§9-2 执行不查授权已拍板(2026-11-20),仅余 enforce 时点随阶段 3 定
- **阶段 0 已落**(2026-11-20 傍晚):保存/导入闸(audit 态生产运行,`REGISTRY_ONLY_IDENTITIES=audit`)+ 审计脚本 `scripts/audit_unregistered_identities.py` 出数 —— 21/56 场景带未登记引用,distinct 名仅 2(`sb`×20 bootstrap 种子 + `gitlab`×1);方案绑定期 0。数字判读与落地明细见 `docs/service-registry-progress.md` 阶段 0 章节。
- **阶段 1 已落**(2026-11-20 晚):执行闸白名单(圈定即承诺,§4)——
  `identity_not_circled` 硬门进 `precheck_hard_gate` 同一道门,含 slot
  换用目标比对、行级 @slot 同码、重跑快照照查(`execCircledAliases`)、
  预检 `notCircled` advisory;换用目标前端自动纳入圈定(payloadOf);
  分享缺名提示钉位。生效行口径 = 显式选定 > 本人默认行(默认行也承诺,
  与绑定层「默认不吃」刻意差异),测试钉死。
- **阶段 2(检索面 2c)已落**(2026-11-20 深夜):§3 编排器选取器硬化
  (注册表降级横幅/截断提示/悬空判定域 = 注册表 ∪ 手配待保存名;
  AuthSelectorModal 环境分组)+ UsersCard 双入口重建(§3.3 本案侧:
  检索 = 双源 `GET /auths?source=all`(拍板 #10 项目池 username 对成员
  可见)+ 手配 = authDrafts 通道;快照导入退役 §3.7 护栏接力)+
  双源检索 API(拍板 #10 载体)。enforce 仍待阶段 3 清账(时点已拍板:
  清账完成即切)。明细见 progress doc「阶段 2c」节。
- **前置讨论**:docs/wiring-quality-audit-20261119.md(TOK-03)→ 三决策点讨论 → 用户拍板「勾选 = 执行承诺」+「引用即登记、共享即移交」

---

## 0. 三句不变式与决策背景

> **引用即登记**(编排闸)· **圈定即承诺**(执行闸)· **共享即授权**(移交闸)

用户产品拍板:

1. **勾选本质是执行承诺**——用户勾选的调用身份集合,就是该配置执行场景时被允许动用的身份全集(归一语义,非管理范围);
2. 场景中使用到的凭证引用,**都必须是服务注册里已定义的调用身份**(约束前移到编排/保存时,而非运行时兜底);
3. 场景编排时直接选取注册好的调用身份;**场景共享到项目时,调用身份引用随场景移交**给目标项目。

### 与已拍板决策的关系

| 决策 | 内容 | 在本方案中的位置 |
|---|---|---|
| 决策 1 | 圈定白名单(归一):取用集 ⊆ 圈定集,409 硬拦 | = §4 执行闸,作为第一阶段先上(安全网) |
| 决策 2 | 撤除 `/carry-config?path=` 深链 + 孤儿组件 | 独立批次,不受本方案影响 |
| 决策 3 | 引擎缺会话 fail-fast(带逃生开关) | 独立批次,不受本方案影响 |
| 本方案新增 | 编排闸(§2/§3)+ 移交闸(§5) | 把约束从运行时前移到编排/共享时 |

### 现状核实结论(2026-11-20 亲核)

- **声明侧零校验**:`validate_binding_aliases`(`service_aliases.py:316-341`)挂在场景保存(`scenarios.py:195`)、方案、运行预览、graph 派发五处,但只校验**换用目标**(swap 的 value 侧:存在 + 同基础服务);步骤 `call.user`、模板 `${auth.X}`、setup/teardown 引用完全不校验——「未登记」灰色地带的洞在此;
- **提取器单源现成**:`exec_auth_aliases_of_definition`(`service_aliases.py:402-409`,§3.2 唯一口径,steps ∪ setup/teardown 扫描);
- **`ServiceIdentity.alias_name` 全局唯一**(`models/service_identity.py:44-45`,String(128) unique),模型无可见性/属主字段——实体拷贝方案与全局唯一约束正面冲突,授权表是唯一正解;
- **共享流今天不搬身份**:`project_promotions.py` 的 `analyze` 只报告 slots 清单,`execute_promotion_copy` 只复制场景 payload + carry 值;身份条目、凭证均不随共享移动。

---

## 1. 总体架构

```
编排(CaseComposer 选取器,§3)
  → 保存闸:引用必须 ∈ 注册表(§2,新)      ← 未登记在这里死
  → 导入闸:同口径(§2,新)
  → 执行闸:取用集 ⊆ 圈定集(§4,已拍板)   ← 超圈在这里死
  → 共享闸:引用随场景授权给项目(§5,新)   ← 项目可见性在这里给
  → 凭证解析/池/注入链:零改动
```

**核心设计决定:场景/配置 payload 里的引用保持「条目名字符串」,不改成 id 外键。**

理由:
- 与既有架构决策「条目改名不做、引用键稳定」一致(`docs/service-registry-redesign.md` 已知风险表);
- 快照回放、重放、导入导出、历史数据全链路零迁移;
- 存在性靠闸保证,不靠外键——闸失效的最坏情况退化为现状,不会更糟。

---

## 2. 保存/导入闸(引用即登记)

### 后端

新函数(放 `service_aliases.py`,与 `validate_binding_aliases` 同居):

```python
async def unregistered_identities(db, definition) -> list[str]:
    """声明侧存在性闸:exec_auth_aliases_of_definition(§3.2 单源,
    steps ∪ setup/teardown ∪ 模板扫描)diff 注册表,返回未登记条目名。"""
```

- **挂载点**:
  - `routers/scenarios.py` 场景保存/更新(与 `:195` 现有换用校验同一调用链);
  - `routers/run_schemes.py` 方案保存;
  - `services/scenario_import` 导入(P2-B.6 已把 `call.user` 统一改写为条目名,加存在性一步是自然延伸);
- **错误**:422 `identity_not_registered`,detail 带条目名清单 + 深链建议(「去服务注册登记,或改绑已有条目」);
- **与现有校验的分工**:`validate_binding_aliases` 继续管换用目标(存在 + 同基础服务),新闸管**声明侧存在**——职责互补,同一文件、一次调用链。

### 开关(新配置 `REGISTRY_ONLY_IDENTITIES`)

| 值 | 行为 |
|---|---|
| `off` | 现状,不校验 |
| `audit` | 保存成功,响应带 `warnings` 头,前端黄条提示——**生产先跑此态拿真实数据** |
| `enforce` | 422 硬拦。切换前置 = §6 存量清账完成 |

---

## 3. 编排器选取器(前端)

落点:`composer/ValueSourcePicker.vue`、`composer/UsersCard.vue`、`composer/CaseComposerConfig.vue`(身份引用的现有手输位)。

- 身份引用从手输改**选取器**:按步骤服务列条目(`listAliases({base, q, 分页})`);交互复用 ExecConfigsView v6 的「搜索加入」模式,>200 截断提示同款;
- 保存前前端预校验(本地比对已加载注册表 + 后端 audit 响应);未登记引用标红「✕ 未登记」+ 深链 ServiceAdmin;
- **草稿政策**:audit 态允许保存带未登记引用的草稿(黄条);enforce 态后端拦、前端同步禁存;
- **不做**编排器内联快捷登记(权限面复杂)——一律深链去服务注册页,登记后回来重选;
- 降级:plate 不可达 / 注册表空 → 退手输 + 黄条(与 ServiceAdmin plate 不可达守卫同款)。

---

## 4. 执行闸:圈定白名单(决策 1,第一阶段)

> 场景引用全是真条目之后,执行时仍须由**配置的圈定集**限定本次动用范围。

- **规则**:派发/预检时算出本场景**换用后的实际取用集**(§8.2 标签解析已在 `run_dispatcher.py:1042-1048` 计算,直接复用,不新造),与 `SystemSubConfig.aliases` 比对:
  - 取用集 ⊆ 圈定集 → 放行;
  - 差集非空 → 409,新错误码 `identity_not_circled`,detail 点名差集条目 + 「去配置页纳入」深链;
- **换用目标自动纳入**:换用 upsert 时目标条目自动写入圈定(前端 `payloadOf` 实现,测试钉死)——保证「执行的 = 勾选的」字面成立;
- **存量兼容**:`aliases=[]` 的存量行跳过校验(等同白名单关闭);任何一次保存后 aliases 非空 = 白名单生效(保存即承诺);
- **重跑**:用快照里的 aliases 照查,单一规则不豁免;
- **挂载**:进 `precheck_hard_gate` 同一道门(场景派发 / 预检端点 / 集成装载前);graph/adhoc 随审计批次②的门对齐,不另开第二份实现;
- **行级 `@slot`**:换绑后的取用名一并计入比对集合(同一函数产出,零额外成本)。

**两闸关系一句话**:登记闸管「引用是真的」(保存时死),白名单管「只用我圈的」(派发时死)——直写 API 绕过保存闸的存量脏数据,由白名单在派发兜底,口径闭环。

---

## 5. 共享闸:promotion 身份授权(共享即授权)

### 数据模型(迁移 0064)

```
identity_project_grants(
  identity_id           FK service_identities ON DELETE CASCADE,
  project_id            FK projects           ON DELETE CASCADE,
  source_promotion_id   FK 可空(溯源),
  created_at,
  UNIQUE (identity_id, project_id)
)
```

条目本体**不拷贝**(`alias_name` 全局唯一 + 引用键稳定决策,拷贝在技术上就是死路)。

### 行为

- **analyze**(`project_promotion.py:182` 的 `_referenced_slots` 升级):逐条目输出
  `{条目名, base_service, env 标签, 注册状态, 目标项目已授权?, 项目池账户就绪?}`;
  「身份条目」分区进冲突裁决面板(现在只有 carry conflicts);
- **execute / approve**:对引用条目批量 upsert 授权,`source_promotion_id` 溯源;共享回滚 → 删授权;
- **项目侧呈现**:项目配置页 / 就绪度面板把「共享带来的条目」标出(授权表 join);`InstanceCredentialMatchPanel` 继续做账户就绪引导;
- **凭证不搬**:项目池自助配置。

### 设计决定(2026-11-20 已拍板:照默认口径)

**执行解析不查授权表**——身份按全局注册表解析照旧,授权是纯管理面概念(可见性 / 呈现 / 审计)。

- 理由:起步零执行链风险;全局唯一名解析天然命中;
- 升级路径:将来若要「项目只能动用被授权的身份」这个硬边界,在 §4 白名单里叠加授权过滤即可,成本约 +1 天(见 §9 开放问题)。

---

## 6. 存量清账(enforce 前置)

1. **审计脚本** `scripts/audit_unregistered_identities.py`:遍历场景 + 方案 payload → 单源提取器 → diff 注册表;输出分布(多少场景、多少个未登记条目名、按系统分组)——**这个数字决定清账是半天还是几天**;
2. **迁移向导**(一次性管理页或 CLI):每个未登记条目二选一——
   - **登记为新条目**(选 base_service / env / ref 模式);
   - **改绑已有条目**(重写 payload 引用,逐场景确认;走既有场景更新链留修订记录,不裸改库);
3. 清账完成 → 开关切 `enforce`。

---

## 7. 测试矩阵(新增部分)

| 闸 | 用例 |
|---|---|
| 保存/导入闸 | 合法通过 / 未登记 422 / 模板 `${auth.X}` 引用命中 / setup-teardown 引用命中 / audit 放行带警告 / 导入同口径 |
| 执行闸 | 差集 409 / 换用目标自动纳入 / 存量空集跳过 / rerun 快照照查 / graph 与 adhoc 对齐 / 行级 @slot 计入 |
| 授权 | analyze 呈现 / approve 写授权 / 回滚删授权 / 条目删除级联清授权 / **执行不查授权(回归钉)** |
| 选取器 | 搜索加入 / 未登记标红 / plate 不可达降级 |
| 清账 | 登记与改绑两路的 payload 重写断言 |

---

## 8. 交付批次与工作量

| 阶段 | 内容 | 工作量 | 依赖 |
|---|---|---|---|
| **0** | 审计脚本 + audit 态保存/导入闸 | 1 天 | 无 |
| **1** | 执行闸白名单(决策 1 全部内容) | 2–3 天 | 无(与阶段 0 并行) |
| **2** | enforce + 编排器选取器 + 存量清账向导 | 4–6 天 | 阶段 0 的存量数据 |
| **3** | promotion 授权(迁移 0064 + analyze + approve + 项目呈现) | 2–3 天 | **✅ 2026-11-21 提前建表落**(与本案阶段 3 并行):0064 live 已升级 + analyze `identityEntries` 分区 + execute/approve 批量 upsert(直通路径「不落申请行」→ 溯源 NULL)+ reject/withdraw revoke 兜底 + PromotionDialog 分区呈现;执行解析不查授权表(拍板照默认口径) |
| 并行 | 决策 2 撤深链(0.5 天)、决策 3 引擎 fail-fast(1 天 + 存量对账) | 独立 | 无 |

关键路径:0 → 2 → 3,合计约 7–10 天;阶段 1 随时可插。

---

## 9. 风险与开放问题

| # | 项 | 说明 | 处置 |
|---|---|---|---|
| 1 | enforce 时点 | 由阶段 0 的存量分布决定;未登记引用量大则长期 audit + 白名单兜底,enforce 缓行 | **已拍板(2026-11-20):阶段 3 清账完成即切 enforce** —— 阶段 0 数据(21/56 场景带未登记引用,distinct 仅 2 名 `sb`×20 bootstrap 种子 + `gitlab`×1;方案绑定 0)否决「长期 audit」假设,清账 ≈ 半天 |
| 2 | **执行是否查授权**(§5) | 默认不查(管理面起步,零风险);硬边界「项目只能用被授权的身份」为可选增强(白名单叠授权过滤,+1 天) | **已拍板(2026-11-20):默认不查**;**✅ 2026-11-23 销问:维持默认不查,硬边界增强不立项**(重开条件 = 出现越权实例诉求;收尾排布 docs/wrapup-plan-20261123.md 批次 0-3) |
| 3 | 编排器内联快捷登记 | 不做(权限面复杂),深链即可 | 有诉求再开 |
| 4 | 选取器规模 | 注册表 >200 分页截断已有先例(v6 模式),复用 | — |
| 5 | 与审计批次的关系 | 审计报告批次①②③(能力恢复/安全收口/副作用防护)不依赖本方案,可先行 | 并行推进 |

---

## 附:改动面清单(按文件)

| 文件 | 改动 |
|---|---|
| `backend/app/services/service_aliases.py` | + `unregistered_identities()`(声明侧存在性闸) |
| `backend/app/routers/scenarios.py` | 保存/更新挂闸(audit/enforce 按 `REGISTRY_ONLY_IDENTITIES`) |
| `backend/app/routers/run_schemes.py` | 方案保存挂闸 |
| `backend/app/services/scenario_import` | 导入挂闸(同口径) |
| `backend/app/core/config.py` | + `REGISTRY_ONLY_IDENTITIES` 开关 |
| `backend/app/routers/run_precheck.py` | 硬门 + `identity_not_circled` 分类 |
| `backend/app/services/run_dispatcher.py` | 派发漏斗复用取用集比对(挂同一硬门) |
| `backend/alembic/versions/0064_*` | `identity_project_grants` 建表 — **✅ 0064_identity_project_grants(2026-11-21,live 已 upgrade head)** |
| `backend/app/models/` | + `IdentityProjectGrant` 模型 |
| `backend/app/services/project_promotion.py` | analyze 升级(条目明细)+ execute/approve 写授权 — **✅ 已落(2026-11-21)** |
| `backend/app/routers/project_promotions.py` | 裁决面板数据面(身份条目分区) |
| `frontend/src/components/composer/ValueSourcePicker.vue`、`UsersCard.vue`、`CaseComposerConfig.vue` | 身份引用选取器 + 未登记标红 + 降级 |
| `frontend/src/views/ExecConfigsView.vue` | 换用目标自动纳入圈定(`payloadOf`);409 深链一键纳入 |
| `frontend/src/components/project/ProjectConfigPanel.vue` 等 | 「共享带来的条目」呈现 |
| `scripts/audit_unregistered_identities.py` | 新建:存量分布审计 |
