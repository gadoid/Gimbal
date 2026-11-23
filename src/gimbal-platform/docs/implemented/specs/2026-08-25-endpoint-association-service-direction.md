# 用例↔接口关联服务方向(基于 Plate 组件派生)

日期:2026-08-25
状态:方向文档(设计已裁定,未排期;重放/流程追踪开工时按此执行)
范围:gimbal-platform 资产域倒排索引的追加式扩展,及其派生的三个下游服务方向。
上游依据:`2026-08-21-asset-domain-complete-design.md`(存储 × 适配 × 数据集主设计,本文是其索引章节的方向延伸)。

---

## 1. 定位

Plate 的组件化模型(步骤 `api.view_hints.endpoint_id` 挂接目录身份、`EndpointSpec` semver 版本目录)使平台天然具备「用例 ↔ 接口」的第一类关联。本文记录:

1. 关联能力的现状盘点(哪些已落地、什么形状);
2. 一项已裁定的追加式扩展(步骤级存在性索引);
3. 三个基于该关联能力派生的下游服务方向:**业务流程接口追踪、Apidoc 式变更影响、业务过程重放**。

本文不排期、不动代码;它是后续派生服务的实现方向锚点。

## 2. 现状盘点(均已落地)

| 能力 | 载体 | 形状 |
|---|---|---|
| 字段级倒排索引 | `scenario_endpoint_refs` | PK `(scenario_id, step_index, source, field_name)` → `endpoint_id` + `via_var`;`ix_ser_endpoint` 反查索引 |
| 索引维护 | `services/endpoint_ref_index.py` | `sync_scenario` / `drop_scenario` 写路径同事务删旧插新(scenario_store 三处挂点);`rebuild` 全量重建;`unindexed_steps` 只读警示 |
| 反向影响查询 | `GET /adaptations/impact` | endpoint(可再按 field)→ 受影响清单(场景/步骤/字段/模板变量/数据集列配对);admin-only |
| 变更检测与批次 | 适配中心全链路 | `catalog/diff` 对版本戳 → 开批次存档 → ops 草案 → apply/rollback |
| 重放的身份前置 | 认证改造(2026-08-25) | config.users / 凭证池 / auth_sessions include_secrets 按需解密 |
| 重放的执行前置 | 执行链加固 P1-P9 | 证据落盘 / JSONL 异步 / 取消 / reconcile / 保留期清扫 / 容量闸 |

**关键性质(源存果算):** payload 是唯一事实源,索引是纯派生态——任何时刻可 drop 后 `rebuild` 重建,与逐行维护结果一致。

## 3. 字段级索引的边界(为什么需要追加扩展)

`parse_refs` 只在 `body`/`headers` **有字段时**才出行。因此:

> 调用了接口但零字段的步骤(典型:无参 GET)在字段级索引中**完全无行**。

这对适配分析是可接受的(无字段即无字段变更可影响);但对下列下游场景,步骤级的存在性关系必须可靠,否则「该流程涉及 8 个接口」会数成 6 个:

| 下游场景 | 需要的粒度 | 依赖方向 |
|---|---|---|
| ① 业务流程 → 涉及接口清单 | 步骤级 | 正向:scenario → endpoints |
| ② Apidoc 式变更影响 | 字段级(**现有 impact 已闭环**) | 反向:endpoint → scenarios(步骤级补充:接口整体下架/重定时,零字段步骤也要浮出) |
| ③ 业务过程重放 | 步骤级 + 执行器 | ①+② 的输出 × 执行链 × 认证 |

## 4. 已定决策(ADR,2026-08-25 裁定)

