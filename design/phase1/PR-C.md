# PR-C: fin 31 端点从 PATH_MODELS 双轨切到 EndpointSpec 单轨 + 业务标注

> **状态**:待执行
>
> **PR 范围**:把 `fin` 服务从"models.py + PATH_MODELS 双轨"切到"endpoints.py + 31 个 EndpointSpec 实例"单轨,完成 31 端点的 `category` + `mutates_state` 业务标注。
>
> **前置依赖**:[PR-B](PR-B.md)(`category` 字段已加 + 强校已就位)
>
> **关键风险**:这是**最大的一次行为变化**——31 端点的存储形态从 dict 换成模块级实例;但存储形态不影响外部 API,`registry.resolve(...)` 不变。
>
> **对应设计**:[PLATE_DESIGN.md §1 目录结构 + §2.1 + §3.3 + §3.4](../../PLATE_DESIGN.md)

---

## 1. 业务动机

### 1.1 双轨问题(现状)

当前 `fin` 服务的存储形态:
- `src/Plate/fin/models.py`:存 Pydantic 数据类 + `PATH_MODELS: dict[(method, path), EndpointBinding]` + 查询函数
- 没有 `src/Plate/fin/endpoints.py`

**业务影响**:
- `EndpointSpec` 形态的字段(`category` / `mutates_state` / `summary` / `tags` / `auth_required` / `field_bindings` 等)无落脚点
- 任何 endpoint 的"业务语义"必须用 `EndpointBinding` 单独表达,**两份维护**
- 与设计 §1 的"endpoints.py 中存 EndpointSpec 实例"目录结构不一致

### 1.2 单轨目标

```
src/Plate/fin/
├── __init__.py     # re-export 31 个 EndpointSpec + 数据类
├── models.py       # Pydantic 数据类 (L1)         ← 只保留数据类
├── endpoints.py    # 31 个 EndpointSpec 实例 (L1)  ← 新建
└── docs.py         # EndpointDoc 实例 (L2)        ← PR-D3 加,本 PR 暂空
```

### 1.3 关键决策

详见 [DECISIONS.md D2](../DECISIONS.md):**response_data_models 字段放在 `EndpointSpec` 上**(单轨,不保留 `EndpointBinding` 内部辅助)。

**TOOL 类边界**(设计 §6 待确认问题 1):**`fin` 范围无 TOOL 类**,需在 PR-C review 阶段**显式**得出结论。

**`check_step1` / `check_step2` / `invoiceAddCheck` 的 category**(设计 §3.3 模糊地带):默认 `QUERY`(`check` 不直接改业务),review 推翻再改。

---

## 2. 代码实现要点

### 2.1 改动文件清单

| 文件 | 改动 |
|---|---|
| `src/Plate/spec.py` | 加 `response_data_models: dict[int, type[BaseModel]]` 字段(单轨合并) |
| `src/Plate/fin/models.py` | **删除** `PATH_MODELS` / `EndpointBinding` / `get_binding` / `get_request_model` / `get_response_data_model` / `list_paths`;只保留 Pydantic 数据类 |
| `src/Plate/fin/endpoints.py` | **新建**:31 个 `EndpointSpec` 模块级实例 |
| `src/Plate/fin/__init__.py` | re-export 31 个 spec + 31 个数据类(按需) |
| `tests/plate/test_fin_category_coverage.py` | 新建:本 PR 专属测试 |
| `tests/plate/test_invariants.py` | 加新不变量 |
| 外部消费者 | `grep` 找所有 `get_request_model` / `get_response_data_model` / `get_binding` / `PATH_MODELS` / `list_paths` 的调用方,逐一改用 `registry.resolve(svc, m, p).request` / `.responses[200]` |

### 2.2 `EndpointSpec` 新增 `response_data_models` 字段(单轨合并)

按 DECISIONS D2:

```python
@final
@dataclass(frozen=True)
class EndpointSpec:
    # ... 原有字段 ...
    request: type[BaseModel] | None = None
    responses: dict[int, type[BaseModel]] = field(default_factory=dict)
    response_data_models: dict[int, type[BaseModel]] = field(default_factory=dict)
    #                 ↑ 新增:data 内部模型(若可建模);按 status 索引
    # ... 其余字段 ...
```

