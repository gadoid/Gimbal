# IO 声明归一化设计 — declarations 唯一真源(schema_ / fields / carry 三轴收敛)

> 状态:待用户审阅
> 日期:2026-09-01
> 前置:carry 存储与注入设计(2026-08-31,分支 feat/carry-fields-storage-injection 已落地)
> 本轮为独立架构轮,不基于 carry 分支提交续作。

---

## 0. 背景与动机

### 0.1 现状:三轴并行

plate 端点契约(`gimbal_plate/schema/endpoint/io_spec.py`)用一个接口的 IO 声明拆在三根轴上:

| 轴 | 形态 | 语义 |
|---|---|---|
| `fields: list[IOFieldBinding]` | 扁平绑定清单 | 表单绑定字段(请求)/ 展示字段(响应) |
| `carry: dict[path, CarryEntry]` | path 键字典 | 传递面(值在 platform 值表) |
| `schema_: dict \| None` | JSON Schema | 结构契约 + Type C(未声明字段)载体 |

响应侧另有第四根小轴 `assertable_fields: list[path]`(fields 的断言子集注记)。

消费者痛点(动机 B):每个消费方要自己拼装三轴 —— 前端 Canvas 读 fields + schema 做 Type C 差集、读 carry 做徽标;platform 的 carry 面(`service_fields`)、field_defaults 各理解一种键;新增"看一个端点全部声明"的消费场景必须三处拼接再归并。

### 0.2 历史教训

model 双真源机制(model_schema/model_name 与 schema_ 并行)刚在 carry 轮(T2)退役 —— 第二承重真源必然漂移腐化。本次归一化的本质:**只留一根承重轴,其余降级或派生**。

### 0.3 规模事实(2026-09-01 勘误,形状决策依据)

最初评估"只有 settlement 声明了 fields,迁移 ≈ 0"是**错误的**。全量 grep 结果:

| 事实 | 数量 |
|---|---|
| 声明了 IOFieldBinding 的 fin 端点文件 | 17 / 17 |
| IOFieldBinding 声明总数 | 737 条 |
| `schema_={}`(空 schema)的端点 | 15 / 17 |
| 单文件最大声明量 | order_order_add / order_order_book / order_entrust_order_add 各 ~226 条(备注族 3 键移入 carry 后) |
| 有真实 model schema 的端点 | 仅 settlement_create_order、account_query_balance |
| carry 声明 | 10 条(settlement $.remark + 下单三端点备注族 $.remark/$.notes/$.cancel_remark) |

**基线口径(2026-09-01)**:上表为 fix/carry-faces-all-fin-endpoints(606be60)并回后的链上实测,与事故记录口径(737/10)一致;归一化实现分支从该链开出,golden 基线(P1 前快照)以含全部 10 条 carry 声明的 /full 为准。

且声明的形态是**场景流量提取物**:路径含数组下标(`$.data.data[0].audit_id`)、深层嵌套(`$.data.audit_content.relation_id`)、根路径(`$`);example 携带真实业务值。对这 15/17 个端点,**fields[] 本身就是结构真源,schema_ 是空壳** —— 与 settlement(模型丰富)正好相反。audit_audit_page 揭示第三种用法:schema_ 只装 Type C 补充字段(risk_note)。

### 0.4 被否决的形状(甲:schema + x-io 注记为唯一真源)

基于 0.3 的规模事实,甲形状不可行:

1. **743/747 条声明无 schema 节点可挂**(737 binding + 10 carry 中,仅 settlement 的 4 条有模型节点)—— x-io 标记必须挂在 JSON Schema 属性节点上,而 `$.data.data[0].audit_id`、`$` 根路径在 schema 里没有对应节点;
2. **为存量声明合成嵌套 schema(含数组结构)= /full 的 schema 键内容变化** → 前端 Type C 差集受影响,违反硬性规格 §1.2;
3. **引入虚拟路径旁路字典 = 双真源**,重蹈 model 机制腐化覆辙。

用户已裁定(2026-09-01):**改用 declarations 扁平清单为唯一真源**(本设计)。

---

## 1. 硬性规格(用户钦定)与保证映射

