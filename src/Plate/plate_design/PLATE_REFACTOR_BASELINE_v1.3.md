# Plate 重构需求定案 v1.3(AI 友好契约层 + Plate 实例化)

> 版本:v1.3 · 2026-07-24 定稿
> 前置基线:[PLATE_REFACTOR_BASELINE.md v1.2](./PLATE_REFACTOR_BASELINE.md)
> 性质:在 v1.2 基础上的演化性升级,冻结范围同 v1.2(需求、目录结构、纪律、裁剪决定)。实现级细节授权就地决定后回写附录。
> 演化动机:八轮讨论的核心结论——把 Plate 从"校验工具"升级为"AI 写策略的契约源",同时把"校验职责"从 scenario 压回 L1 schema。

---

## 0. 一句话定位(演化)

**Plate 是被测系统的行为分身、测试体系的记忆器官,以及 AI 写策略的契约源**:让"了解被测系统"从散落在人脑、文档、脚本中的隐性状态,变成一个**可查询、可校验、知道自己边界、随每次分歧变厚、且可被 AI 直接消费的显性系统**。

Plate 与 GIMBAL(内核执行器)、Meter(决策规划器)构成三件套。Meter 与 AI 写策略工作流单向消费 Plate;需持久化的归 Plate,Meter 无状态。

---

## 1. v1.3 相对 v1.2 的演化总览

| 维度 | v1.2 形态 | v1.3 形态 |
|---|---|---|
| 策略层字段引用 | JSONPath 字符串(`$.response_body.data.orderId`) | 点分路径(锚定 Pydantic 模型根) |
| 校验职责 | 散落在 scenario assertion 中 | 集中到 L1 schema(Pydantic 注解 + validators) |
| scenario 与 schema 同步 | 运行时 fail,人肉排查 | 加载期 fail-fast(`path_resolver` 静态校验) |
| `plate.resolve()` 返回 | 概念上的 EndpointSpec | `ResolveResult{spec, obj, dict, errors, valid}` |
| 类型校验位置 | 运行时 assertion | 加载期 `path_resolver` + Pydantic 字段类型 |
| bindings 执行 | 待实现 | 对象世界 `setattr` + Pydantic 自动校验目标类型 |
| guard 时点 | 再生 + 摄入 | **+ scenario 加载期**(三时点) |
| `plate.describe()` 角色 | MCP 入口,给 Meter 用 | AI 写策略的 prompt 上下文 |

**核心迁移**:**校验职责从 scenario 压回 L1 schema**,AI 写策略从"推断路径"升级为"对照 schema 声明字段名"。

---

## 2. 新增需求项(B13)

### B13 · AI 友好契约层 + Plate 实例化

**目标**:让 Plate 在策略层路径引用、AI 工作流、bindings 执行三个维度成为"结构化对象世界"的一等公民。

**要点**:

1. **策略层路径引用从 JSONPath 切到点分路径**:锚定 `spec.responses[status]` / `spec.request` 的 Pydantic 根;scenario 加载期由 `path_resolver` 静态校验类型一致性。
2. **`plate.resolve()` 内部完成 `model_validate`**:对象世界里做校验,校验后 `.model_dump()` 序列化(热路径给 Gimbal 喂 dict)。
3. **所有 schema 级校验声明一次进 L1**:
   - 字段存在性(`extra='forbid'`)
   - 字段类型(Pydantic 字段类型注解)
   - 嵌套递归校验(自动)
   - 跨字段约束(`@model_validator`)
   - 字段别名(`Field(alias=...)`)
   - BeforeValidator / AfterValidator
4. **bindings 在对象世界执行**:`setattr(response_obj, ...)` 时 Pydantic 自动校验目标类型,跨端点字段注入零额外代码。
5. **`plate.describe()` 把 L1 Pydantic schema 作为结构化 prompt 上下文喂给 AI**:字段名引用无需从样例 JSON 推断。
6. **scenario 加载期扩为 guard 第三个强制时点**:与再生、摄入并列。

### 子需求 B13.1 · 路径引用形态

| 旧(JSONPath) | 新(点分路径) |
|---|---|
| `$.response_body.data.orderId` | `data.orderId`(锚定 `spec.responses[200]`) |
| `$.response_body.code` | `code`(锚定 `spec.responses[200]`) |
| `$.request_body.orderId` | `orderId`(锚定 `spec.request`) |

