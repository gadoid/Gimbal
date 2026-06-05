# GIMBAL 变更方案 v2：引入 ModelRegistry,以契约模型 + EndpointSpec 替代裸字典请求

**状态**：设计定稿 · 待实现
**版本**：v2（在 v1 基础上整合多轮讨论修订；v1 为 PathRegistry 方案）
**影响版本**：v1.0 RC（含 breaking change，见 §9）
**核心目标**：把"被测系统的接口长什么样"从散落在各 scenario 的裸 dict,沉淀为可执行、可校验、可导出、可 mock 的**契约规范**,服务于 PHP→Java 迁移的接口与数据一致性验证,并为后续 SpringDoc 式接口文档 / 调试 / mock 打底。

---

## 0. 相对 v1 的关键修订（先读这一节）

v1 的方向正确,但多个核心机制在讨论中被推翻或细化。下面是**设计层面**的修订,具体到代码的改动点见文末 §10。

| v1 的做法 | v2 的修订 | 原因 |
|---|---|---|
| 模块名 `PathRegistry` | 改名 `ModelRegistry` | 实际按 service 组织,不按 path 索引；名字应表达"模型仓库" |
| api **直接持有** `request_model`（显式引用） | api **不感知** model,框架按 `(service, method, path)` **反查** | 真正的接口/数据分离：使用者只跟接口打交道,不必记 api↔model 映射；接入新系统 = 丢一个 service 目录即自动接入 |
| model 是裸 Pydantic 类,逐个引用 | 每个 endpoint = 一个 **`EndpointSpec` 实例**（组合,非继承） | 一个通用增强类,数据为主、能力（hook）为辅；用实例参数在"贫血/充血"间无级调节,无子类爆炸、无上帝对象 |
| （曾讨论）装饰器注册 + ast 发现 + `SERVICE` 常量 | **全部砍掉**：约定 service 名 = 目录名 = import 路径 | 装饰器带来 import 副作用→按需加载触发→自指悖论一整套补丁；约定目录名后这些问题直接蒸发 |
| `request.model_ref` 信封持 model 引用 | 信封不持 model 引用,只留 `api_ref` + values + headers | model 由反查得到,信封无需知道 model |
| （未涉及）ref 与 model 的关系 | 明确**三层结构**：ref（复用层）→ values（内容层）→ model（契约层） | `api_ref`/`request_ref` 是复用/别名机制,与 model 定位正交,二者共存、串行 |

v1 中**未变**的部分（仍然有效,本版完整保留）：§3 契约保真全部要求、模板兼容策略、response 建模、breaking change 处理。

---

## 1. 背景与动机

当前 step 定义里,请求体是裸 `request.body` 字典。在 PHP→Java 迁移对账场景下有两个根本问题：

1. **没有契约**：字段类型、空值语义、字段集合全靠手写,加载期发现不了结构错误,也无法作为两端验收标准。
2. **接口与数据耦合**：同一接口在不同 scenario 重复手写,接口定义无法集中维护、无法当文档用。

变更的本质：**为被测系统建立一份"可运行的契约规范"**。PHP 端与 Java 端都必须满足它,GIMBAL 用它在加载期做结构校验、执行期做对账、后期生成文档与 mock。

---

## 2. 三层结构：ref / 内容 / 契约（理解全方案的总纲）

讨论中确立的核心认知：**复用机制**与**契约定位**是两个正交的过程,不能互相替代。整套加载流程分三层,**严格串行**：

```
┌─ ref 层 ────────── api_ref / request_ref         复用、别名、快速构建（作者便利层）
│        ↓ 展开（解析别名 → 具体内容）
├─ 内容层 ────────── 展开后的 api 定义 + values     本次请求实际要发的东西
│        ↓ 反查（(service, method, path) → EndpointSpec）
└─ 契约层 ────────── ModelRegistry / EndpointSpec   结构化、类型、无损校验、文档、mock
```