| # | 规格 | 保证机制 |
|---|---|---|
| 1.1 | 前端零强制改动,现有应用实现照常工作 | 既有线上键(body_type/fields/schema/carry/assertable_fields)全量继续发射,形状与语义逐键等价(§4.3);declarations 为纯新增可选键 |
| 1.2 | 后端变更不影响前端 | 同上 —— 唯一线上增量是 declarations 键(可忽略);schema 键内容不变(不做合成) |
| 1.3 | 数据迁移 ≈ 0 | 端点是代码声明非 DB 存储;PG 只存 shape 无关的值与锚点;scenario payload 只带值;P2 构造桥让 17 个端点文件零改动通过(§7 P2) |
| 1.4 | 多层次渲染/导入/导出 full/执行 scenario 结构不受影响 | 派生层让 views/exporter/field_defaults 等属性消费者透明(§4.2);执行链只读线上派生键,结构免疫 |

---

## 2. 目标与非目标

### 目标
1. IO 声明单一承重真源:declarations 扁平清单(请求与响应同构)。
2. fields / carry / assertable_fields 变为按通道的派生投影,全部既有消费者透明。
3. 读写归一:构造侧(declarations= 参数 + declare() 糖)与读取侧(/full declarations 视图 + 派生旧键)走同一存储。
4. 三段可回滚迁移,每段有独立断点与全绿门禁。

### 非目标
1. **不合成、不改写 schema_** —— 它降级为可选伴随(§6 B1),内容与今日完全一致。
2. 不动策略侧描述符(`StrategyFieldDesc`,策略 dim 是另一契约面,仅词汇表对齐)。
3. 不动执行链(carry_injection / run_materialize 读的是 /full 线上派生键)。
4. 不做前端切换(P3 挂账,可选)。
5. 不做声明与 schema 节点的交叉校验(§6 B1 开放点)。

---

## 3. 统一声明模型

### 3.1 DeclarationEntry

新增 pydantic 模型(`io_spec.py`,extra=forbid):

```python
class DeclarationEntry(BaseModel):
    # path/name 校验沿用现行 IOFieldBinding 规则:
    # is_valid_path → normalize($.xxx);name == last_segment(path)
    name: str
    path: str
    channel: Literal["binding", "carry", "view_only"]
    # type 仅 carry 通道必填(六原语词表,沿用 CarryEntry 规则);
    # 其余通道可选(默认 None)—— 与今日 fields 无 type 字段一致,桥编译零增益
    type: str | None = None
    required: bool = True
    default: Any | None = None
    example: Any | None = None
    description: str = ""
    enum: list[Any] | None = None
    ui_kind: Literal["text","number","boolean","select","textarea",
                      "json","file","binary","unknown"] = "unknown"
    source_kind: Literal["independent","lookup","generated"] = "independent"
    # 仅响应侧有意义:True 才进派生 assertable_fields(§6 B3)
    assertable: bool = False
```

通道语义:

| channel | 轴来源 | 语义 |
|---|---|---|
| `binding` | 请求 fields[] | 表单绑定字段(值由场景 step body 提供) |
| `carry` | 请求 carry{} | 传递面(值在 platform 值表,运行时注入) |
| `view_only` | 响应 fields[] | 响应展示字段;`assertable=True` 者为断言目标 |

通道约束(条目级校验):

- `channel=="carry"` → **default 与 example 必须为 None**(§6 B6,D2 后门封死)。桥路线天然合规 —— CarryEntry 本就无值字段,编译产物恒 None;禁令实际约束的是手写 declarations 与 declare() 的节点吸收。enum 不禁 —— 词表约束非值,不触 D2,派生 carry 面天然丢弃;
- `name == last_segment(path)` 对根路径沿用现行行为(`last_segment("$")=="$"`,order_entrust 响应现网已有 name='$' 合法先例),实现带一条 `$` 条目单测。

### 3.2 通道互斥(D4 结构化)

同一 path 在 declarations 内唯一 —— 清单是 list[path 唯一],构造时重复 path 即校验错误。carry∩fields=∅ 由此从"运行时检查"变为"结构性不可能"。

### 3.3 RequestSpec / ResponseSpec 新形态

```python
class RequestSpec(BaseModel):
    body_type: BodyType = "json"
    declarations: list[DeclarationEntry] = []      # ← 唯一承重存储
    schema_: dict | None = Field(default=None, alias="schema")  # 伴随,不参与派生

class ResponseSpec(BaseModel):
    status: int
    description: str = ""
    declarations: list[DeclarationEntry] = []
    schema_: dict | None = Field(default=None, alias="schema")
```