**业务意图**:
- `responses[200] = CommonResponseEnvelope` 是 envelope,只能校验 `code/msg/request_id/data` 顶层形状
- `response_data_models[200] = OrderDetailData` 是 data 内部模型,可深入校验 `data.order_id` / `data.customer_id` 等
- 两者并存 = **两层契约**(外层 envelope + 内层 data)
- 多数 envelope 的 `data: Any` 会让"内层校验"走"Any 降级"路径(PR-D1 解析器),但**精确建模的 8 个端点可严格校验**

### 2.3 `fin/endpoints.py` 结构(31 端点)

按设计 §1 目录结构,新建此文件,逐个端点 31 个 `EndpointSpec` 实例:

```python
"""fin 服务:31 个 EndpointSpec 实例(单轨化)。"""
from Plate.spec import EndpointSpec, EndpointCategory
from Plate.fin.models import (
    # 数据类按端点 import
    OrderDetailRequest, OrderDetailData, CommonResponseEnvelope,
    ToggleRealAmountRequest, ToggleRealAmountData,
    # ...
)


# ════════════════════════════════════════════════════════════════════════════
# 1. orderEntrust/orderPage  ← QUERY
# ════════════════════════════════════════════════════════════════════════════
orderEntrustOrderPage = EndpointSpec(
    method="POST",
    path="/api/order/orderEntrust/orderPage",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=OrderEntrustOrderPageRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: OrderEntrustOrderPageData},
    summary="委托订单分页查询",
    tags=["order", "entrust", "query"],
)


# ════════════════════════════════════════════════════════════════════════════
# 2. orderEntrust/orderAdd  ← BUSINESS
# ════════════════════════════════════════════════════════════════════════════
orderEntrustOrderAdd = EndpointSpec(
    method="POST",
    path="/api/order/orderEntrust/orderAdd",
    category=EndpointCategory.BUSINESS,
    mutates_state=True,  # 创建委托
    request=OrderEntrustOrderAddRequest,
    responses={200: CommonResponseEnvelope},
    summary="委托订单新增",
    tags=["order", "entrust", "write"],
)


# ... 31 个端点逐一 ...


# ════════════════════════════════════════════════════════════════════════════
# 31. finance/receiveWriteoff/writeoffPage  ← QUERY
# ════════════════════════════════════════════════════════════════════════════
writeoffPage = EndpointSpec(
    method="POST",
    path="/api/finance/receiveWriteoff/writeoffPage",
    category=EndpointCategory.QUERY,
    mutates_state=False,
    request=WriteoffPageRequest,
    responses={200: CommonResponseEnvelope},
    response_data_models={200: WriteoffPageData},
    summary="核销分页查询",
    tags=["finance", "writeoff", "query"],
)
```

### 2.4 31 端点 `category` 判定清单

按设计 §3.3 两步问,逐端点判定(本表是 **PR-C review 阶段的检查表**):

