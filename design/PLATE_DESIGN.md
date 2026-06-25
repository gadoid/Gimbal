# Plate 设计文档

> 感光板（感光板 / Plate）—— GIMBAL 体系中存储被测系统接口结构化契约的静态模块，
> 后续演化为多系统共享的接口真值服务。
>
> 命名取自摄影史上的感光板（底片前身，"被测系统留存在测试系统中的底片"），
> 同时取 base plate（基座）之意，与 Gimbal（稳定取向）、Prism（折射分光）共同构成
> 光学—机械仪器命名链路。本文档对应 `ModelRegistry` → `Plate` 重命名后的目标形态。

> **修订说明（rev.2）**：本版 `FieldBinding` 设计经一份真实抓包（31 端点 / 87 次调用的
> fin 业务流）与一份黄金 scenario（45 步、含 extract/assign 值血缘）校准。关键发现：
> 真实值血缘中 **91% 的字段提取路径穿过列表**（如 `data.to_customer[0].put_amount.
> standard_list[0].order_fee_real_id`），且存在"同字段不同下标"（`data[0]` vs `data[1]`）
> 与"按业务维度选元素"（`main_currency_bank.CNY[0]` vs `.USD[0]`）两类选择。据此**修正**了
> rev.1 的两个设计错误：(1) 元素下标/键的选择是 scenario 级实例信息，**不进** `FieldBinding`；
> (2) "回查探针"是软使用习惯，**不进** `EndpointSpec` 核心字段。详见 §2.2 与 §2.3。

---

## 0. 文档定位

本文档描述 Plate 的**数据模型设计**（字段、类型、约束）与**数据流转**（谁生产、谁消费、
怎么校验）。演进路径（从静态模块到服务化）见配套文档 `PLATE_EVOLUTION.md`。

阅读前需要理解的两条核心原则，贯穿全文：

1. **L1 / L2 分层**：可从抓包/代码自动再生成的"形状契约"是 L1（机器产物，可覆盖重写）；
   只能人工补充的"业务语义标注"是 L2（人工产物，覆盖前必须经人确认）。混在一起会让
   "自动重生成契约"这个动作变得危险。
2. **契约本体 vs 叙述标注**：能写成机器可验证三元组的（如"字段 X 应从接口 Y 的字段 Z 取"）
   属于契约本体，进 `EndpointSpec`；纯叙述性业务背景（如"此字段非空时触发审核"）属于
   叙述标注，进独立的 `EndpointDoc`。

---

## 1. 总体结构

Plate 由两个**独立存储、独立维护节奏**的数据层组成：

```
plate/
├── 被测系统A/                    # service 包(目录名 = 合法 Python 包名)
│   ├── __init__.py              # re-export 本 service 的查询函数
│   ├── models.py                # Pydantic 数据类(request / response 形状)  ← L1
│   ├── endpoints.py             # EndpointSpec 实例(契约本体 + FieldBinding) ← L1
│   └── docs.py                  # EndpointDoc 实例(业务语义标注)             ← L2
├── 被测系统B/
│   └── ...
├── _aliases.py                  # service 名 → Python 包名 的反向映射(兜底)
├── spec.py                      # EndpointSpec / FieldBinding / 三个 hook Protocol
├── doc.py                       # EndpointDoc(L2 注册表的类型定义)
└── core.py                      # Registry:collect / resolve / warm,线程安全
```

层次关系：

| 层 | 物理位置 | 性质 | 维护节奏 | GIMBAL 执行态是否加载 |
|---|---|---|---|---|
| **数据类层** | `models.py` | L1 形状契约 | 可自动再生成 | 是（结构化检查刚需） |
| **契约层** | `endpoints.py` 中 `EndpointSpec` | L1 契约本体 | 可自动再生成 | 是 |
| **绑定层** | `EndpointSpec.field_bindings` | L1 机器可验证依赖边 | 半自动（抓包挖掘 + 人工确认） | 是（静态依赖检查） |
| **文档层** | `docs.py` 中 `EndpointDoc` | L2 叙述标注 | 纯人工 | **否** |

