# GIMBAL 变更方案：引入 PathRegistry,以契约模型替代裸字典请求

**状态**：设计定稿 · 待实现
**影响版本**：v1.0 RC（含 breaking change，见 §7）
**核心目标**：把"被测系统的接口长什么样"从散落在各 scenario 的裸 dict,沉淀为可执行、可校验、可导出的**契约模型**,服务于 PHP→Java 迁移的接口与数据一致性验证。

---

## 1. 背景与动机

当前 step 定义里,请求体是一个裸 `request.body` 字典。在 PHP→Java 迁移对账的场景下,这种写法有两个问题：

1. **没有契约**：字段类型、空值语义、字段集合全靠作者手写,无法在加载期发现结构错误,也无法作为两端的验收标准。
2. **接口与数据耦合**：同一个接口在不同 scenario 里被重复手写,接口定义无法集中维护、无法当文档用。

变更的本质：**为被测系统建立一份"可运行的契约规范"**。PHP 端和 Java 端都必须满足这份规范,GIMBAL 用它在加载期做结构校验、在执行期做对账。

---

## 2. 核心变更（已决策）

### 2.1 新增 PathRegistry 模块

新建目录 `PathRegistry`,集中存放被测系统所有接口的**数据类结构对象**（Pydantic 模型）,按服务（service）组织。它同时承担两个角色：

- **模型仓库**：所有 request / response 模型的存放地。
- **接口文档真源**：配合 `Field(description=...)`、`examples`,可直接 `model_json_schema()` 导出 JSON Schema / OpenAPI。

```
PathRegistry/
├── __init__.py
├── settlement/
│   ├── __init__.py
│   └── orderadd.py        # OrderAddRequest / OrderAddResponse / Supplier ...
└── ...
```

### 2.2 api 直接持有 request_model（替代命名约定查找）

> **关键决策**：放弃"服务名 → 同名模块 → path → 数据类"的约定式查找,改为 api 定义**直接持有模型引用**。

原约定式查找靠命名匹配,改名即崩、IDE 跳不进去、重构无保护。改为显式引用后：

- 可跳转、可重构、IDE 全程跟得到；
- 启动期可一次性校验"每个 api 都绑定了 model"；
- PathRegistry 退居为模型**存放地**,api 只是**引用**进去。

**依赖方向必须单向**：`api → PathRegistry`,反向禁止,避免循环 import。

api 定义两种形式都支持,且校验逻辑统一：

- Python：直接持类引用 `request_model = OrderAddRequest`
- YAML：存 dotted path `PathRegistry.settlement.orderadd.OrderAddRequest`,启动期解析并校验引用存在

### 2.3 `request` 字段重命名为 `values`,但保留请求信封

`values` 存放**本次请求的值信息**,通过对应数据类实例化,不再用裸 dict 处理。

但原 `request.body` 之外尚有 header / query / content-type 的存放空间。若 `values` 直接退化为纯类型化 payload,这些请求级信息将无处安放。**保留一层薄信封**：

```yaml
request:                      # 信封层（保留）
  model_ref: ...              # 指向 PathRegistry 中的模型（见 2.2）
  values: {...}               # 类型化 payload（由模型实例化）
  headers: {...}              # 请求级元信息,不进模型
```

---

## 3. 契约保真要求（已决策 · 本方案最关键的工程约束）

迁移对账的价值,完全建立在"模型不能悄悄改写 payload"之上。模型一旦默默把 `""` 规整成 null、把缺失字段丢掉、把字符串转成整数,就可能**恰好抹掉正要抓的那个 bug**。以下为硬性约束：

### 3.1 字段类型按 PHP 实际线格式定义,不图省事

body 中 `service_id:"55"`、`customer_id:"16"`、`status:"1"`、`supplier_id:"8"`、`main_ids:"31,1"` 等**均为字符串**。

- 若把这些字段标成 `int`,Pydantic 在实例化阶段就把 `"55"` 转成整数 `55`——这一步发生在 httpx 之前,httpx 只会忠实地把整数发出去。
- PHP 当初收到的是字符串 `"55"`,Java 端是否容忍这个差异,**正是要 diff 的对象**。
- **规则**：是字符串就写 `str`,不要为了"看起来更类型化"写成 `int`。类型按被测系统真实线格式定。

### 3.2 null 处理：禁用 `exclude_none`

httpx 会把 `None` 忠实地序列化为 `null` 发出。`gross_weight:null`、`bulk:null` 等三态中的 null 支,只要**不使用 `model_dump(exclude_none=True)`**,即可干净保真。

### 3.3 空串默认值对齐 PHP "未填"语义

body 中大量 `""`。只要 values 从作者 dict 实例化、字段为 `str`,`""` 即可保住。**危险仅在于**：作者省略了某字段、而模型默认值是 `None`——此时 PHP 期望的 `""` 会塌成 null。**字段默认值必须与 PHP 的"未填"语义一致**（该是 `""` 就默认 `""`）。

### 3.4 加载期硬护栏：`extra="forbid"` + round-trip 无损自检

不要逐字段靠人脑推理保真,用两条机器护栏兜住：

**(a) `extra="forbid"`**：作者 dict 里有、模型里没有的字段直接报错,而不是被默默吞掉。

**(b) round-trip 等价自检**——这是本套契约模型"无损"的**定义**：