| # | path | 第一步:改业务实体? | 第二步:返回业务实体数据? | category | mutates_state |
|---|---|---|---|---|---|
| 1 | /api/order/orderEntrust/orderPage | 否 | 是 | QUERY | False |
| 2 | /api/order/orderEntrust/orderAdd | 是(创建委托) | — | BUSINESS | True |
| 3 | /api/order/order/orderDetail | 否 | 是 | QUERY | False |
| 4 | /api/order/order/orderAdd | 是(创建订单) | — | BUSINESS | True |
| 5 | /api/order/order/orderBook | 是(订单订舱) | — | BUSINESS | True |
| 6 | /api/order/orderFee/toggleRealAmount | 是(金额确认) | — | BUSINESS | True |
| 7 | /api/order/orderFee/bookRealAmountEdit | 是(订舱金额修改) | — | BUSINESS | True |
| 8 | /api/order/order/checkGenerateOrderSub | 否(check 不改) | 是 | **QUERY** | False |
| 9 | /api/order/order/generateOrderSub | 是(生成子单) | — | BUSINESS | True |
| 10 | /api/order/orderFee/realAmountLockSubmit | 是(锁定费用) | — | BUSINESS | True |
| 11 | /api/home/audit/auditPage | 否 | 是 | QUERY | False |
| 12 | /api/home/audit/auditDetail | 否 | 是 | QUERY | False |
| 13 | /api/home/audit/auditExecute | 是(执行审核) | — | BUSINESS | True |
| 14 | /api/order/order/changeInvoiceApply | 是(发起改票审核) | — | BUSINESS | True |
| 15 | /api/order/order/orderConfirmAccount | 是(确认账户) | — | BUSINESS | True |
| 16 | /api/finance/accountFee/financePutList | 否 | 是 | QUERY | False |
| 17 | /api/finance/receiveAccount/orderReceiveAccountEdit | 是(编辑收款账户) | — | BUSINESS | True |
| 18 | /api/finance/receiveAccount/receiveAccountDetail | 否 | 是 | QUERY | False |
| 19 | /api/finance/receiveAccount/receiveConfirmList | 否 | 是 | QUERY | False |
| 20 | /api/finance/receiveAccount/accountConfirm | 是(确认收款) | — | BUSINESS | True |
| 21 | /api/Finance/ReceiveInvoiceBatch/applyPage | 否 | 是 | QUERY | False |
| 22 | /api/Finance/ReceiveInvoiceBatch/checkStep1 | 否(check 不改) | — | **QUERY** | False |
| 23 | /api/Finance/ReceiveInvoiceBatch/checkStep2 | 否 | — | QUERY | False |
| 24 | /api/Finance/ReceiveInvoiceBatch/batchOrderEdit | 是(批量编辑) | — | BUSINESS | True |
| 25 | /api/Finance/ReceiveInvoiceBatch/batchDetail | 否 | 是 | QUERY | False |
| 26 | /api/Finance/ReceiveInvoiceBatch/applyDetail | 否 | 是 | QUERY | False |
| 27 | /api/finance/receiveInvoice/invoiceAddCheck | 否(check) | — | **QUERY** | False |
| 28 | /api/finance/receiveInvoice/invoiceAdd | 是(添加发票) | — | BUSINESS | True |
| 29 | /api/finance/receiveWriteoff/orderFeePage | 否 | 是 | QUERY | False |
| 30 | /api/finance/receiveWriteoff/writeoffBatch | 是(批量核销) | — | BUSINESS | True |
| 31 | /api/finance/receiveWriteoff/writeoffPage | 否 | 是 | QUERY | False |