**实现**:`field_path` 在 scenario 加载期跑 `resolve_logical_path(root_model, field_path)`,校验:
- 路径可在 Pydantic 模型树中解析(字段存在性);
- 路径终点类型与 `expected` / `target` 字段类型一致(类型一致性);
- 路径未穿过 Any / 多态 Union(否则软降级或 fail-fast 由 guard 策略决定)。

### 子需求 B13.2 · `plate.resolve()` 返回值

```python
@dataclass(frozen=True)
class ResolveResult:
    """plate.resolve() 返回值。Gimbal 只与本类型交互。"""

    # 元信息:标识结果来自哪个 endpoint
    service: str
    method: str
    path: str
    spec: EndpointSpec                    # 原始 spec(category, mutates_state 等可读)

    # 校验结果(双形态)
    request_obj: BaseModel | None        # 校验通过的 Pydantic 对象(策略层字段访问用)
    request_dict: dict | None            # model_dump() 后的 dict(Gimbal 热路径 / httpx 用)
    response_obj: BaseModel | None       # 同上,响应侧
    response_dict: dict | None           # 同上

    status: int | None                   # response 状态码

    # 错误结构化
    errors: tuple[ValidationIssue, ...]  # Pydantic ValidationError 转换后的结构化错误
    request_errors: tuple[ValidationIssue, ...]  # request 校验错误(单独保留)
    response_errors: tuple[ValidationIssue, ...]  # response 校验错误(单独保留)

    @property
    def valid(self) -> bool:
        return not self.errors
```

**关键承诺**:
- `request_obj` / `response_obj` 总是 Pydantic 对象(校验通过时);
- `request_dict` / `response_dict` 总是 dict(校验通过时,model_dump 序列化);
- `errors` 永远是结构化列表,Pydantic `ValidationError` 不逃逸;
- Gimbal 通过 `valid` 决定是否继续,不需要 try/except;
- 策略层访问字段用 `result_obj.field_name`,O(1);Gimbal 编排层用 `result_dict`,热路径零 Pydantic 代理开销。

### 子需求 B13.3 · `plate.resolve()` 函数签名

```python
def resolve(
    service: str,
    method: str,
    path: str,
    *,
    payload: dict | None = None,           # request 体,None = 不校验 request
    response_body: dict | None = None,    # response 体,None = 不校验 response
    status: int | None = None,             # response 状态码,None = 不校验 response
) -> ResolveResult:
    """plate.resolve() 主入口。

    内部流水线:
      1. registry.resolve(service, method, path) → spec
         # 首次访问触发 service 包 import(models.py 整包拉起)
      2. 若 payload != None 且 spec.request != None:
           spec.request.model_validate(payload) → request_obj
           request_obj.model_dump() → request_dict
         校验失败 → request_errors,request_obj/dict 为 None
      3. 若 response_body != None 且 status != None:
           spec.responses[status].model_validate(response_body) → response_obj
           response_obj.model_dump() → response_dict
         校验失败 → response_errors,response_obj/dict 为 None
         status 不在 spec.responses 中 → fail-fast(spec 保真护栏)
      4. 装配 ResolveResult 返回
    """
```

**注意**:`payload` / `response_body` / `status` 三个参数都是可选,**支持三种调用形态**:
- 都给 → 同时校验 request + response(scenario step 完成态);
- 只给 `payload` → 只校验 request(场景:scenario 启动期拦截拼错的请求体);
- 只给 `response_body` + `status` → 只校验 response(场景:HTTP 响应后校验)。

### 子需求 B13.4 · bindings 在对象世界执行

```python
def execute_bindings(
    source_obj: BaseModel,
    target_obj: BaseModel,
    bindings: tuple[FieldBinding, ...],
) -> BaseModel:
    """在对象世界里执行跨端点字段注入。

    对每个 binding:
      1. resolve_attr(source_obj, binding.from_path) → 源值
      2. 若 binding.transform != None,查 _KNOWN_TRANSFORMS 应用转换
      3. setattr(target_obj, binding.to_path[-1], 转换后的值)
         # Pydantic v2 在 __setattr__ 时校验类型
         # 类型不匹配 → ValidationError,转 binding 失败错误
      4. 返回 target_obj

    错误处理:任一 binding required=True 且执行失败 → 抛 BindingError
    """
```

**收益**:`setattr` 时 Pydantic 自动校验目标类型,跨端点字段注入零额外代码;`@model_validator(mode="after")` 在所有 bindings 执行后跑,可做"注入后再校验"。

### 子需求 B13.5 · scenario 加载期路径校验