- **ref 层不变**：`api_ref` / `request_ref` 继续保留,它是"给可复用内容起别名、后续快速构建"的机制,关心的是少写、复用、组合。
- **反查发生在 ref 展开之后**：只有别名展开成具体 api 定义,才拿得到确定的 `(service, method, path)` 三元组,才能反查 model。顺序不可逆。
- **统一校验时机规则**：**model 校验永远发生在所有引用展开、模板替换、运行期 extract 都完成之后**。ref 片段可能是半成品（只复用 supplier 段、其余 step 内补全）,对半成品校验没有意义。

---

## 3. ModelRegistry 模块设计

### 3.1 定位与目录结构

新建目录 `ModelRegistry`,集中存放被测系统所有接口的契约,按 service 组织。**约定:service 名 = 目录名 = import 路径**（这一约定消除了 v1 讨论里的 ast / `SERVICE` 常量 / 自指悖论）。

```
ModelRegistry/
├── __init__.py            # 只 re-export 注册表核心,不 import 任何子包
├── core.py                # 注册表：collect() / resolve() / 索引（命名避免 registry.py 自指）
├── spec.py                # EndpointSpec 通用类定义（见 §4）
├── settlement/            # 目录名即 service 名
│   ├── __init__.py
│   ├── order_add.py       # EndpointSpec 实例 + Request / Response 模型
│   └── order_page.py
└── order/
    └── order_detail.py
```

> **service 名合法性**：service 名要能直接拼成 Python 包名。若被测系统真实 service 标识含连字符（如 `tidb-test-service`）,二选一：目录用下划线（`tidb_test_service/`）+ 反查时 `service.replace("-", "_")`；或直接约定 service 标识用下划线、与目录逐字相等。**不要**因此把 `SERVICE` 常量 + ast 请回来。

### 3.2 注册表机制：collect / resolve（拉式收集,无 import 副作用）

整个加载/mock 机制收敛为一个核心方法 `collect`,reverse 与 mock 共用同一入口：

```python
# ModelRegistry/core.py（骨架，非完整实现）
import importlib
from dataclasses import dataclass

@dataclass(frozen=True)
class EndpointKey:
    service: str
    method: str
    path: str

class _Registry:
    def __init__(self):
        self._index: dict[EndpointKey, "EndpointSpec"] = {}
        self._loaded: set[str] = set()

    def collect(self, service: str) -> None:
        """import 该 service 包，遍历命名空间，拉式收集所有 EndpointSpec 实例。幂等。"""
        if service in self._loaded:
            return
        pkg_name = service.replace("-", "_")
        module = importlib.import_module(f"ModelRegistry.{pkg_name}")
        for attr in vars(module).values():
            if isinstance(attr, EndpointSpec):          # 拉式：靠类型识别，不靠装饰器副作用
                key = EndpointKey(service, attr.method, attr.path)
                self._index[key] = attr
        self._loaded.add(service)

    def resolve(self, service: str, method: str, path: str) -> "EndpointSpec":
        self.collect(service)                            # 首次访问触发该 service 收集
        key = EndpointKey(service, method, path)
        if key not in self._index:
            raise LookupError(
                f"[ModelRegistry] 未找到 {service} {method} {path}。"
                f"该 service 已注册端点：\n"
                + "\n".join(f"  {k.method} {k.path}" for k in self._index if k.service == service)
            )
        return self._index[key]

    def warm(self, services: list[str]) -> None:
        """启动期对一批 service 预热：所有 import / spec 错误在此 fail-fast，避免并发惰性竞态。"""
        for s in services:
            self.collect(s)

registry = _Registry()
```

要点：

- **拉式收集（pull）而非自注册（push）**：数据文件不在 import 时往全局表塞东西,而是由 registry import 后遍历命名空间挑出 `EndpointSpec` 实例。**零 import 副作用、幂等、可重置**,避免全局可变状态（你之前 review 抓过的线程安全/shutdown 根源）。
- **拉式收集顺带松绑了"一文件一 endpoint"约定**：一个模块里定义多个 `EndpointSpec` 实例也能全收上来,想分文件就分,不强制。
- **按 service 粒度按需加载**：未被引用的 service 一个字节都不 import。
- **warm 预热**：测试会话/ mock 启动时,对"本次声明要用的 service 列表"显式 `warm([...])`,把 import 与 spec 校验错误在启动期一次性炸出来,并消除并发下的惰性 import 竞态。与"按需"不冲突——预热的只是声明要用的 service。