```python
assert Model.model_validate(raw).model_dump(by_alias=True) == raw
```

任何序列化偏差（类型被强制、字段被丢、key 被重排、空值被改写）都会在**启动期炸出来**,而不是等到对账阶段才发现 payload 被悄悄改过。

### 3.5 模型 ConfigDict 基线

```python
from pydantic import BaseModel, ConfigDict

class EndpointModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",          # 多余字段报错,不吞
        # 不开启任何会改写线格式的强制/规整
    )
    # 序列化统一走 by_alias=True、不带 exclude_none
```

---

## 4. 模板兼容（当前可行 · 后续按需扩展）

`@{}` / `${}` 模板目前**全部落在 `values` 内**,且仅落在 `str` 字段上（如 `bl_no`、`pol`）。在此前提下与加载期校验**无冲突**,本期无需特殊处理。

**已识别但推迟**：当某个模板需要塞进被标成 `int` / `float` / `list` 的字段（如 `teu`、`gross_weight`、`container`）时,加载期校验会绊住。届时再为相关字段开占位口子：

```python
Annotated[int | TemplateExpr, ...]   # 加载期接受模板占位
```

并采用**两段校验**：加载期只校结构与静态字段；执行期模板替换完成后再跑一次完整校验。**本期不预先实现**,避免过度设计。

> 注意:运行期 extract（如 step 里的 `extract_token`,从上一步抽值）产生的值在加载期根本不存在,天然无法做完整 load-time 校验。这与上面的两段校验是同一套机制,合并处理即可。

---

## 5. 推荐项 / 后续演进（建议纳入,非本期阻塞）

### 5.1 同步建模 response（强烈建议）

strategy 中已在断言 `$.response_status`。对迁移验证而言,**响应契约比请求更重要**——要拿 PHP 响应与 Java 响应,对同一份期望做 diff。

- 每个 endpoint 同时提供 `request_model` + `response_model`,设计才闭环。
- response model 同样 `extra="forbid"`：Java 端字段一增一减,用例立刻报警,正中迁移漂移的靶心。

### 5.2 契约模块升级为 spec 真源

PathRegistry 既定位为接口文档,顺势在模型上补 `Field(description=...)`、`examples`,即可 `model_json_schema()` 直接导出 JSON Schema / OpenAPI。契约模块从"给人看的文档"升级为"能生成 spec 的真源",**PHP 与 Java 两端拿同一份 schema 当验收标准**。这是本套设计最值的产出。

---

## 6. 启动期校验清单（实现时落地）

加载阶段一次性暴露所有契约错误（fail-fast）：

1. 每个 api 的 `request_model` 引用可解析、存在于 PathRegistry。
2. （若启用 5.1）每个 api 的 `response_model` 引用可解析、存在。
3. 依赖方向单向：PathRegistry 不反向 import api 层。
4. 每个 step 的 `values` 能被对应模型 `model_validate` 通过。
5. round-trip 无损自检（§3.4b）通过——即模型未改写任何存量 payload。

---

## 7. 迁移与兼容（breaking change）

`request → values` 字段重命名属 **breaking change**,而项目已进入 v1.0 RC,存量 scenario 不能一夜全红。二选一：

- **保留 deprecation alias**：`request` 作为 `values` 的过渡别名,加载期告警,下个版本移除。
- **一次性迁移脚本**：批量改写存量 scenario 的 `request` → `values` 结构。

建议先跑 §3.4 的 round-trip 自检扫一遍存量,**先把"哪些字段会被模型悄悄改写"暴露出来**,再决定迁移脚本的字段类型映射,避免迁移过程本身引入线格式偏差。

---

## 8. 落地顺序建议

1. 搭 PathRegistry 目录骨架 + `EndpointModel` 基类（§3.5）。
2. 以 `settlement/orderadd` 为试点,按 §3.1/§3.3 的真实线格式建 `OrderAddRequest`。
3. 接上 round-trip 自检（§3.4b),对该接口的存量 scenario 扫描验证无损。
4. api 定义改为持有 `request_model`(§2.2),打通加载期引用校验。
5. step 结构 `request → values`,上 deprecation alias(§7)。
6. 补 response_model(§5.1)与 schema 导出(§5.2),全量推广。

---

## 决策摘要

| 项 | 决策 |
|---|---|
| PathRegistry 模块 | ✅ 新增,按 service 组织,兼作契约文档真源 |
| 接口与模型绑定 | ✅ api 直接持 request_model,放弃命名约定查找 |
| 依赖方向 | ✅ api → PathRegistry 单向 |
| 字段重命名 | ✅ request → values,保留请求信封层 |
| 字段类型 | ✅ 按 PHP 真实线格式（数字串保持 `str`） |
| null 处理 | ✅ 禁用 exclude_none,httpx 透传 |
| 空串默认值 | ✅ 对齐 PHP "未填"语义 |
| 加载期护栏 | ✅ extra="forbid" + round-trip 无损自检 |
| 模板在 int/list 字段 | ⏸ 推迟,届时上 TemplateExpr + 两段校验 |
| response 建模 | 🔵 强烈建议,本期可并行 |
| schema 导出 | 🔵 建议,作为两端验收标准 |
| breaking change | ⚠ deprecation alias 或迁移脚本 |