```python
# 在 Gimbal scenario 加载器内
def load_strategy(strategy_yaml: dict, response_model: type[BaseModel]) -> Strategy:
    if "field_path" not in strategy_yaml:
        return _legacy_jsonpath_strategy(strategy_yaml)  # 兼容旧写法(deprecated)

    field_path = strategy_yaml["field_path"]
    resolved = resolve_logical_path(response_model, field_path)

    if resolved.error is not None:
        raise ScenarioLoadError(
            f"strategy field_path {field_path!r} 解析失败: {resolved.error}"
        )

    if "expected" in strategy_yaml:
        expected_type = type(strategy_yaml["expected"])
        if not _is_compatible_type(expected_type, resolved.target_type):
            raise ScenarioLoadError(
                f"strategy expected {expected_type} 与 field_path {field_path} "
                f"终点类型 {resolved.target_type} 不兼容"
            )

    return _field_path_strategy(strategy_yaml, resolved)
```

**收益**:scenario 加载期 fail-fast 拦截三类错误:
- 字段名拼错(`data.orderId` → `data.orderid`);
- 类型不匹配(`expected: 0` 但 `code` 是 str);
- 路径穿过不支持区域(`Union[A, B]` 多态)。

### 子需求 B13.6 · `plate.describe()` AI 友好输出

```python
# plate.describe() 输出形态(B10 已定义,这里细化)
{
    "name": "订单详情查询",                    # L2 definition,缺则机械描述
    "description": "查询订单基本信息",          # L2 definition,缺则空
    "anchor": ("fin", "POST", "/api/order/order/orderDetail"),
    "schema": {
        "request": {
            "OrderDetailRequest": {
                "orderId": {"type": "str", "required": True}
            }
        },
        "responses": {
            200: {
                "CommonResponseEnvelope[OrderDetailData]": {
                    "code": {"type": "int", "required": True},
                    "data": {
                        "type": "OrderDetailItem",
                        "fields": {
                            "orderId": {"type": "str"},
                            "amount": {"type": "int", "constraints": "ge=0"}
                        }
                    }
                }
            }
        }
    },
    "bindings": [
        {"from_path": ["orderDetail", "data", "orderId"],
         "to_path": ["orderConfirm", "body", "orderId"],
         "transform": None}
    ],
    "maturity": "stable",                       # 成熟度申报(B3)
    "evidence_count": 42,                       # evidence 计数(B8)
    "blindspots": ["data.internalNotes 字段未建模"]  # 盲区清单(B5)
}
```

**AI 工作流**:AI 收到 `schema` 字段,直接对照字段名生成 scenario,无需从样例 JSON 推断。

---

## 3. 需求清单(终稿 v1.3)

### A 组 — 既有需求(v1.2 保留,v1.3 不变)

| # | 需求 | 现有承载 | v1.3 状态 |
|---|---|---|---|
| A1 | EndpointSpec 单轨数据模型 | spec.py | 不变 |
| A2 | category × mutates_state 交叉校验 | spec.py | 不变 |
| A3 | 进程级空 registry + 延迟首次 import | core.py | 不变 |
| A4 | byte-equal 序列化与 manifest 校验和 | serialization.py / manifest.py / version.py | 不变 |
| A5 | FieldBinding 声明性跨端点依赖 | binding.py / path_resolver.py | **v1.3 升级**:在对象世界执行 |
| A6 | 文档投影 | api_doc/ | 不变 |

### B 组 — 定案的新需求(v1.2 引入 + v1.3 新增)

| # | 需求 | v1.3 状态 |
|---|---|---|
| B1 | 两层存储 + 端口预留 | v1.2 不变 |
| B2 | L2 binding 体系 | v1.2 不变 |
| B3 | 面向 Meter 的供给接口 | v1.2 不变 |
| B4 | MCP 投影 | **v1.3 微调**:第一入口 `plate.describe()` 同时供 Meter 与 AI 用 |
| B5 | 分歧驱动的知识摄入 | v1.2 不变 |
| B6 | 图投影 | v1.2 不变 |
| B7 | 联邦查询 | v1.2 不变 |
| B8 | evidence 写回通道 | v1.2 不变 |
| B9 | map(catalog) | v1.2 不变 |
| B10 | describe/load 统一原语 | v1.2 不变,**v1.3 加 `resolve()` 作为 load() 的具体形态** |
| B11 | guard(再生 + 摄入) | **v1.3 扩展**:+ scenario 加载期(第三时点) |
| B12 | 套件规范 | **v1.3 细化**:`service_aliases` 显式声明 |
| **B13** | **AI 友好契约层 + Plate 实例化** | **v1.3 新增** |