- `fields` / `carry`(请求)与 `fields` / `assertable_fields`(响应)不再是存储字段,是**派生属性**(§4.1)。
- 校验规则迁移见 §5。

### 3.4 declare() 糖(pydantic 优先路线的瘦身入口)

两个类方法,参数按类拆分(canonical 结构同构,分歧只在糖的默认通道):

```python
class RequestSpec(BaseModel):
    @classmethod
    def declare(cls, model: type[BaseModel] | dict, *,
                body_type: BodyType = "json",
                bindings: dict[str, dict | None] | list[str] | None = None,
                carry: dict[str, dict | None] | list[str] | None = None,
                ) -> "RequestSpec": ...

class ResponseSpec(BaseModel):
    @classmethod
    def declare(cls, model: type[BaseModel] | dict, *,
                view_only: dict[str, dict | None] | list[str] | None = None,
                assert_paths: list[str] | None = None,
                ) -> "ResponseSpec": ...
```

展开规则(纯函数,无状态):

- `schema_ = model.model_json_schema()`(dict 直接用);
- 列出的键生成 DeclarationEntry,**元数据从 schema 节点吸收**:type←节点 type、default←节点 default、description←节点 description、enum←节点 enum、required←schema.required 成员;**carry 键跳过 default 吸收**(B6 —— 契约面不带值);example 从来不在吸收清单内;
- dict 值中的键(ui_kind/source_kind/description/…)作为覆写,优先于节点吸收值;
- 未列出的属性不生成声明(Type C 语义不变);
- 默认通道:RequestSpec → `binding`,ResponseSpec → `view_only`;
- `assert_paths` 列出的 path 置 `assertable=True`(§6 B3);
- carry 条目的 type 从节点吸收;节点无 type(如空 schema)时必须显式给出 —— 报告"carry 声明缺 type"构造错误。

**表达力边界(防静默)**:

- **键仅支持顶层属性名**(`schema.properties` 直查)。含 `.` 或 `[` 的键 → 构造错误(嵌套/数组路径请直接手写 DeclarationEntry 或走构造桥);
- **bindings 键必须存在于 schema.properties** —— 查无此键报构造错误,防"吸收落空静默生成全默认值垃圾条目";
- **carry 键可无节点**(B2 镜像:carry 自持),但必须显式给 type。糖对两通道的契约是"binding 必须挂模型、carry 可以自持"。

**type 吸收的通道不对称是刻意的**:declare() 路线全通道吸收 type;构造桥路线 type 仅 carry 必填、其余 None(§6 B5)。不对称只存在于新增的 declarations 键内 —— 旧键(fields)今日本就无 type,线上等价不受影响。

settlement 手写三轴改写示例:

```python
request=RequestSpec.declare(
    CreateOrderRequest,
    bindings={"order_id": None, "amount": {"ui_kind": "number"}, "currency": None},
    carry=["remark"],
)
# remark 的 type="string"、description、default=None 均从模型节点吸收;
# order_id/amount/currency 的 required/description 从模型吸收,不再手写。
```

场景提取路线(order_order_add 等 15 个端点)**不使用糖** —— 扁平清单本就是其自然输入形态,由构造桥(§7 P2)零改动承接。

---

## 4. 派生层与消费者影响面

### 4.1 派生属性(纯 property 现算,不缓存)

```python
@property
def fields(self) -> list[IOFieldBinding]:      # channel ∈ {binding}(请求) / {view_only}(响应)
    ...
@property
def carry(self) -> dict[str, CarryEntry]:      # channel == carry;path → {description, type}
    ...
@property
def assertable_fields(self) -> list[str]:      # 响应:view_only 且 assertable=True 的 paths
    ...
```

- 现算无缓存:端点对象是进程级单例、消费频率低,747 条量级的过滤是微秒级 —— YAGNI,不引入 pydantic 缓存复杂度。
- 返回值视为只读快照(返回新构造对象),调用方修改不影响存储。

### 4.2 属性消费者(全部零改动透明)