> **关键设计**：文档层（L2）与契约层（L1）物理解耦存储，通过
> `(service, method, path)` 外键关联。GIMBAL 执行时只加载 L1，完全不碰 L2；
> 只有 AI skill 做上下文查询、API doc 站点渲染时才把两层合并展示。
> 这条边界决定了后续服务化时客户端"该缓存什么、该向远端查什么"。

---

## 2. 字段设计

### 2.1 EndpointSpec（契约本体，L1）

单个 endpoint 的契约描述。`@final` + `frozen=True` 的 dataclass：
`@final` 保证拉式收集时可用 `type(attr) is EndpointSpec` 严格匹配（排除继承）；
`frozen=True` 保证实例不可变（锁内取出到锁外用无 TOCTOU 风险）。

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import final
from pydantic import BaseModel


class EndpointCategory(str, Enum):
    """接口在业务体系中的角色分类。给人 / AI 理解和决策用,不构成强约束。"""
    BUSINESS = "business"   # 主业务流程接口(有业务意义的状态变更)
    QUERY = "query"         # 查询接口(返回具体业务实体数据,无业务状态变更)
    TOOL = "tool"           # 工具型接口(系统级能力,与具体业务实体无关)


@final
@dataclass(frozen=True)
class EndpointSpec:
    # —— 数据(必填)——
    method: str                                # HTTP 方法,非空
    path: str                                  # 接口路径,非空

    # —— 分类(新增)——
    category: EndpointCategory = EndpointCategory.BUSINESS
    mutates_state: bool = True                 # 是否产生"有业务意义"的状态变更(见 §3.2)

    # —— 数据(可选)——
    request: type[BaseModel] | None = None     # 请求体模型(GET 类允许 None)
    responses: dict[int, type[BaseModel]] = field(default_factory=dict)

    # —— 绑定(新增,机器可验证依赖边)——
    field_bindings: tuple["FieldBinding", ...] = field(default_factory=tuple)

    # —— 文档元数据 ——
    summary: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)   # 自由标签,与 category 正交
    auth_required: bool = False

    # —— 预留槽位(本期不实装)——
    default_response: type[BaseModel] | None = None
    response_union: dict[int, tuple[type[BaseModel], ...]] = field(default_factory=dict)

    # —— 能力 hook(本期不实装,None = 走通用行为)——
    mock_hook: "MockHook | None" = None
    validate_hook: "ValidateHook | None" = None
    build_request_hook: "BuildRequestHook | None" = None
```

字段分组说明：

| 字段 | 性质 | 作用 |
|---|---|---|
| `method` / `path` | 必填 | endpoint 唯一标识(配合 service 构成 EndpointKey) |
| `category` | 分类标签 | 给消费者判断接口角色;驱动 AI 编排、保活探测、doc 分组 |
| `mutates_state` | 底层事实 | 给 `category` 正确性背书的可验证字段(见 §3.2) |
| `request` / `responses` | 形状契约 | GIMBAL 结构化检查、mock 填充、doc 渲染的数据来源 |
| `field_bindings` | 依赖边 | 字段级取值来源,Capture/AI 直接消费(见 §2.2) |
| `tags` | 自由标签 | 与 category 不冲突的补充维度(如 "需要登录态"、"金额相关") |
| `auth_required` | 元数据 | 喂 mock / 后期 OpenAPI 导出 |

### 2.2 FieldBinding（依赖边，L1，收编进 EndpointSpec）

回答"这个字段的值结构上能从哪个接口来"——一条**机器可验证的生产者-消费者依赖边**。
把 `gimbal-traffic-to-scenario` skill 里现存的 `required_bindings`（靠流量挖掘的
启发式产出）提升为 Plate 的权威契约数据，让 Capture / AI 三方共享同一份真值，
不再各自从流量里猜。

```python
@dataclass(frozen=True)
class FieldBinding:
    """本接口某请求字段的权威生产者声明（契约级、静态）。

    只回答"这个字段能从哪个接口的哪个响应字段取",不回答"取列表里的第几个 / 哪个键"——
    后者是 scenario 级的实例选择,由 skill 的值血缘挖掘负责,Plate 不持有。
    """
    field_path: str          # 本接口 request schema 内的目标路径(逻辑路径,见下)
    source_service: str      # 来源接口所属 service
    source_method: str
    source_path: str
    source_field_path: str   # 来源响应 schema 内的字段路径(逻辑路径,见下)
    note: str = ""           # 可选:为什么 / 何时需要这条绑定