### C 组 — 结构性定案(v1.2 保留)

| # | 问题 | v1.3 状态 |
|---|---|---|
| C1 | fin/ 归属 | v1.2 不变 |
| C2 | L1 载体 Python | v1.2 不变 |
| C3 | L2 载体数据文件 | v1.2 不变 |
| C4 | facade/server 删除 | v1.2 不变 |
| C5 | knowledge 数据归属 | v1.2 不变 |

---

## 4. 目录结构(终稿 v1.3)

```
src/Plate/
├── contracts/     # L1:挂载收集 + registry + 验收门 + resolve 流水线
│                  #   收编 spec.py / binding.py / path_resolver.py / core.py / _aliases.py
│                  #   v1.3 新增:resolve.py / resolve_result.py
├── knowledge/     # 引擎 only:L2 binding 的 schema 定义与本地读写;evidence 仅端口定义
├── guard/         # v1.3 扩:scenario 加载期校验钩子 + 再生/摄入三时点守卫
├── projection/    # manifest / catalog(map) / api_doc
├── supply/        # provenance、成熟度、联邦路由
├── mcp/           # v1.3 重点:plate.describe() 实现,MCP 投影
└── ingest/        # 分歧摄入、evidence 写回

suites/<system>/   # 被测系统套件:
│   ├── <契约 Python 包>        # L1
│   ├── bindings/*.yaml         # L2
│   ├── evidence.ndjson         # 后置
│   └── suite.manifest          # v1.3 新增 service_aliases 字段
```

**v1.3 关键变化**:
- `contracts/resolve.py` 新文件:`plate.resolve()` 主入口实现;
- `contracts/resolve_result.py` 新文件:`ResolveResult` 数据类;
- `mcp/` 从第三片提前到首片依赖(因为 AI 写 scenario 需要 `describe()`);
- `guard/` 扩 scenario 加载期校验(供 Gimbal 集成)。

---

## 5. 纪律(v1.2 四条 + v1.3 一条)

### D1 · 投影红线(扩展)

**v1.2 原文**:一切派生物(map、图、manifest、api_doc)必须由存储推导生成。

**v1.3 扩展**:**scenario YAML 中的字段引用也是派生数据**——它引用 L1 schema 字段名,严禁手写与 schema 不一致的引用。`path_resolver` 在 scenario 加载期强制这个约束。

### D2 · 生成验收门

不变(v1.2)。

### D3 · 拉取纪律(封存)

不变(v1.2)。

### D4 · 切片规矩

不变(v1.2)。

### D5 · Pydantic 类型边界(v1.3 新增)

**`plate.resolve()` 内部边界**:
- Plate 内部走对象世界(`BaseModel` 实例 + `model_validate` + `setattr`);
- Gimbal 拿到的永远是 dict(由 `model_dump()` 序列化)+ 结构化错误;
- Pydantic 类型不渗透到 Gimbal:`ValidationError` 在 resolve 内部转 `ValidationIssue` 元组,不出 resolve 边界。

**违反 D5 即架构腐化**——Gimbal 引入 `from pydantic import BaseModel` 或 `from Plate.spec import EndpointSpec` 即视为违反。

---

## 6. 裁剪记录(新增 v1.3 项)

| 砍除项 | 理由 | 回归条件 |
|---|---|---|
| v1.2 既有砍除项(略) | | |
| **JSONPath 在策略层的强制使用** | dict + JSONPath 是 v1.2 现状的"没有办法的办法";v1.3 切到点分路径后 JSONPath 沦为 deprecated;首片保留兼容,第二片移除 | 不回归 |
| **`assertion.py` 的 schema 级断言迁移到 L1** | scenario 不再承载 schema 级校验(`extra=forbid` / 类型校验 / 嵌套递归);`assertion.py` 只保留业务断言(与 schema 无关的运行时约束) | 不回归 |

---

## 7. 首片计划:resolve 替换 + scenario 加载期校验(半个月)

**目标**:Gimbal scenario 执行链走 `plate.resolve()` 校验响应,scenario 加载期跑 `path_resolver` 静态校验,旧 JSONPath 写法 deprecated 但兼容。