---

## 4. EndpointSpec：通用增强类,数据为主、能力为辅

每个 endpoint 是 `EndpointSpec` 的一个**实例**。差异全靠构造参数：必填的是数据,可选的是 hook。**默认不传 hook = 走框架通用行为（贫血）；传 hook = 该接口特异行为（充血）。同一个类,无级调节。** 这正是 GIMBAL "骨架通用、组件特异" 哲学落到 endpoint 粒度。

```python
# ModelRegistry/spec.py（字段草案）
from dataclasses import dataclass, field
from typing import Callable
from pydantic import BaseModel

@dataclass
class EndpointSpec:
    # —— 数据（必填）——
    method: str
    path: str
    request: type[BaseModel]
    responses: dict[int, type[BaseModel]]     # {200: OrderAddResponse, 400: ErrorResponse}

    # —— 文档元数据（喂 SpringDoc 式生成）——
    summary: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    auth_required: bool = False

    # —— 能力 hook（预留扩展点，本期不实装，默认 None = 走通用行为）——
    mock_hook: Callable | None = None         # 覆盖默认 mock 生成
    validate_hook: Callable | None = None     # 覆盖默认 payload 校验
    build_request_hook: Callable | None = None  # 覆盖默认请求构建

    def __post_init__(self):
        # 轻量校验：畸形 spec 在所属 service 被 collect 的瞬间 fail-fast，定位到具体文件
        if not (isinstance(self.request, type) and issubclass(self.request, BaseModel)):
            raise TypeError(f"{self.path}: request 必须是 BaseModel 子类")
        for code, model in self.responses.items():
            if not isinstance(code, int):
                raise TypeError(f"{self.path}: responses 的 key 必须是 int 状态码")
            if not (isinstance(model, type) and issubclass(model, BaseModel)):
                raise TypeError(f"{self.path}: responses[{code}] 必须是 BaseModel 子类")
```

定义一个 endpoint 的样子：

```python
# ModelRegistry/settlement/order_add.py
from pydantic import BaseModel, ConfigDict, Field
from ModelRegistry.spec import EndpointSpec

class OrderAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: str = Field("", description="客户ID", examples=["16"])   # 注意：示例用真实线格式
    service_id:  str = Field("", description="销售ID", examples=["55"])
    status:      str = Field("", description="状态")
    # ... 其余字段按 PHP 真实线格式定（见 §5）

class OrderAddResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...

# 一个模块级实例，collect 时被拉式收集
ORDER_ADD = EndpointSpec(
    method="POST",
    path="/api/order/orderEntrust/orderAdd",
    request=OrderAddRequest,
    responses={200: OrderAddResponse},
    summary="新增订单委托",
    tags=["订单"],
    auth_required=True,
)
```

> **能力 hook 的纪律（重要）**：hook 只承载"跟这一个接口的契约内在相关、且可能因系统而异"的行为（校验自己的 payload、按自己的 schema mock、构建自己的请求）。判据是"换个系统这行为可能要变"。**跨 endpoint 的编排、reverse 索引、event bus、状态机、报告等框架骨架,绝不下沉到 endpoint**,否则 EndpointSpec 会膨胀成上帝对象。本期 hook **只预留、不实装**（YAGNI）；真碰到某 PHP 接口诡异语义、通用 mock 造不出合理数据时,再在那个实例上实装。

---

## 5. 契约保真要求（v1 原样保留 · 全方案最关键的工程约束）

迁移对账的价值完全建立在"模型不悄悄改写 payload"之上。模型一旦默默把 `""` 规整成 null、丢字段、把字符串转整数,就可能**恰好抹掉正要抓的那个 bug**。硬性约束：