| # | 决策 | 理由 |
|---|---|---|
| A1 | **字段级索引保持不动** | 它就是为版本管理(适配分析)设计的正确形状,不欠任何债 |
| A2 | 步骤级存在性 = **追加式兄弟表 `scenario_step_refs`**,不用同表哨兵行 | 哨兵行(`field_name=''`)会漏进 `impact()` / `open_batch()` 的字段级消费,所有读点永久背 `WHERE field_name != ''`,漏一处是静默数据错误;兄弟表让现有读点零改动。写侧集中一处 vs 读侧处处设防,前者总成本低,且随消费者增加差距拉大 |
| A3 | 两表维护**不构成双写一致性问题** | 同一事实源(payload)、同一派生函数(`parse_refs` 一并产出)、同一事务(要么都落要么都不落);`rebuild` 是终极对账。经典双写漂移(DB+ES)的前提——独立存储、独立失败——在这里不成立 |
| A4 | 写路径增量 = `sync_scenario`/`drop_scenario` 各 +1 条 DELETE、`parse_refs` 一并产出两类行 | 全部收在 endpoint_ref_index 一个模块内,`scenario_store` 调用点与签名零改动 |
| A5 | **时机灵活:到点再加,不必前置到 PG 迁移前** | 派生层随时可 rebuild,后加与前加成本完全一致;规模约万级用例(×十来步 ×若干字段 ≈ 几十万行),成本可忽略 |
| A6 | 「补索引」指的是**产出行的派生结构**,不是 DB 索引 | 盲区是「行不存在」而非「查得慢」——零字段步骤一行不出,加多少 B-tree 都捞不出 |

## 5. 目标形态

### 5.1 存储结构(追加)

```sql
CREATE TABLE scenario_step_refs (
    scenario_id TEXT   NOT NULL,   -- 与 scenario_endpoint_refs 同源同事务维护
    step_index  INTEGER NOT NULL,  -- definition.steps 下标(编排顺序)
    endpoint_id TEXT   NOT NULL,   -- api.view_hints.endpoint_id
    PRIMARY KEY (scenario_id, step_index)
);
CREATE INDEX ix_ssr_endpoint ON scenario_step_refs (endpoint_id);
```

无 FK、无生成列,与主设计 D1/D4 纪律一致;整表可 drop 后由 `rebuild` 重建。

### 5.2 查询形态

- **步骤级正向(①的主查询,单表)**:`SELECT DISTINCT endpoint_id FROM scenario_step_refs WHERE scenario_id = ?` — 不需要 join,场景名等展示信息由前端列表 store 带;
- **步骤级反向(②的补充、③的影响面)**:`WHERE endpoint_id = ?` — `ix_ssr_endpoint` 直查;
- **合并视图(Apidoc 式影响详情)**:

```sql
SELECT s.step_index, s.endpoint_id, e.source, e.field_name, e.via_var
FROM scenario_step_refs s
LEFT JOIN scenario_endpoint_refs e
       ON e.scenario_id = s.scenario_id AND e.step_index = s.step_index
WHERE s.scenario_id = ?;
```

join 键 `(scenario_id, step_index)` 恰为字段表复合主键前缀,LEFT JOIN 天然保留零字段步骤 — 万级规模下微秒级,性能不构成设计输入。

### 5.3 与 unindexed_steps 的关系

缺 `view_hints.endpoint_id` 的步骤仍不进**任何**一张索引(警示清单 `/adaptations/unindexed-steps` 的既有语义不变)。两表都只覆盖「声明了接口身份」的步骤,这是组件化协作的入场约定,不是索引缺陷。

## 6. 推进顺序

1. **步骤索引(到点再加)**:重放或流程追踪开工时,按 §5.1 建表 + `parse_refs` 扩展 + `rebuild` 一次;先过一轮 brainstorming 定 `parse_refs` 返回形状(元组扩为三类产出)与测试基线;
2. **正向查询端点**:`GET /scenarios/{id}/endpoints`(或挂 adaptation 路由旁),同时裁定权限面 —— 现有 impact 是 admin-only,流程追踪若面向 member 使用需单独放行只读;
3. **重放平台 = 纯编排层**:impact(变了什么、影响谁)× 执行链(怎么重跑)× 认证(以谁的身份跑),不再有新的数据模型债务。

## 7. 与路线图的关系

- 列表服务端化与 PG 迁移:独立线,互不阻塞(索引全派生,迁移 = rebuild);
- 认证改造(2026-08-25)与执行链加固(P1-P9)已就位,重放的前置条件已集齐;
- 本文档记录的方向不改变「下一步存储结构设计」的优先级。