| 消费者 | 读取 | P2 后 |
|---|---|---|
| `http/views.py` `_serialize` | spec.fields / spec.carry / spec.assertable_fields | 属性派生,透明 |
| `export/platform.py`(L173/222/237) | ep.request.fields / spec.fields | 同上 |
| `service/field_defaults.py`(L78-92) | request.fields / request.carry / resp.fields | 同上 |
| 前端 Canvas / 平台 carry_injection | /full 线上键 | 线上键由派生属性序列化,逐键等价(§4.3) |

### 4.3 /full 线上视图与兼容表

响应形状(`_serialize` 输出):

```json
// request(旧键全保留 + 新增 declarations)
{
  "body_type": "json",
  "fields": [ ... IOFieldBinding 形状,与今日逐键一致 ... ],
  "schema": { ... 与今日内容完全一致,不做合成 ... },
  "carry": { "$.remark": {"description": "...", "type": "string"} },
  "declarations": [ ... §3.1 全量条目 ... ]     // ← 纯新增,有声明才发
}
// responses["200"](同构)
{
  "status": 200, "description": "成功",
  "fields": [ ... ], "assertable_fields": [ ... ],
  "schema": { ... },
  "declarations": [ ... ]
}
```

| 线上键 | P1 前 | P1 后 | P2 后 | P3 后(可选) |
|---|---|---|---|---|
| body_type | ✓ | ✓ | ✓ | ✓ |
| fields | ✓ | ✓ | ✓(派生) | 移除(前端切 declarations) |
| schema | ✓ | ✓ | ✓ | ✓ |
| carry | ✓ | ✓ | ✓(派生) | 移除 |
| assertable_fields | ✓ | ✓ | ✓(派生) | 移除 |
| declarations | — | ✓ 新增 | ✓(直存) | ✓ |

**等价性锚点**:fields 顺序 = declarations 顺序按通道过滤(桥编译保输入序,与今日 fields 声明序一致);carry 字典键序 = declarations 中 carry 条目序。**declarations 键序约定(P1 view 与 P2 桥两处实现显式遵循同一约定)**:binding/view_only 条目(输入序)在前,carry 条目(输入序)在后。

---

## 5. 校验规则迁移表

| 现行规则(io_spec._validate) | 新家 | 备注 |
|---|---|---|
| path is_valid_path → normalize;name == last_segment(path) | DeclarationEntry 校验(不变) | 逐条声明即逐条校验 |
| enum 非空时 default/example ∈ enum | DeclarationEntry 校验(不变) | |
| carry 键归一 + 归一后重复键检查 | path 唯一性检查(全通道合并) | 覆盖面扩大:任何通道重复 path 都拒 |
| carry ∩ fields[].path = ∅(D4) | **结构性消亡** | 同 path 单通道(§3.2) |
| CarryEntry.type ∈ 六原语 | carry 通道条目校验(不变);其他通道 type=None | |
| assertable_fields ⊆ 归一化 fields paths | 消亡 | assertable 只存在于 view_only 条目上,派生即合法 |
| body_type='none' → schema_ must be None(Rule B) | 不变 | |
| body_type='none' → declarations 必须为空 | **新增**(§6 B4) | 无存量实例 |
| body_type≠'none' → schema_ 非 None(Rule B,{} 算声明) | 不变 | schema 伴随轴独立校验 |
| —(新增) | channel=="carry" → default/example 必须为 None | B6:桥路线天然合规(CarryEntry 无值字段);爆炸半径仅手写声明与 declare() 吸收 |

---

## 6. 语义裁定(逐条带代价)