**完成定义**:
1. `plate.resolve()` 实现并接入 `HTTP_AFTER_RECV` hook 处;
2. scenario 加载器跑 `path_resolver` 校验 `field_path`;
3. 存量 fin scenarios 跑通(允许 deprecated JSONPath 写法);
4. `plate.describe()` 输出 L1 Pydantic schema;
5. manifest 自证重构前后契约零漂移。

### 第一周 — resolve 流水线 + ResolveResult

1. 新建 `contracts/resolve.py`:`plate.resolve()` 主入口;
2. 新建 `contracts/resolve_result.py`:`ResolveResult` 数据类;
3. `contracts/_aliases.py` 扩展:支持 `service_aliases` 双向映射(场景层 service 名 ↔ Plate service 包名);
4. `mcp/` 建 README 空壳 + 协议签名(`plate.describe()` 接口定);
5. `guard/` 建 README 空壳 + scenario 加载期校验协议定;
6. **接入点决策**:`HTTP_AFTER_RECV` hook 处,新增 `plate.resolve_response()` handler(不替换 assertion,validate 与 assertion 并行)。

### 第二周 — 场景加载期校验 + 存量迁移

7. scenario 加载器接入 `path_resolver`:新写法 `field_path` 走点分路径校验;旧 JSONPath 写法走 deprecated 分支;
8. **存量场景双协议跑通**:同一批 scenarios 既支持 JSONPath 也支持点分路径,结果一致;
9. `plate.describe()` 输出 L1 Pydantic schema 字段树(供 AI 工作流);
10. manifest 生成跑通,输出重构前后 checksum 对比;
11. 迁移工具:JSONPath → 点分路径自动转换脚本(只针对存量 fin scenarios)。

**风险预案**:第二周中段 scenario 加载器接入仍未跑通 → 旧 JSONPath 写法保留期延长,新写法按 opt-in 启用,不阻塞 deadline。

---

## 8. 后续片(顺序既定)

### 第二片:L2 数据载体 + guard 三时点

- L2 数据文件具体格式(YAML 倾向,anchor 用点分路径);
- guard 三时点实现:再生期 + 摄入期 + scenario 加载期;
- EvidencePort / IngestPort 协议签名(仅定义);
- fin 31 端点开始积语义(doc.py 胚胎字段迁移:summary→definition、notes→pitfall、requires→constraint、see_also→relation)。

### 第三片:evidence 实现 + MCP + AI 工作流

- evidence 实现落地(ndjson)+ ingest 写回;
- provenance + 成熟度申报;
- catalog(map)实现;
- MCP `plate.describe()` / `plate.resolve()` 完整实现;
- AI 写 scenario 工作流集成(Director / skill 接入 `describe()` 输出)。

### 第四片(封存):remote adapter 与拉取模式

同 v1.2。

---

## 9. 能力承诺(最终形态对照表 v1.3)

| 消费者 | Plate 能答的问题 |
|---|---|
| **GIMBAL(执行器)** | 契约解析与校验;mutates_state 事实;manifest 漂移检测;FieldBinding 依赖注入(对象世界执行) |
| **Meter(决策层)** | 字段 provenance 四通道;L2 语义按 anchor 检索;成熟度申报;图关联(后置);联邦代理易变查询 |
| **AI 写 scenario** | `plate.describe()` 输出 L1 Pydantic schema;字段名直接对照;`expected` / `target` 类型一致性加载期校验;bindings 跨端点引用可见 |
| **生成管线(Director / skill)** | AI 生成契约的验收落地;分歧摄入;evidence 写回 |
| **人** | L1/L2 独立 review;知识可溯源(anchor 机械校验);投影可再生 |

**边界(不做)**:不做决策(阈值归 Meter);不存易变业务数据(联邦);不含被测系统业务代码(套件);不产日志报告(执行器)。

**v1.3 新增边界**:不做 JSONPath 解析(已 deprecated);不做 Pydantic 类型渗透到调用方(由 D5 纪律约束)。

---

## 10. v1.3 相对 v1.2 的关键决策汇总