### 5.1 字段类型按 PHP 实际线格式定义,不图省事
body 中 `service_id:"55"`、`customer_id:"16"`、`status:"1"`、`supplier_id:"8"`、`main_ids:"31,1"` **均为字符串**。标成 `int` 会让 Pydantic 在实例化阶段把 `"55"` 转成整数（发生在 httpx 之前,httpx 只忠实发整数）,而 PHP 当初收的是字符串——这个差异**正是要 diff 的对象**。**规则：是字符串就写 `str`**,类型按被测系统真实线格式定。

### 5.2 null 处理：禁用 `exclude_none`
httpx 会把 `None` 忠实序列化为 `null` 发出。`gross_weight:null`、`bulk:null` 等三态中的 null 支,只要**不用 `model_dump(exclude_none=True)`** 即可干净保真。

### 5.3 空串默认值对齐 PHP "未填"语义
危险仅在于"作者省略某字段、而模型默认值是 `None`"——此时 PHP 期望的 `""` 会塌成 null。**字段默认值必须与 PHP "未填"语义一致**（该 `""` 就默认 `""`）。

### 5.4 加载期硬护栏：`extra="forbid"` + round-trip 无损自检
不靠人脑逐字段推理,用两条机器护栏兜住：
- **`extra="forbid"`**：作者 dict 有、模型没有的字段直接报错,不被默默吞掉。
- **round-trip 等价自检**——本套契约模型"无损"的**定义**：

```python
assert Model.model_validate(raw).model_dump(by_alias=True) == raw
```

任何序列化偏差（类型被强制、字段被丢、key 重排、空值被改写）都在**启动期炸出**,而非对账时才发现 payload 被改过。

### 5.5 文档/mock 的 examples 也要用真实线格式
自动生成的 mock/example 会带 `"55"`、`""` 这类"不漂亮但真实"的值,**这是对的,别美化**——文档的价值正是展示真实线格式。`Field(examples=...)` 写示例时务必用真实形态（`"55"` 而非 `55`）,否则文档示例与契约模型自相矛盾。

---

## 6. 模板兼容（v1 原样保留 · 当前可行,后续按需扩展）

`@{}` / `${}` 模板目前**全部落在 `values` 内**,且仅落在 `str` 字段（如 `bl_no`、`pol`）,与加载期校验**无冲突**,本期无需特殊处理。

**已识别但推迟**：当模板需塞进 `int`/`float`/`list` 字段（`teu`/`gross_weight`/`container`）时,加载期校验会绊住。届时为相关字段开 `Annotated[int | TemplateExpr, ...]` 占位口子,采用两段校验（加载期只校结构与静态字段；解析完再跑完整校验）。**本期不预先实现**。

> 这与 §2 的统一校验时机规则是同一套机制：运行期 extract（如 `extract_token`）产生的值加载期不存在,与模板替换一样,完整校验都推迟到"解析完成之后"。合并处理即可。

---

## 7. SpringDoc 式文档 / 调试 / mock（后期演进,本期打底)

EndpointSpec 的设计已为这条路线留好全部结构化空间：

- **文档生成**：遍历所有 `EndpointSpec`,每个吐 `method`/`path`/`summary`/`tags` + 各 response 的 `model_json_schema()`,拼成 OpenAPI。字段级文档来自 `Field(description=, examples=)`,是 §5 严格建模的免费红利。
- **调试**：OpenAPI 出来后,Swagger UI 式调试器免费获得。
- **mock 启动流程**（与 reverse / warm / collect 完全自洽）：
  ```
  mock 启动(声明要 mock 的 service 列表)
    → registry.warm(services)            # import + 拉式收集这些 service 的 EndpointSpec 实例
    → 遍历收集到的实例
    → 按每个实例的 (method, path) 注册到 mock 前端路由
    → handler 用 responses[status] 的 model + examples 造数据返回
                （若该实例提供 mock_hook，则走 hook）
  ```
  要 mock 哪些 service 由 warm 显式声明,不会把全部系统拉起来。

