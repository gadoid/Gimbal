# 填充字段存储：endpoint 默认值 + 零配置默认 + 出现即配置

- 日期：2026-08-31（设计定稿；同日修订：默认态从"落库快照"改为"零配置 + 运行时补全"）
- 状态：**设计已确认（修订版待复核），待实现**
- 关联：`PRD-case-composer.md` §5.4 / §5.5 / §11 开放问题 #2 #3、`FIELD-UI-MAPPING.md` §3.5、`PLATE_V3_DESIGN.md` §7.2

## 背景

- 接口请求字段规模：**单请求 100-200 个字段，其中 50-60 个不需要业务配置**——它们是
  保证业务过程完整性的"填充字段"（如订单中的商品明细信息）。
- **用户裁决（2026-08-31，本设计的核心约束）**：填充字段"**写不写都完全不影响业务**"
  ——是否配置它们、配置成什么值，对业务结果零影响；但**可配置的能力必须保留**。
- 由此推出三条硬需求：
  1. **默认需要传递**：接口要求这些字段出现在请求里（缺了请求不完整）→ 运行时必须补全后发出；
  2. **值无业务含义** → 默认态**零配置**：不落库、不变量、不进数据集，无任何管理负担；
  3. **可配置** → 保留唯一配置通道：body 里出现 key 即显式配置。
- 修订动机：初版设计的"物化全量快照落库"强迫每个场景持久化 50-60 个无人关心的值，
  正是要消除的噪音，取消；可复现性让位于低噪音（业务无关字段的漂移无害）。

## 已确认的关键决策

| 决策点 | 结论 |
|---|---|
| 出厂默认值住在哪 | endpoint 定义（`schema_.properties[*].default` / `model` JSON Schema default），按 **Type C 处理（不进 `fields[]`）** |
| 默认态 | **零配置**：不出现在 `body` / `config.vars` / 数据集；运行时从 endpoint 默认补全后发出 |
| 配置态 | **出现即配置**：body 里写 key（字面量或 `${var.xxx}`）= 显式覆盖，唯一配置点 |
| 落库 body | 最小化：只含业务字段引用 + 显式配置 + 临时字段 |
| 补全时机 | 运行分发（materialize/convert 链）+ 前端展示（读 fields_meta 默认值）——**不在落库层物化** |
| 默认值缺失时填什么 | **null**（拍板 PRD §11 开放问题 #3） |
| 是否新增存储结构 | **否**。不加 `schema_fields` 等平行值容器；Type C 元数据以派生条目进现有 `fields_meta` |
| 快照语义 | **取消落库快照**：endpoint 默认演进自然跟随到后续运行（业务无关，漂移无害）；单次运行的审计由 run 物化副本承担 |
| 向后兼容 | 已落库场景 body 中已有的值 = "出现即配置"，语义不变，无需迁移 |
| 填充字段是否变量化 | **否**。它们不参与任何一致性约束（见下节） |

## 设计

### 三层存储模型

```text
┌─ 出厂层 endpoint（plate 仓库，共享资产，单一真相）
│    填充字段的声明 + 默认值：schema properties 的 default
│    不进 fields[] → 前端不进主编辑区 → 折叠"附带字段"区
│    endpoint 改一次默认值，此后所有运行即时受益（无快照滞后）
│
├─ 实例层 steps[*].request.body（最小化，只存意图）
│     body 出现 key = 用户显式配置（字面量或 ${var.xxx}）
│     缺席 = 运行时补全出厂默认
│     50-60 个填充值不进持久层 → 落库 JSON 只表达业务意图
│
└─ 变量层 config.vars（只收业务字段）
     仅存放被 ${var.xxx} 引用、参与跨 step 一致性或复用的业务字段值
     填充字段永不进入
```

### 补全链路（按时机分布，唯一补全函数多处调用）

```text
优先级：body 已填（含显式配置）→ 绑定: IOFieldBinding.default
                                 → 未绑定(Type C): properties[k].default
                                 → 绑定: IOFieldBinding.example
                                 → 未绑定(Type C): properties[k].examples[0]
                                 → null
```

| 时机 | 行为 |
|---|---|
| 导出（plate → platform dict 落库） | body **原样透传**（不物化补全）；`fields_meta` 携带绑定条目 + Type C 派生条目（含 default / example / ui_kind） |
| 前端编辑 | 折叠"附带字段 (N)"区从 `fields_meta` 渲染，endpoint 默认值以 placeholder 灰显；**未编辑的 key 不提交**（保存的 body 保持最小） |
| 运行分发 | `materialize_run_copy`（执行/导出共用的唯一物化点）新增补全步骤：查 endpoint catalog（service + method + path）→ 按优先级链补全；非 dict body 直通 |
| gimbal 引擎 | **零改动**：收到的 run 副本 body 已补全完整 |

实现要点：

1. **Type C 属性集合** = `ep.request.json_schema().properties` 的 key − `fields[*].name`；
   `RequestSpec.json_schema()` 已统一 `model` / `schema_` 两种来源。