```

**路径格式:逻辑 schema 路径,而非 JSONPath。** `field_path` / `source_field_path` 描述的是
"字段在 Pydantic 模型树里的位置",**透明穿过 list 与 dict-key,不带任何下标和具体键**。

为什么不带下标/键——这是 rev.2 的核心修正。真实值血缘里 91% 的提取路径穿过列表,且出现
"同字段不同下标"和"按业务维度选键"两类选择。这些选择是 **scenario 级的实例信息**(这条流
恰好取第 0 和第 1 个,换条流就不是了),正是本设计反复强调"Plate 不持有、归 skill 值血缘
挖掘"的动态信息。把 `index=1` 固化进 `FieldBinding` 等于把测试用例的偶然选择当成接口的
永久事实,违反 L1 静态契约边界。三层各管各的:

| 信息 | 例子 | 归属 |
|---|---|---|
| **结构形状** | `order_sub` 是 list、`main_currency_bank` 是 dict[币种→list] | `models.py` 的 Pydantic 类型(已有,FieldBinding 不重复记) |
| **键的语义** | "这个 dict 的 key 是币种码" | `Field(description=)` 或 `EndpointDoc.field_notes`(L2) |
| **取哪个元素** | `[0]` / `[1]` / 按 CNY 选 | scenario 的 extract/assign,**Plate 完全不碰** |

路径转换示例(JSONPath → 逻辑 schema 路径):

```
$.data.order_sub[0].order_sub_id
  → data.order_sub.order_sub_id                      # 丢 [0]

$.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id
  → data.to_customer.put_amount.standard_list.order_fee_real_id   # 丢两个 [0]

$.data.main_currency_bank.CNY[0].bank_account
  → data.main_currency_bank.bank_account             # 丢 CNY 键和 [0]
```

逻辑路径配合 `models.py` 的类型即可还原"穿过几层列表/字典"(`order_sub: list[...]`
本身就携带了基数),所以 `FieldBinding` 不需要额外的 selector 字段。

**端到端示例(取自真实黄金 scenario):** `realAmountLockSubmit`(费用锁定提交)的请求
需要两个上游字段,其 `EndpointSpec` 完整形如:

```python
realAmountLockSubmit = EndpointSpec(
    method="POST",
    path="/api/order/orderFee/realAmountLockSubmit",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,                         # 锁定 = 改业务状态
    request=RealAmountLockSubmitRequest,
    responses={200: CommonResponseEnvelope},
    summary="实际费用锁定提交",
    auth_required=True,
    field_bindings=(
        FieldBinding(
            field_path="order_id",
            source_service="fin", source_method="POST",
            source_path="/api/order/order/orderDetail",
            source_field_path="data.order_id",
            note="锁定目标订单",
        ),
        FieldBinding(
            field_path="order_fee_real_ids",   # 注:request schema 里是 list[str]
            source_service="fin", source_method="POST",
            source_path="/api/order/orderFee/toggleRealAmount",
            source_field_path="data.to_customer.put_amount.standard_list.order_fee_real_id",
            note="费用项实收 id;来源响应里 to_customer / standard_list 均为列表,"
                 "取哪一项由 scenario 按业务条件决定(Plate 不固化下标)",
        ),
    ),
)
```

这条 4 层穿列表的 `source_field_path` 正是真实 scenario step 16→17 的值流动,在 Plate 里
只声明"能从哪取",元素选择留给 scenario。

**重要限制(Any 区域不可校验):** `models.py` 对超大字段接口大量用 `Any` 兜底。若
`source_field_path` 指向的路径落在某个 `Any` 字段之下,schema 树到 `Any` 就断了,该
`FieldBinding` 的引用完整性**无法静态校验**——此时它退化成 L2 性质的标注(只能人工保证)。
这是 `FieldBinding` 可验证性的硬边界:其严格程度受限于来源响应模型的建模精度。

放进 `EndpointSpec` 内（而非独立文档层）的理由：它是强结构化、机器要直接消费的
数据，跟 method/path 一样属于契约本体，不是松散业务说明。

**判定标准**：一条信息能不能写成"字段 X 的值应该从接口 Y 的字段 Z 来"这种结构化
三元组（且不含"取第几个"这种实例选择）？能 → `FieldBinding`；不能（是纯叙述/业务背景，
或本质是元素选择）→ `EndpointDoc.field_notes` / scenario。

### 2.3 EndpointDoc（叙述标注，L2，独立存储）

纯叙述性的业务语义，通过 `(service, method, path)` 外键关联 `EndpointSpec`，
独立维护、独立存储。GIMBAL 执行态完全不加载。

```python
@dataclass(frozen=True)
class EndpointDoc:
    """L2 人工标注层。与 EndpointSpec 解耦存储,外键关联。"""
    service: str
    method: str
    path: str
    field_notes: dict[str, str] = field(default_factory=dict)  # 字段路径 → 处理语义
    flow_notes: str = ""        # 这个接口在业务流程里的位置 / 作用
    maintainer: str = ""        # 标注负责人
    updated_at: str = ""        # 最后更新时间(ISO 8601)