**必须现在就埋的设计点**：EndpointSpec 用 `responses={200:..., 400:...}` 区分 request/response 角色与多状态码,**现在定好,后期多状态码 mock 就是免费的**；若现在偷懒只放一个 response,后期补多状态码要改数据结构 + 改所有调用点。

---

## 8. 启动期校验清单（替换 v1 §6,fail-fast）

加载阶段一次性暴露所有契约错误：

1. **反查可达**：每个 step 的 `(service, method, path)` 能 `registry.resolve(...)` 到非空 EndpointSpec,且其 `request` 非 None。首次访问触发该 service 的 `collect`。
2. **path 交叉校验（反查方案的关键兜底）**：把 api 引用的 `(service, method, path)` 集合,与所有已收集 EndpointSpec 的 path 集合做对账,**两边差集都报出来**——api 引用了但没 spec（契约缺失）、spec 注册了但没 api 用（死契约 / path 写错）。这条专治"反查方案下 path 字符串在两处复制、漂移时只会静默 resolve not found"的代价。
3. **EndpointSpec 自检通过**：collect 时 `__post_init__` 的轻量校验（responses key 为 int、request/response 为 BaseModel 子类）全过。
4. **values 可校验**：每个 step 的 `values` 能被对应模型 `model_validate` 通过。
5. **round-trip 无损自检**（§5.4）通过——模型未改写任何存量 payload。
6. **依赖方向单向**：`ModelRegistry` 不反向 import api 层,避免循环依赖。

---

## 9. 迁移与兼容（breaking change · v1 原样保留）

`request → values` 字段重命名属 **breaking change**,项目已 v1.0 RC,存量 scenario 不能一夜全红。二选一：
- **deprecation alias**：`request` 作为 `values` 过渡别名,加载期告警,下版移除。
- **一次性迁移脚本**：批量改写存量 scenario 结构。

建议先跑 §5.4 round-trip 自检扫存量,**先把"哪些字段会被模型悄悄改写"暴露出来**,再决定迁移脚本的字段类型映射,避免迁移本身引入线格式偏差。

---

## 10. 最终需要进行的改动点（实现清单）

按依赖顺序排列,每条都是可独立提交的改动。

### A. 目录与基础设施
- [ ] **A1** 新建 `ModelRegistry/` 目录（注意:不是 PathRegistry）。
- [ ] **A2** 写 `ModelRegistry/spec.py`：`EndpointSpec` 通用类（§4 字段草案 + `__post_init__` 轻量校验 + 预留三个 hook 字段,**不实装**）。
- [ ] **A3** 写 `ModelRegistry/core.py`：`_Registry`,实现 `collect`（拉式收集,幂等）/`resolve`（含友好的 not-found 报错）/`warm`；导出单例 `registry`。命名避开 `registry.py` 自指。
- [ ] **A4** `ModelRegistry/__init__.py` 只 re-export `registry`,**不 import 任何子包**。
- [ ] **A5** 确立约定：**service 名 = 目录名 = import 路径**；连字符 service 走 `replace("-","_")` 或直接用下划线标识。**不引入** ast / `SERVICE` 常量 / 装饰器。

### B. 契约模型（试点先行）
- [ ] **B1** 定一个 `EndpointModel` 基类或共享 `ConfigDict(extra="forbid")` 基线（§5.4/§5.5）。
- [ ] **B2** 以 `settlement/order_add.py` 为试点:按 PHP **真实线格式**建 `OrderAddRequest`（数字串保持 `str`、空串默认 `""`,§5.1/§5.3）,补 `Field(description=, examples=)`,examples 用真实形态。
- [ ] **B3** 建 `OrderAddResponse`（response 同样 `extra="forbid"`）。
- [ ] **B4** 在该文件定义模块级 `EndpointSpec` 实例,`responses={200: ...}` 形态先定好（为多状态码 mock 留路）。