| # | 裁定 | 理由 | 代价 |
|---|---|---|---|
| B1 | **schema_ 降级为伴随**:不参与派生、不交叉校验、内容不动 | 今日本就无交叉校验(settlement 的 description 双写是现状);合成/校验都会破硬性规格 1.1/1.2 | schema 与声明可能漂移 —— 开放点挂账(§11),declare() 路线天然一致 |
| B2 | **carry 保持自持**:type 声明内携带,不要求 schema 节点 | 与今日 CarryEntry 语义一致;甲形状下"必须挂节点"的收紧不再需要 | 无(settlement 的 remark 节点仍在,仅为伴随展示) |
| B3 | **assertable 覆写键,默认 False** | 今日缺省 assertable_fields=[] —— 默认 False 才能派生回空,保线上等价 | 声明"可断言"须显式(assertable=True 或 declare(assert_paths=...));存量 3 处显式写有的零损失 |
| B4 | **body_type='none' → declarations 必须空** | 无 body 的端点声明字段无意义;今日无存量实例 | 理论收紧,零实际影响 |
| B5 | **type 仅 carry 通道必填** | 今日 fields 无 type 字段;桥编译不做信息发明 | binding/view_only 条目类型信息仍靠 ui_kind 近似(与今日一致) |
| B6 | **carry 通道禁值**:default/example 必须为 None;declare() 对 carry 键跳过 default 吸收 | D2(2026-08-31 carry spec 钦点"契约只声明字段面,值全收 platform")—— 同构字段若不封,`channel="carry", default="压测-张三"` 结构合法,值回流 plate;declare() 吸收会无声带值 | 手写 carry 条目失去 example 文档位(今日 CarryEntry 本就无此字段,零实际损失);enum 不禁(词表约束非值) |

---

## 7. 三段迁移(α 序:先统一读者,再翻转写者)

### P1 — 读侧统一(线上加 declarations,platform 切读)

**内容**:
1. io_spec 增加 `declarations_view()` 派生方法:从**现行** fields/carry 存储生成 §3.1 形状条目(请求 fields→binding、carry→carry;响应 fields→view_only + assertable∈assertable_fields);
2. `_serialize` 与 views.py /full 输出新增 declarations 键;
3. platform 切读(消费面归一,动机 B 落地):carry router `service_fields`(app/routers/carry.py)从 carry 键切到 declarations;
4. 前端零动(忽略未知键)。

**裁定:carry_injection 不切**。它虽也读 /full carry 面,但是运行时关键路径,单轴消费、无重推导痛点;切 declarations 零收益、带执行链等价风险。carry 键在 P3 前恒发,留在旧键上直至 P3 一并处理。

**门禁**:plate 451+ / backend 345+ / frontend 401 全绿;新增 golden 测试 ①(见 §8)。
**断点与回滚**:线上只增不减;回滚 = platform 读键切回 + 删 declarations 输出。

### P2 — 存储翻转(declarations 成为真源,构造桥保 17 文件零改动)

**内容**:
1. DeclarationEntry 模型落地;RequestSpec/ResponseSpec 存储字段切换为 declarations + schema_ 伴随(§3.3);
2. **构造桥**:构造函数继续接受 fields=/carry=/assertable_fields= 旧参数,以 `model_validator(mode="before")` 在存储前逐条编译为 DeclarationEntry(请求 fields→binding、carry→carry 保序;响应 fields→view_only,assertable_fields 成员置 assertable=True);declarations= 与旧参数二选一,同传报构造错误;
3. fields/carry/assertable_fields 变为派生属性(§4.1),属性消费者透明;
4. declare() 糖落地(§3.4),含单测;
5. settlement_create_order 迁移为 declare() 写法(showcase,验证糖的端到端等价);**迁移时以覆写保住今日线上串**(如 carry description"备注(随请求传递,不进表单)"≠ 模型节点 description,不带覆写会无声漂移),等价由 golden ③ 锁;其余 16 文件经构造桥零改动;
6. golden 测试 ②③(见 §8)。

**门禁**:三套件全绿 + golden 全绿。
**断点与回滚**:旧线上键照发(派生),前端无感;回滚 = revert P2 提交(构造桥使新旧写法并存,无数据迁移)。

### P3 — 拆旧键(可选,挂账)

前端切读 declarations → 移除构造桥与旧线上键(fields/carry/assertable_fields)→ 移除 IOFieldBinding/CarryEntry 对外导出(内部保留为派生投影的返回类型)。**仅在用户明示启动时执行**;不启动则桥长期承重(spec §9 钦点同款先例)。

---

## 8. 测试矩阵