2. **嵌套属性不展开**：仅顶层参与补全（与 `_bindings_from_model` 顶层-only 约定一致）。
3. **补全函数单一实现**：导出侧与运行侧调用同一函数（plate 暴露，platform backend 引用），
   避免两处优先级链漂移。
4. **run 副本审计**：物化后的 run 副本随执行记录留存（现状行为），单次运行可复现。

### fields_meta 派生 Type C 条目

- 把 `_bindings_from_model`（`schema/endpoint/io_spec.py`）的
  "JSON Schema property → IOFieldBinding"派生逻辑提取为共享 helper，`schema_` 来源复用。
- 派生条目与绑定条目同构共存于 `fields_meta`（`ui_kind` 按 property type 推导），
  前端零新结构；折叠集识别：`fields_meta keys − endpoints[*].request_fields`（均已下发）。
- 量级权衡（已接受）：单 step 的 fields_meta 携带全部字段条目（100-200 个），
  PLATE_V3_DESIGN §7.2 方案 C 既有决策的延伸（O(1) 查询换重复）。

### 跨接口数据一致性（简化）

填充字段**完全不参与一致性**（写不写都不影响业务）。一致性只涉及业务字段，走既有机制：

| 业务字段身份 | 例子 | 机制 |
|---|---|---|
| 过程中产生的实体引用 | step1 建单的 order_id，step2 查单用 | Extract → `config.vars` → `${var.xxx}`；引擎单点解析，同 run 同值 |
| 预置共享业务值 | customer_id | `config.vars` 单一来源；`--var` 覆盖均匀生效 |

判据：一个字段若需要与其他 step 对齐值，它就是**业务字段**，走"出现即配置"通道写
`${var.xxx}` 升级为变量——不需要数据模型区分，值怎么写（字面量 vs 引用）即身份。

### 明确不做的事

- ~~物化全量快照落库~~（初版方案，已修订取消）：强迫持久化 50-60 个业务无关值，
  与"零配置"裁决冲突。
- 不引入 `schema_fields` 轻量值容器：双值载体合并税、同名冲突规则、
  `fields_meta` 平行类弯路的前车之鉴（PLATE_V3_DESIGN §7.5）。
- 不把填充字段播种进 `config.vars`，不进常量池。
- **不在数据集（DataSet）里加非绑定字段列**（2026-08-31 讨论裁决）：数据集是数据驱动的
  参数化行（行键 ⊆ `config.vars` 调色板，adaptation 批次/回滚建立在"数据集列 = 变量"上），
  填充字段是 step 级常量——层级错位、语义污染（常量进按行变化的表）。业界对照
  （OpenAPI default/example、Postman body 模板、JMeter Sampler+CSV、factory_boy）共识：
  已知良好请求值住在接口定义，参数化表只放变化维度。
- 不做"附带字段默认不发出、手动开关"（PRD §5.5 的开关留待真需要时再议）。
- 不在 `RequestSpec.schema_`（endpoint 定义）里存实例值：schema 描述形状、scenario 存实例。
- 一致性 lint（"同名字段一处引用一处字面量"告警）为可选后续项，不阻塞本期。

## 影响面

| 位置 | 改动 |
|---|---|
| `Gimbal/src/gimbal-plate/gimbal_plate/export/platform.py` | `_render_request_view`：body 透传（停止物化 full_body）+ fields_meta 增加派生 Type C 条目 |
| `Gimbal/src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py` | 提取/新增 property → IOFieldBinding 派生共享 helper |
| plate 补全函数 | 新增单一补全函数（优先级链实现），导出/运行共用 |
| `Gimbal/src/gimbal-platform/backend/app/services/run_materialize.py` | 新增补全步骤：endpoint catalog 查询 + 调用补全函数 |
| 平台前端 | 折叠区 placeholder 渲染 + **未编辑不提交**契约 |
| `Gimbal/tests/plate/test_v3_export_platform.py` | 方案 C 测试调整：导出不再物化 body、fields_meta 含派生条目 |
| `Gimbal/src/gimbal-platform/backend/tests/` | 新增运行补全测试（materialize 后 body 完整） |
| `Gimbal/docs/PRD-case-composer.md` | §11 开放问题 #3 状态更新为"已约定：null" |
| `Gimbal/docs/FIELD-UI-MAPPING.md` | §3.5 缺口段落更新 |

## 测试计划

1. **导出不物化**：endpoint `schema_` 声明 `goods_name`（带 default）未绑 →
   platform dict 的 body **不含**该 key；`fields_meta` 含派生条目（ui_kind=text、default 带出）。
2. **运行补全**：同上场景经 `materialize_run_copy` → run 副本 body 含 `goods_name = default`。
3. **null 兜底**：Type C 属性无 default / example → run 副本值为 null。
4. **出现即配置**：body 显式写 `goods_name="x"` → run 副本用 `"x"`，不取默认。
5. **非 dict body**：`body: "raw text"` → 直通不补全。
6. **向后兼容**：已落库的全量 body 场景 → 补全不覆盖已有值，行为不变。
7. **round-trip**：platform dict → `Scenario.model_validate` → `GimbalScenarioExporter.to_dict()`
   → gimbal dict body 最小可执行、无 fields_meta；经运行补全后完整。