```

**`field_notes` 的 key 必须区分 request / response 侧**，不能用裸字段名：
同一个字段名在请求侧和响应侧语义可能完全不同（如 `order_id` 在请求里是"查哪张订单"，
在响应里可能是"履约后生成的单据号"）。约定 key 加前缀：

```python
field_notes = {
    "request.order_id": "用于定位订单;不触发任何状态变更",
    "response.data.amount_status": "为 2 时代表金额已确认,会影响下游结算流程是否可发起",
}
```

> 注意区分：如果 note 内容在描述"这个字段的值会流向哪个接口"，那是**结构化流向关系**，
> 应该走 `FieldBinding`，不是 `field_notes`。`field_notes` 只装无法表达成
> "字段路径 → 另一个接口字段路径"的纯叙述内容（如"非空时触发审核""null 代表历史
> 兼容字段，新接口不应再传"）。

> **rev.2 修正——回查探针属于 `flow_notes`,不是核心字段。** 真实抓包里 `orderDetail`
> 与 `auditPage` 各被调用 10 次,是"每次状态推进后回查拿新生成 id"的高频探针。曾考虑给
> `EndpointSpec` 加 `is_context_probe: bool`,但这是**软使用习惯**(没有 `mutates_state`
> 那种安全后果,不是硬契约不变量),给典型探针接口的 `flow_notes` 写一句"本接口常作为写
> 操作后的状态回查点,下游需要新 id 时插入"即可,不该在契约层加 typed 字段。AI 编排时把
> `category=QUERY` + 此 flow_notes 合起来读,就能推断"写操作后该回查哪个接口"。

### 2.4 EndpointKey（索引键）与 EndpointBinding（service 内查询表）

```python
@dataclass(frozen=True)
class EndpointKey:
    """Registry 索引键。frozen=True 保证可作 dict key / set element。"""
    service: str
    method: str
    path: str