| 决策点 | v1.2 形态 | v1.3 决策 | 理由 |
|---|---|---|---|
| `plate.validate(...)` 签名 | 5 个必填参数 | 5 个可选参数(`payload` / `response_body` / `status` 都默认 None) | 支持三种调用形态(校验 request / response / 两者) |
| 校验结果形态 | bool / None | `ResolveResult{spec, obj, dict, errors, valid}` | 双形态同时返回,策略层用 obj,热路径用 dict |
| Pydantic 异常逃逸 | 抛 ValidationError | 转 `ValidationIssue` 元组不出 resolve | D5 边界纪律,避免 Pydantic 类型渗透 |
| 策略层字段引用 | JSONPath 字符串 | 点分路径(锚定 Pydantic 根) | 加载期静态校验 + 类型驱动生成 |
| 路径解析失败处理 | 运行时 None | 加载期 `ScenarioLoadError` | 与 L1 schema 改动自动同步 |
| scenario 加载期校验 | 无 | `path_resolver` 校验 `field_path` + `expected` 类型 | 加载期 fail-fast,改字段名 scenario 自动报错 |
| guard 时点 | 再生 + 摄入 | + scenario 加载期 | B11 纪律扩第三时点 |
| bindings 执行 | 待实现 | 对象世界 `setattr` + Pydantic 自动校验 | 类型安全,零额外代码 |
| `plate.describe()` | Meter 专用 MCP 入口 | Meter + AI 写 scenario 通用 prompt 源 | AI 工作流是 v1.3 核心受益者 |
| service 命名空间映射 | `_aliases.py` 单向 | `suite.manifest.service_aliases` 双向 | B12 显式声明,避免 validate 入口在跨命名空间调用上 fail-fast |
| `mock_hook` 返回值 | dict | BaseModel 实例(对象世界更易用) | 与 v1.3 实例化方向一致 |

---

## 11. 与现有实现的具体对位

| v1.3 设计条目 | 现状承接点 | 重构后承接点 | 状态 |
|---|---|---|---|
| A1 EndpointSpec 单轨 | [spec.py:117](src/Plate/spec.py#L117) | contracts/spec.py | 平移 |
| A3 按需加载(resolve 语义) | [core.py:132-156](src/Plate/core.py#L132-L156) | contracts/core.py | 平移 |
| A5 FieldBinding + path_resolver | [binding.py](src/Plate/binding.py) + [path_resolver.py](src/Plate/path_resolver.py) | contracts/{binding,path_resolver}.py | **v1.3 升级**:path_resolver 暴露给 scenario 加载器 |
| B10 describe/load 原语 | 无(协议已定) | contracts/resolve.py + mcp/describe.py | **v1.3 新增** |
| **B13 ResolveResult** | 无 | contracts/resolve_result.py | **v1.3 新增** |
| **B13 resolve() 主入口** | 无 | contracts/resolve.py | **v1.3 新增** |
| **B13 bindings 对象世界执行** | [binding.py](src/Plate/binding.py) 只定义数据类 | contracts/binding.py 扩 execute_bindings | **v1.3 新增** |
| **B13 scenario 加载期 path_resolver** | 无 | guard/scenario_loader.py | **v1.3 新增** |
| **B12 service_aliases** | [_aliases.py](src/Plate/_aliases.py) 单向 | suite.manifest.service_aliases | **v1.3 新增字段** |

---

## 12. 附录 · 授权就地决定项(回写区)

- [ ] `ResolveResult` 字段精切(已定稿于 §B13.2,实现期如调整须回写本附录)
- [ ] `plate.resolve()` 内部流水线异常路径(已定稿于 §B13.3,实现期如调整须回写)
- [ ] bindings 对象世界执行的 transform 转换实现细节(transform 仍是白名单字符串,Pydantic 不感知)
- [ ] `plate.describe()` 输出 JSON schema 字段命名约定(OpenAPI 兼容 vs 自定义,首片定)
- [ ] scenario 加载器接入点(Gimbal 端 vs Plate 端插件,首片定)
- [ ] 存量 JSONPath 写法的 deprecated 时间线(建议:首片引入 deprecated 警告,第二片移除)

---

## 13. v1.2 → v1.3 演化路径总览

```
v1.2(2026-07-23)                     v1.3(2026-07-24)
─────────────                        ─────────────
JSONPath 字符串引用       ──────→     点分路径(锚定 Pydantic 根)
scenario 承载 schema 校验  ──────→     L1 schema 集中校验
运行时 fail              ──────→     加载期 fail-fast
plate.validate(5 必填)   ──────→     plate.resolve(5 可选)
返回值 bool/None         ──────→     ResolveResult{obj, dict, errors}
guard 2 时点             ──────→     guard 3 时点(+ scenario 加载期)
describe() Meter 专用    ──────→     describe() Meter + AI 通用
bindings 待实现           ──────→     bindings 对象世界执行
```

**演化方向的一致性**:校验职责从 scenario 压回 L1 schema,AI 写策略从推断升级为声明,职责重新分配让 Plate 与 Gimbal 边界更清晰。