### C. 加载器接入反查（替代 v1 的"api 持 model"）
- [ ] **C1** api 定义**移除任何 model 引用**（不要 `request_model` / `model_ref`）；api 块只保留 `service / method / path / headers` 等接口自身信息。
- [ ] **C2** 信封层改为 `request: { api_ref?, values, headers }`；`values` 由反查到的 model 实例化,不再裸 dict。
- [ ] **C3** 加载器在 step 加载时,先**展开 ref**,再用 `(service, method, path)` 调 `registry.resolve(...)` 拿 EndpointSpec,用 `spec.request` 实例化 `values`。落实"反查在 ref 展开之后"的顺序（§2）。
- [ ] **C4** 确认 `api_ref` / `request_ref` 复用机制**保持不变**,仅在其展开后接入反查。

### D. 校验时机统一
- [ ] **D1** 实现统一规则:**model 校验发生在 ref 展开 + 模板替换 + 运行期 extract 全部完成之后**（§2/§6）。半成品 ref 片段不校验。

### E. 启动期校验（替换 v1 §6）
- [ ] **E1** 实现 §8 校验清单第 1 条:每个 step 反查可达且 request 非 None。
- [ ] **E2** 实现 **path 交叉校验**（§8.2,反查方案关键兜底）:api 引用 path 集合 vs 收集到的 spec path 集合,双向差集报错。
- [ ] **E3** 接入 round-trip 无损自检（§5.4）,对试点接口的存量 scenario 扫一遍,先暴露"哪些字段会被模型悄悄改写"。
- [ ] **E4** 加 `warm(services)` 调用点:测试会话 / mock 启动前预热声明要用的 service,错误 fail-fast,消除并发惰性竞态。

### F. breaking change 兼容
- [ ] **F1** `request → values` 重命名:加 deprecation alias **或** 写一次性迁移脚本（§9）。建议先跑 E3 再定字段类型映射。

### G. 后期演进（本期只打底,不实装）
- [ ] **G1**（预留）OpenAPI 导出:遍历 EndpointSpec → `model_json_schema()` 拼 spec。
- [ ] **G2**（预留）mock server:`warm` → 收集实例 → 按 `(method,path)` 绑前端路由 → handler 用 `responses[status]` + examples（或 `mock_hook`）造数据（§7）。
- [ ] **G3**（预留）能力 hook 实装:仅当真实碰到系统特异语义时,在具体 EndpointSpec 实例上实装对应 hook。

---

## 决策摘要（v2）

| 项 | 决策 |
|---|---|
| 模块命名 | ✅ ModelRegistry（v1 的 PathRegistry 改名） |
| service 组织 | ✅ service 名 = 目录名 = import 路径,无 ast/无 SERVICE 常量 |
| 接口↔model 绑定 | ✅ **反查**`(service,method,path)`→EndpointSpec（推翻 v1 的"api 持 model"） |
| 反查理由 | ✅ 真分离 + 接入新系统只需丢目录,使用者不背 api↔model 映射 |
| endpoint 形态 | ✅ 通用 `EndpointSpec` 实例（组合）,数据为主、hook 为辅 |
| 注册机制 | ✅ 拉式收集（isinstance）,无 import 副作用,幂等；放弃装饰器 |
| 加载粒度 | ✅ 按 service `collect`,幂等；`warm` 批量预热 fail-fast |
| ref 机制 | ✅ `api_ref`/`request_ref` 保留,三层结构（ref→内容→契约） |
| 校验时机 | ✅ 统一在 ref/模板/extract 全部解析后 |
| 字段类型 | ✅ 按 PHP 真实线格式（数字串保持 `str`） |
| null / 空串 | ✅ 禁用 exclude_none；默认值对齐 PHP "未填" |
| 加载期护栏 | ✅ extra="forbid" + round-trip 无损 + path 交叉校验 |
| response 建模 | ✅ 纳入,`responses={status: model}` 多状态码形态先定 |
| 文档/调试/mock | 🔵 本期打底（EndpointSpec 结构就位）,后期实装 |
| 能力 hook | ⏸ 预留不实装（YAGNI） |
| 模板在 int/list 字段 | ⏸ 推迟,届时 TemplateExpr + 两段校验 |
| breaking change | ⚠ deprecation alias 或迁移脚本 |