```

每个 service 包内维护 `PATH_MODELS: dict[(method, path), EndpointBinding]`，
`EndpointBinding` 持有 `request_model` / `response_data_model`，提供 service
内的 `(method, path)` → 模型反查（保留现有 `models.py` 中的查询函数形态）。

> **path 大小写敏感（真实数据约束）**：同一被测系统里真实存在
> `/api/Finance/ReceiveInvoiceBatch/...` 与 `/api/finance/receiveAccount/...` 大小写
> 不一致的路径并存。`EndpointKey` 的 path 匹配**必须大小写敏感、按 wire 原样存储**,
> 不做任何归一化——否则两个真实不同的端点会被错误合并。这条同样适用于 Capture/Prism
> 抓包入库与 scenario 引用时的 path 比对。

---

## 3. 约束规则

### 3.1 契约保真护栏（沿用 v3）

所有契约模型必须不会改写 wire 格式，`_assert_safe_model` 在 spec 注册期逐一检查：

1. 必须声明 `model_config`；
2. `model_config['extra']` 必须为 `"forbid"`（契约模型不允许默默吞掉未知字段）；
3. 禁用清单必须全部关闭：
   - `str_strip_whitespace`（会把 `' abc '` 改成 `'abc'`）
   - `coerce_numbers_to_str`（会在 `55` / `'55'` 之间互转）
   - `use_enum_values`（会把 Enum 实例替换为字面值）

> **现实约束**：被测系统部分接口字段多达 200+、类型随样本漂移，实践中 `models.py`
> 会对这类接口用 `extra="ignore"` + `Any` 兜底。设计上必须允许"只精确建模关心的
> 字段、其余兜底"，否则维护成本爆炸。`_assert_safe_model` 的护栏作用于声明了
> `extra="forbid"` 的契约模型；permissive 兜底模型是另一类，按其文档约定处理。

### 3.2 category 与 mutates_state 的交叉校验

`category` 是消费者要用的分类标签，但它驱动一个有真实风险的决策——
**CT 保活只能对 `QUERY` / `TOOL` 做主动探测**，标错类目意味着探测脚本可能在生产
环境意外触发一次业务写入（真实事故风险）。因此引入 `mutates_state` 做底层背书。

两者关系：

- `category`：分类**结论**（三选一），给消费者用；
- `mutates_state`：底层**事实**（布尔），给 `category` 的正确性背书。

`mutates_state` 回答"这个接口客观上改不改业务状态"，`category` 回答"基于这个事实，
该归哪一类"。日常只需填 / 查 `category`，`mutates_state` 是后台校验辅助字段。

**review pipeline 强制规则**：

```
category in (QUERY, TOOL)  ⇒  mutates_state == False     (否则 CI fail)
```

这样分类不再靠单字段主观判断，而是被一个更易核实的字段约束
（"这个接口到底改不改业务数据"远比"算业务还是查询"更容易判断对错）。

### 3.3 category 判定规则

按顺序问两个问题：

**第一步**：调用后，被测系统里某个**业务实体**（订单、账务、审核记录等）的持久化
状态是否发生改变？
- 是 → `BUSINESS`
- 否 → 进第二步

**第二步**：它读取/返回的内容，是不是某个具体业务实体的数据？
- 是 → `QUERY`
- 否（系统级能力，与具体业务实体无关——验证码、字典枚举、文件上传导出等）→ `TOOL`

> **"有业务意义"的限定（必读脚注）**：第一步只算**对调用方/业务流程可观察、影响
> 后续业务行为**的状态变更。纯内部审计日志 / 监控埋点写入**不算**。否则几乎所有接口
> 背后都写日志，会被全部误判成 BUSINESS。
>
> 例：`orderDetail` 即使背后写访问日志，仍是 `QUERY`（日志不影响后续业务流转）；
> `toggleRealAmount` 表面是"切换开关"，但改变订单金额确认状态、影响后续结算，
> 所以是 `BUSINESS`。

### 3.4 EndpointSpec 注册期校验（沿用 v3 + 新增）

`__post_init__` 强校：
- (a) 必填字段类型（method/path 非空字符串；request/responses 必须是 BaseModel
  子类或 None）；
- (b) 契约保真护栏（§3.1）；
- (c) **新增**：`category in (QUERY, TOOL)` 时断言 `mutates_state is False`；
- (d) **新增**：`field_bindings` 中每条 `field_path` 必须能在本接口 `request`
  模型字段树中解析到（防止绑定指向不存在的本接口字段）。**路径解析器须透明穿过
  `list[X]`（进入元素类型 `X`）与 `dict[str, V]`（进入值类型 `V`），逻辑路径不含下标/键**；
  遇到 `Any` 类型字段则停止解析并**放行**（无法证伪,见 §2.2 的 Any 限制）。

> 注意：`FieldBinding.source_*` 指向的是**别的** service/endpoint，注册期无法
> 单点校验（可能尚未 collect），这部分留给 review pipeline 的全局 referential
> integrity check（见 §5）。

---

## 4. Registry 核心（线程安全 / 拉式收集 / 按需加载）

沿用 v3 设计，要点不变：

- **拉式收集**：`importlib.import_module` 后遍历模块命名空间，`type(attr) is
  EndpointSpec` 严格匹配（排除继承）。
- **线程安全**：`threading.Lock` 保护 `_index` / `_loaded`；"collect + dict
  读取/迭代"必须在同一把锁内，避免锁外迭代被并发 collect 触发
  `RuntimeError: dictionary changed size during iteration`。
- **按需加载**：scenario 加载器和 mock 启动都"按需"，未引用的 service 一个字节
  都不 import。
- **共用 `warm()`**：contract check 与 mock server 启动都走这一入口；多 service
  异常合并抛 `BootstrapError`，一次性 fail-fast。

> **L2 不进 Registry 热路径**：`core.py` 的 Registry 只索引 `EndpointSpec`（L1）。
> `EndpointDoc`（L2）由独立的 doc registry 管理，仅 AI skill / doc 站点按需加载，
> GIMBAL 执行态不触碰。

---

## 5. 数据流转

### 5.1 谁生产、谁消费

```
┌──────────────────────────────────────────────────────────────────────┐
│                          生产端(写入 Plate)                            │
├──────────────────────────────────────────────────────────────────────┤
│  Prism / Capture  ──抓包蒸馏──▶  models.py / endpoints.py (L1 形状契约)  │
│  CT 主动探测       ──drift report──▶  review pipeline(只读端点)          │
│  人工 / AI 辅助   ──标注──▶       docs.py (L2 业务语义)                  │
│  人工确认         ──提升──▶       field_bindings (流量挖掘候选 → 权威绑定) │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                         CI / CT / AI / human review pipeline
                                   │  (保证契约跟随被测系统;校验标注引用完整性)
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          消费端(读取 Plate)                            │
├──────────────────────────────────────────────────────────────────────┤
│  GIMBAL 执行       ──resolve──▶   EndpointSpec(结构化检查 / 静态依赖检查) │
│  Capture / Prism   ──查询──▶      field_bindings(蒸馏时取权威值血缘)      │
│  AI skill          ──MCP 查询──▶  EndpointSpec + field_bindings +        │
│                                   EndpointDoc(scenario 编排上下文)       │
│  API doc 站点      ──渲染──▶      EndpointSpec + EndpointDoc(合并视图)    │
│  Mock server       ──填充──▶      responses + Field(examples=) / MockHook │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 关键流转链路