**统计**:BUSINESS = 15,QUERY = 16,**TOOL = 0**(`fin` 范围内确认无 TOOL 类)
> 注:本节统计行原写 `BUSINESS = 14, QUERY = 17`,是算术误差(漏数了 1 个 BUSINESS)。
> 实际算术 = 15 + 16 = 31。修正依据见 [DECISIONS.md D8](DECISIONS.md#d8-pr-c-24-端点分布统计行算术修正)。

**模糊项**(需业务方确认):
- 8 号 `checkGenerateOrderSub`:判定"check 不直接改"= QUERY;若 check 实际触发生成子单,改 BUSINESS
- 22/23 号 `checkStep1/2`:同上
- 27 号 `invoiceAddCheck`:同上

### 2.5 `models.py` 清理

**删除**:
- `PATH_MODELS` dict
- `EndpointBinding` dataclass
- `get_binding` / `get_request_model` / `get_response_data_model` / `list_paths` 函数
- `__all__` 中相应条目

**保留**:
- `_Base` 基类
- `_SAFE_CONFIG` ConfigDict
- `CommonResponseEnvelope` / `Params`
- `PermissiveRequest` + 它的 3 个 alias(`OrderEntrustOrderAddRequest` / `OrderAddRequest` / `OrderBookRequest`)
- 31 个端点的请求/响应数据类
- 内部 helper 类(`_MoneyBlock` / `_SettleSideItem` / `_AmountSummary` / 等)

### 2.6 外部消费者改写

**调用方盘点**(实际执行时 `grep`):
- `src/Plate/fin/__init__.py` 的 re-export
- 任何 e2e / scenario / mock / contract check 工具
- 抓包 skill 中如果用了

**改写模式**:
```python
# 旧
from Plate.fin.models import get_request_model
Req = get_request_model("POST", "/api/order/orderDetail")

# 新
from Plate.core import registry
Req = registry.resolve("fin", "POST", "/api/order/orderDetail").request
```

---

## 3. 测试用例设计(面向业务需求)

### 3.1 设计原则

每个测试对应一个具体业务承诺:
1. 31 端点**全部**有 `category` + `mutates_state` 标注
2. 标注**正确**(对照设计 §3.3 判定规则)
3. 31 端点**全部**可被 `registry.resolve` 拿到
4. 31 端点**全部**有合理的 `summary` / `tags`(供 AI skill 上下文查询)

### 3.2 必测业务场景

```python
"""PR-C:fin 31 端点单轨化 + 业务标注测试。

业务动机:31 端点必须从双轨切到单轨,全部带 category 标注,
供 CT 主动探测 / Mock server / AI skill 上下文查询使用。
"""


# ════════════════════════════════════════════════════════════════════════════
# 完整性:31 端点全部存在
# ════════════════════════════════════════════════════════════════════════════

EXPECTED_31_PATHS = {
    ("POST", "/api/order/orderEntrust/orderPage"),
    ("POST", "/api/order/orderEntrust/orderAdd"),
    ("POST", "/api/order/order/orderDetail"),
    # ... 共 31 项 ...
    ("POST", "/api/finance/receiveWriteoff/writeoffPage"),
}


def test_all_31_fin_endpoints_resolvable():
    """业务需求:fin 服务的 31 端点全部能被 registry.resolve 拿到。

    对应设计:§1 目录结构(endpoints.py + 31 个 EndpointSpec 实例)。
    业务影响:任何端点漏迁 = 该端点无法被 scenario 引用,e2e 测试断链。
    """
    from Plate.core import registry
    resolved = set()
    for method, path in EXPECTED_31_PATHS:
        spec = registry.resolve("fin", method, path)
        assert spec is not None
        resolved.add((method, path))
    assert resolved == EXPECTED_31_PATHS, (
        f"端点不一致:缺 {EXPECTED_31_PATHS - resolved},"
        f"多 {resolved - EXPECTED_31_PATHS}"
    )


# ════════════════════════════════════════════════════════════════════════════
# 完整性:31 端点全部带 category + mutates_state
# ════════════════════════════════════════════════════════════════════════════

def test_every_fin_endpoint_has_category():
    """业务需求:fin 服务的 31 端点全部带 category 标注(非默认值)。

    对应设计:§3.4(c) review pipeline 强制规则。
    业务影响:任何端点漏标 = PR-C 未完成;CT 主动探测可能误判。
    """
    from Plate.core import registry
    no_category = []
    for method, path in EXPECTED_31_PATHS:
        spec = registry.resolve("fin", method, path)
        if spec.category is None:
            no_category.append((method, path))
    assert not no_category, f"未标 category 的端点: {no_category}"


def test_every_fin_endpoint_has_correct_mutates_state():
    """业务需求:31 端点中,QUERY/TOOL 端点必须 mutates_state=False。

    对应设计:§3.2 真实事故风险。
    业务影响:任何破坏 = CT 主动探测可触发业务写入。
    """
    from Plate.core import registry
    from Plate.spec import EndpointCategory
    violations = []
    for method, path in EXPECTED_31_PATHS:
        spec = registry.resolve("fin", method, path)
        if spec.category in (EndpointCategory.QUERY, EndpointCategory.TOOL):
            if spec.mutates_state is not False:
                violations.append((method, path, spec.mutates_state))
    assert not violations, f"QUERY/TOOL 端点 mutates_state != False: {violations}"


# ════════════════════════════════════════════════════════════════════════════
# 正确性:对照 §3.3 判定规则逐端点验证
# ════════════════════════════════════════════════════════════════════════════

EXPECTED_CATEGORY = {
    # 写操作
    ("POST", "/api/order/orderEntrust/orderAdd"): (EndpointCategory.BUSINESS, True),
    ("POST", "/api/order/order/orderAdd"): (EndpointCategory.BUSINESS, True),
    ("POST", "/api/order/order/orderBook"): (EndpointCategory.BUSINESS, True),
    # ...
    # 读操作
    ("POST", "/api/order/orderEntrust/orderPage"): (EndpointCategory.QUERY, False),
    ("POST", "/api/order/order/orderDetail"): (EndpointCategory.QUERY, False),
    # ...
}


def test_fin_endpoints_match_expected_category():
    """业务需求:31 端点 category 标注对照设计 §3.3 判定规则全部正确。

    对应设计:§3.3 判定规则 + §3.4(c) 强制规则。
    业务影响:任何端点标错 = CT 主动探测误判 + AI 编排顺序错。
    """
    from Plate.core import registry
    for (method, path), (expected_cat, expected_mutates) in EXPECTED_CATEGORY.items():
        spec = registry.resolve("fin", method, path)
        assert spec.category is expected_cat, (
            f"{method} {path}: category 应为 {expected_cat}, 实际 {spec.category}"
        )
        assert spec.mutates_state is expected_mutates, (
            f"{method} {path}: mutates_state 应为 {expected_mutates}, 实际 {spec.mutates_state}"
        )


# ════════════════════════════════════════════════════════════════════════════
# 业务分布:符合预期(BUSINESS 14 / QUERY 17 / TOOL 0)
# ════════════════════════════════════════════════════════════════════════════

def test_fin_category_distribution_matches_design():
    """业务需求:fin 服务的 category 分布符合 PR-C review 拍板结论。

    对应设计:§6 待确认问题 1 "TOOL 类是否全部对应真实 wire 端点"。
    业务影响:若 TOOL 数为 0 但实际有工具型接口未识别,Phase 4 CT 探测会漏覆盖。
    """
    from Plate.core import registry
    from Plate.spec import EndpointCategory
    from collections import Counter
    counter = Counter()
    for method, path in EXPECTED_31_PATHS:
        spec = registry.resolve("fin", method, path)
        counter[spec.category] += 1
    assert counter == Counter({EndpointCategory.BUSINESS: 14, EndpointCategory.QUERY: 17}), (
        f"分布偏离 PR-C review 拍板: BUSINESS=14, QUERY=17, TOOL=0; 实际 {dict(counter)}"
    )


# ════════════════════════════════════════════════════════════════════════════
# 单轨化:旧查询函数已删除
# ════════════════════════════════════════════════════════════════════════════

def test_legacy_fin_query_functions_removed():
    """业务需求:fin.models 中的旧查询函数(PATH_MODELS / get_*_model)已删除。

    对应设计:§1 目录结构(单轨)。
    业务影响:旧函数残留 = 新旧两套,维护分叉。
    """
    import Plate.fin.models as fin_models
    assert not hasattr(fin_models, "PATH_MODELS"), "PATH_MODELS 应删除"
    assert not hasattr(fin_models, "EndpointBinding"), "EndpointBinding 应删除"
    assert not hasattr(fin_models, "get_binding"), "get_binding 应删除"
    assert not hasattr(fin_models, "get_request_model"), "get_request_model 应删除"
    assert not hasattr(fin_models, "get_response_data_model"), "get_response_data_model 应删除"
    assert not hasattr(fin_models, "list_paths"), "list_paths 应删除"


# ════════════════════════════════════════════════════════════════════════════
# 兼容性:resolve 拿到的 spec 仍可走 contract check / mock server
# ════════════════════════════════════════════════════════════════════════════

def test_resolved_fin_spec_compatible_with_contract_check():
    """业务需求:resolve 拿到的 EndpointSpec 满足现有 contract check 接口。

    对应设计:§2.1 EndpointSpec 形态不变。
    业务影响:spec 形态破坏 = contract check / mock server 全部失效。
    """
    from Plate.core import registry
    spec = registry.resolve("fin", "POST", "/api/order/order/orderDetail")
    # 现有 contract check 依赖 .request / .responses
    assert spec.request is not None
    assert 200 in spec.responses
    # .has_request() 辅助方法
    assert spec.has_request() is True
    # .response_models() 浅拷贝
    rms = spec.response_models()
    assert rms == {200: spec.responses[200]}
```

### 3.3 不变量更新

`tests/plate/test_invariants.py` 新增:

```python
def test_invariant_fin_endpoints_have_category():
    """业务不变量:fin 服务的 31 端点全部带 category 标注。

    对应设计:§3.4(c) review pipeline 强制规则。
    业务影响:任何端点漏标 = CT 主动探测可能误判业务写入。
    """
    from Plate.core import registry
    from Plate.spec import EndpointCategory
    no_label = []
    for key, spec in registry._index.items():
        if key.service != "fin":
            continue
        if spec.category is None:
            no_label.append(f"{key.method} {key.path}")
    assert not no_label, f"fin 端点未标 category: {no_label}"


def test_invariant_fin_query_endpoints_do_not_mutate():
    """业务不变量:fin 服务的所有 QUERY/TOOL 端点 mutates_state=False。

    对应设计:§3.2 真实事故风险。
    业务影响:任何破坏 = CT 探测可触发业务写入。
    """
    from Plate.core import registry
    from Plate.spec import EndpointCategory
    violations = []
    for key, spec in registry._index.items():
        if key.service != "fin":
            continue
        if spec.category in (EndpointCategory.QUERY, EndpointCategory.TOOL):
            if spec.mutates_state is not False:
                violations.append(
                    f"{key.method} {key.path}: {spec.category}/{spec.mutates_state}"
                )
    assert not violations, f"QUERY/TOOL 端点未保持 mutates_state=False: {violations}"
```

---

## 4. 收口验证

### 4.1 执行命令

```bash
# 1. 跑本 PR 专属测试
pytest tests/plate/test_fin_category_coverage.py -v

# 2. 跑不变量
pytest tests/plate/test_invariants.py -v -k "category or fin"

# 3. 跑全量基线
pytest tests/

# 4. 验证外部消费者已迁移
grep -rn "get_request_model\|get_response_data_model\|get_binding\|PATH_MODELS" src/ tests/ | grep -v "test_legacy_fin_query_functions_removed" | head -20
# 应无残留(除了删除前的旧测试)
```

### 4.2 验收

| 项 | 值 |
|---|---|
| `test_fin_category_coverage.py` 测试数 | ≥ 8 |
| 失败 | 0 |
| 31 端点全部有 category | ✅ |
| BUSINESS / QUERY / TOOL 分布 | 14 / 17 / 0 |
| 旧查询函数残留 | 0 |
| `from Plate.fin.endpoints import orderDetail` 可用 | ✅ |

### 4.3 风险

| 风险 | 缓解 |
|---|---|
| 外部消费者断链(grep 漏) | 跑全量 e2e 兜底 |
| `response_data_models` 字段破坏 frozen | 全部 Optional 默认空 dict;只追加,不改原 |
| `category` 标错导致 CT 误判 | review 阶段业务方逐个确认;模糊项标 TODO |
| 31 端点 `summary` 描述不准 | review 阶段 AI 抽样检查 |

---

## 5. 与后续 PR 的衔接

- **PR-D1**(路径解析器):用本 PR 产出的 8 个精确建模的 `response_data_models` 测 `FieldBinding` 解析
- **PR-D2**(`FieldBinding` 落地):`EndpointSpec.field_bindings` 字段加在 spec 上,本 PR 已就位
- **PR-D4**(`field_bindings` 批量化):用本 PR 标定的 `category` 区分"写端点"和"读端点"排调用顺序
- **Phase 4**(CT 主动保活):用本 PR 产出的 category 分布判断哪些端点可主动探测(14 BUSINESS 排除 / 17 QUERY 入选)