| # | 测试 | 内容 | 阶段 |
|---|---|---|---|
| ① | /full 逐键相等 golden | P1 前后,全部 17 端点(加 account 共 18)的 /full JSON:既有键逐键相等,新增仅 declarations | P1 |
| ② | 桥构造等价 golden | **16 个桥路线端点**(settlement 除外,走 ③)零改动经桥构造 → /full 与 P1 基线**全键**逐键相等(既有键 + declarations;锁 fields/carry/declarations 三处序) | P2 |
| ③ | declare() 等价 golden | settlement 迁移后:(a) 既有键与 P1 基线逐键相等(锁覆写保串);(b) 手写 declarations(含节点吸收值与覆写)与 declare() 输出全键相等。**②③ 基线不混用**:② 的 binding 条目 type 恒 None(桥不吸收),③ 的 type 恒吸收值 —— 混用必假阳性 | P2 |
| ④ | 派生==手写 | declarations 手写 → 派生 fields/carry/assertable_fields == 直接构造旧参数的投影 | P2 |
| ⑤ | 通道互斥与守卫 | 重复 path(含跨通道)→ 构造错误;body_type=none + 声明 → 错误;**carry 条目带 default/example → 构造错误(B6);根路径 `$` 条目构造与派生** | P2 |
| ⑥ | assertable 语义 | 缺省派生 assertable_fields == [];显式 True 才进;audit_detail 的 audit_id(声明但未断言)桥编译后保持 False | P2 |
| ⑦ | declare() 展开规则与边界 | 节点吸收(type/default/description/enum/required)、覆写优先、未列出=Type C、carry 缺 type 报错;**carry 键不吸收 default;键含 `.` 或 `[` → 报错;bindings 键查无 schema.properties 节点 → 报错** | P2 |
| ⑧ | 既有三套件 | plate 451 基线 / backend 345 / frontend 401 + typecheck,允许 ±新增用例数 | P1/P2 |

---

## 9. 风险表

| 风险 | 缓解 |
|---|---|
| fields 顺序漂移(前端表单渲染序) | 桥编译保输入序;golden ② 锁序 |
| 派生属性性能 | 现算微秒级,进程级单例,消费低频(§4.1);如实测热点再缓存 |
| pydantic v2 property 与序列化 | fields/carry 不再是模型字段 → `model_dump` 不含它们;`_serialize` 本就是手写 wrap(线上键显式拼),不受影响;测试 ①② 锁线上形状 |
| platform P1 切读的版本错配 | 同仓同部署内网单体,无错配窗口 |
| 构造桥长期滞留变成新兼容债 | P3 挂账显式可执行;桥是编译语义(旧参数→canonical)而非并行真源,不产生第二承重轴 |
| `$` 根路径/数组下标路径的派生 | 本就是扁平 path 一等公民,path 校验沿用 is_valid_path,无节点依赖 |

---

## 10. 验收清单

- [ ] /full 既有键(body_type/fields/schema/carry/assertable_fields)对全部端点与 P1 前逐键相等(测试 ①②③a);
- [ ] **declarations 键被 golden 全键锁定**(16 桥路线端点 P1→P2 逐键相等,测试 ②;唯一已切换消费者 service_fields 的读取面稳态);
- [ ] declarations 视图覆盖全部 747 条存量声明(737 fields + 10 carry),channel 映射正确(测试 ①④);
- [ ] **carry 通道 default/example 封死有单测**,declare() 对 carry 键不吸收 default(测试 ⑤⑦,B6);
- [ ] 17 个端点文件在 P2 提交里零 diff(桥承接;settlement 除外,迁 declare());
- [ ] settlement declare() 写法与手写线上等价,覆写保串(测试 ③);
- [ ] 通道互斥/body_type 守卫/assertable 缺省语义/declare 边界报错有单测(测试 ⑤⑥⑦);
- [ ] 三套件门禁全绿(测试 ⑧);
- [ ] platform 消费面已归一到 declarations(P1 切换完成,carry 面 service_fields 走新键)。

---

## 11. 挂账(P3 及开放点)

1. **P3 拆旧键**(可选):前端切 declarations → 移除构造桥与旧线上键。未启动前桥承重。
2. **schema 伴随与声明的交叉校验**(开放点):B1 裁定不做;若未来漂移成痛,再立项"一致性 lint"(非运行时校验)。
3. **binding/view_only 条目的 type 增强**(B5 余项):若前端控件渲染需要真类型,再扩 type 到全通道 —— 届时 declare() 已在吸收,存量靠一次性脚本补齐。
4. **StrategyFieldDesc 同构化**:策略 dim 描述符词汇表与 DeclarationEntry 对齐问题,另一契约面,独立轮。