**链路 A —— GIMBAL 执行态结构化检查（只走 L1）**

```
scenario 引用 (service, method, path)
  → registry.resolve(service, method, path)        # 触发按需 collect,锁内
  → 拿到 EndpointSpec
  → 用 spec.request 校验请求体形状(extra=forbid 拦截未知字段)
  → 用 spec.responses[status] 校验响应形状
  → (可选)用 spec.field_bindings 做静态依赖检查:本步骤依赖的上游字段是否已就绪
```

**链路 B —— Capture / Prism 流量蒸馏（用 FieldBinding 替代启发式挖掘）**

```
ndjson 抓包
  → 旧:靠启发式从抓包猜"这个值是不是上一步响应来的"(易产生过匹配 / 幻觉)
  → 新:查 Plate field_bindings 拿权威答案
       "本接口 order_id 字段应从 orderDetail 的 data.order_id 取"
  → 生成 extract / assign 上下文传递,JSONPath 仍在真实响应里解析(防幻觉)
  → Plate 未覆盖的接口,再退回抓包挖掘(优雅降级)
```

> **互补,不是替代**：Plate 的 `field_bindings` 是**静态、契约级**——回答
> "order_sub_id **能**从 orderDetail 取"。流量挖掘是**动态、实例级**——回答
> "在**这一条**抓包里,**具体哪个** order_sub_id 值从第几步流到了第几步"。
> 两者互补:Plate 提供权威路径,lineage 分析提供本条流的实际值流向。

**链路 C —— AI skill 编排 scenario（合并 L1 + L2,走 MCP）**

```
AI 装配 scenario
  → MCP 查询某接口的 EndpointSpec(知道字段、类型、状态码)
  → MCP 查询 field_bindings(知道调用前必须先拿哪个上游接口的哪个字段 → 排调用顺序)
  → MCP 查询 EndpointDoc(知道字段的业务语义、流程位置 → 更合理梳理业务流转)
  → MCP 查询 category(区分"业务关键步骤,顺序敏感" vs "查询接口,随时可调")
  → 产出更合理的 scenario,而非靠模型自己猜上下文
```

### 5.3 二阶 drift 同步（L2 标注如何跟随 L1 契约变化）

这是"二阶 drift 问题"：一阶是契约跟随被测系统（已有 CI/CT/AI/human pipeline 解决）；
二阶是 `EndpointDoc` / `FieldBinding` 还要跟随 `EndpointSpec` 变化。L2 是纯人工
产物，探测不出来，**只能靠校验 + 报告，不能靠自动重生成**。

**referential integrity check**（review pipeline 内）：

对每条标注，反查它指向的 `EndpointSpec`，递归走 Pydantic 模型字段树，确认引用的
字段路径还存在。**解析器须按 §3.4(d) 透明穿过 `list[X]` / `dict[str, V]`**——真实
路径如 `data.to_customer.put_amount.standard_list.order_fee_real_id` 要穿 4 层(含两层
列表),这个解析器本身有真实复杂度,不是平凡字符串比对。

| 引用源 | 失效后处理 | 严重程度 |
|---|---|---|
| `FieldBinding`(路径可解析到具体类型) | **CI 直接 fail** | 硬失败——机器要直接消费做依赖排序/校验,指向不存在字段 = 给下游一个会产生幻觉的假绑定 |
| `FieldBinding`(路径落入 `Any` 区域) | **进 drift report,不卡 CI** | 降级——无法证伪(§2.2 Any 限制),只能人工保证,按 L2 处理 |
| `EndpointDoc.field_notes` 的 key | **进 drift report 队列,不卡 CI** | 软提示——纯叙述标注,路径漂移不影响下游正确性 |

> `FieldBinding` 的严重程度**取决于来源模型的建模精度**:来源响应若被精确建模,绑定
> 是硬契约、失效即 fail;若来源字段在 `Any` 兜底区(如 200+ 字段的 permissive 模型),
> 同一条 `FieldBinding` 只能降级成软提示。这给"优先精确建模哪些响应"提供了排序依据——
> **被下游 FieldBinding 依赖最多的响应字段,最值得从 `Any` 升级为精确类型**。

**不自动删除失效标注**：`EndpointSpec` 字段改名/删除时，标注的路径解析不到，但
标注文字本身可能仍有价值（旧 `order_sub_id` → 新 `sub_order_id`，业务语义不变）。
自动删除等于把人工劳动直接扔掉。正确做法：标成 `orphaned`，进 review pipeline 给人看，
由人决定迁移路径还是确认废弃。

> 这里把"是否还能解析到字段"当成驱动 review pipeline 优先级的信号,而不是靠人定期
> 巡检——呼应 Cell Engineering 中"hit_log 作单一真值、weight 为派生量"的思路。

---

## 6. 待确认 / 开放问题

1. **TOOL 类是否全部对应真实 wire 端点**：`EndpointSpec.method`/`path` 必填且强校验
   非空。如果"工具类"里存在不对应真实 HTTP 端点的纯函数式业务规则，它不该塞进
   `EndpointSpec`（否则被迫造假 method/path,污染契约纯净性）——这类应归 GIMBAL
   主框架/scenario 层。需确认 TOOL 类是否都是真实接口（验证码、文件上传等辅助接口）。
2. **field_bindings 候选的"提升"工作流**：流量挖掘产出的是候选绑定,提升为权威
   `FieldBinding` 需要人工确认环节,这个环节挂在 review pipeline 哪一步、用什么形态
   呈现给评审人,待定。
3. **EndpointDoc 的存储与版本**:L2 与 L1 解耦后,docs.py 仍是 Python 模块还是
   改为独立数据文件(便于非工程角色编辑),与服务化阶段一并决定。
4. **`Any` 字段的精确化排序（rev.2 新增）**：`models.py` 大量 `Any` 兜底使部分
   `FieldBinding` 不可静态校验(§5.3)。已确立排序原则:被下游 `FieldBinding` 依赖最多的
   响应字段优先从 `Any` 升级为精确类型。待定:是否在 Plate 里自动统计"字段被引用次数"
   并生成精确化优先级清单,作为建模工作的 backlog 来源。
