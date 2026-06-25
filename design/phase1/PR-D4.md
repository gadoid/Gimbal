# PR-D4: 首批 field_bindings 批量化

> **状态**:待执行
>
> **PR 范围**:为 fin 服务的 17 个 QUERY 端点批量标注 `field_bindings`(找上游 → 标 binding),**不**包括 BUSINESS 类(BUSINESS 是写入端,无上游读依赖)。
>
> **前置依赖**:[PR-D2](PR-D2.md)(FieldBinding 落地) + [PR-D1](PR-D1.md)(路径解析器) + [PR-C](PR-C.md)(fin 已显式标 category)。
>
> **关键设计**:**只在有**真实"上游响应字段**塞进下游请求体"**关系的端点对上加 binding**,不强凑。
>
> **对应设计**:[PLATE_DESIGN.md §2.2 + §3.5](../../PLATE_DESIGN.md)

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:PR-D2 落地了 `FieldBinding` 类型,但 31 个 fin 端点 `bindings=()`。没有真实 binding 标注 = PR-D2 是空架子。

**真实业务场景**:
- `addOrder` 返回 `order_id` → `orderDetail` 请求需要 `order_id`
- `addOrder` 返回 `order_id` → `cancelOrder` 请求需要 `order_id`
- `addCart` 返回 `cart_id` → `cartDetail` 请求需要 `cart_id`
- `addAddress` 返回 `address_id` → `updateAddress` 请求需要 `address_id`
- `addInvoice` 返回 `invoice_id` → `invoiceDetail` 请求需要 `invoice_id`

**17 QUERY 端点中,有上游注入需求的大约 8-12 个**,其余是"独立查询"(无明确上游)或"用户手动输入"(如 login)。

### 1.2 关键决策

- **不强凑**:没有真实依赖的端点对,**不加 binding**。允许 QUERY 端点 `bindings=()`。
- **上游默认 `addOrder`**:fin 几乎所有数据生命周期从 `addOrder` 起步。**但**有少数 QUERY(如 `userInfo` / `dictList`)无上游,这些端点 `bindings=()` 是**正确状态**,不是缺失。
- **本 PR 不引入 BindingRegistry**:精确"binding from → 哪个 endpoint"反向索引留到 PR-EOP(收口 review pipeline 时一起做)。

### 1.3 业务覆盖矩阵(预估)

| 上游端点 | 下游端点 | binding 描述 |
|---|---|---|
| `addOrder` | `orderDetail` | order_id |
| `addOrder` | `cancelOrder` | order_id |
| `addOrder` | `payOrder` | order_id + amount |
| `addCart` | `cartDetail` | cart_id |
| `addCart` | `updateCart` | cart_id |
| `addAddress` | `addressDetail` | address_id |
| `addAddress` | `updateAddress` | address_id |
| `addInvoice` | `invoiceDetail` | invoice_id |
| `applyDetail` | `cancelApply` | apply_id |

**(预估 9 个 binding,实际 PR 执行时以端点对端点分析为准)**

---

## 2. 代码实现要点

### 2.1 改动文件清单

| 文件 | 改动 |
|---|---|
| `src/Plate/fin/specs.py` 或 `src/Plate/fin/__init__.py` | 给相关 endpoint 加 `bindings=(...)` |
| `src/Plate/fin/dannotations/__init__.py` | 补首批 endpoint 的 L2 注释(可与 binding 标注并行) |
| `tests/plate/test_fin_bindings.py` | 新建:本 PR 专属测试(≥15 个) |
| `tests/plate/test_invariants.py` | 加不变量:`bindings` 引用真实上游(路径在某个 QUERY/BUSINESS 响应里存在) |

### 2.2 binding 标注规范

**示例:`orderDetail` 依赖 `addOrder`**

```python
# src/Plate/fin/__init__.py(或 specs.py)

# 上游
_ADD_ORDER = EndpointSpec(
    method="POST",
    path="/api/order/order/addOrder",
    request=AddOrderRequest,
    responses={200: CommonResponseEnvelope},
    category=EndpointCategory.BUSINESS,
    mutates_state=True,
)

# 下游(典型 QUERY)
_ORDER_DETAIL = EndpointSpec(
    method="POST",
    path="/api/order/order/orderDetail",
    request=OrderDetailRequest,
    responses={200: CommonResponseEnvelope},
    category=EndpointCategory.QUERY,
    mutates_state=False,
    bindings=(
        FieldBinding(
            from_path=("data", "order_id"),  # addOrder 响应里的路径
            to_path=("order_id",),            # orderDetail 请求里的路径
            required=True,
        ),
    ),
)
```

### 2.3 binding 标注前置分析(端点对端点)

**PR 执行时需对每个候选 binding 做**:

| 检查项 | 说明 | 失败处理 |
|---|---|---|
| 上游真实存在 | `addOrder` 真在 fin 服务里 | 不存在则跳过,本 PR 不加 |
| 下游真实存在 | `orderDetail` 真在 fin 服务里 | 不存在则跳过 |
| from_path 在上游响应模型里 | 用 PR-D1 的 `resolve_logical_path` 验证 | 不存在则跳过或硬错(待 PR-D4 决策) |
| to_path 在下游请求模型里 | 同上 | 同上 |
| transform 类型已知 | 在 `_KNOWN_TRANSFORMS` 内 | 未知则先扩白名单(本 PR 允许) |

**本 PR 决策**:`resolve_logical_path` 验证失败的 binding,**硬错拒绝**(注册期 fail-fast),不静默跳过。原因:静默跳过 = "binding 标了但其实没用" = 死代码误导 AI。

### 2.4 binding 落地表(本 PR 目标清单)

| 序号 | 上游 | 下游 | from_path | to_path | transform |
|---|---|---|---|---|---|
| 1 | addOrder | orderDetail | (data, order_id) | (order_id,) | identity |
| 2 | addOrder | cancelOrder | (data, order_id) | (order_id,) | identity |
| 3 | addOrder | payOrder | (data, order_id) | (order_id,) | identity |
| 4 | addOrder | payOrder | (data, amount) | (amount,) | int->str |
| 5 | addCart | cartDetail | (data, cart_id) | (cart_id,) | identity |
| 6 | addCart | updateCart | (data, cart_id) | (cart_id,) | identity |
| 7 | addAddress | addressDetail | (data, address_id) | (address_id,) | identity |
| 8 | addAddress | updateAddress | (data, address_id) | (address_id,) | identity |
| 9 | addInvoice | invoiceDetail | (data, invoice_id) | (invoice_id,) | identity |
| 10 | applyDetail | cancelApply | (data, apply_id) | (apply_id,) | identity |

**(预估 10 个 binding,实际以端点真实分析为准)**

---

## 3. 测试用例设计(面向业务需求)

### 3.1 设计原则

每个测试对应一个具体业务承诺或硬错误,docstring 写明:
1. **业务需求**(binding 真实性的硬约束)
2. **对应设计章节**
3. **业务影响**(违反此约束的代价)

### 3.2 必测业务场景

```python
"""PR-D4:fin 首批 field_bindings 批量化测试。

业务动机:FieldBinding 类型已落地(PR-D2),但 31 端点 bindings=() 是空架子。
本 PR 把"上游 addOrder → 下游 orderDetail"等真实依赖批量标注。
"""


# ════════════════════════════════════════════════════════════════════════════
# 真实 binding 落地验证(端点对端点)
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("upstream,downstream,from_path,to_path", [
    ("/api/order/order/addOrder", "/api/order/order/orderDetail",
     ("data", "order_id"), ("order_id",)),
    ("/api/order/order/addOrder", "/api/order/order/cancelOrder",
     ("data", "order_id"), ("order_id",)),
    ("/api/order/order/addOrder", "/api/order/order/payOrder",
     ("data", "order_id"), ("order_id",)),
    ("/api/cart/cart/addCart", "/api/cart/cart/cartDetail",
     ("data", "cart_id"), ("cart_id",)),
    ("/api/cart/cart/addCart", "/api/cart/cart/updateCart",
     ("data", "cart_id"), ("cart_id",)),
    ("/api/address/address/addAddress", "/api/address/address/addressDetail",
     ("data", "address_id"), ("address_id",)),
    ("/api/address/address/addAddress", "/api/address/address/updateAddress",
     ("data", "address_id"), ("address_id",)),
    ("/api/invoice/invoice/addInvoice", "/api/invoice/invoice/invoiceDetail",
     ("data", "invoice_id"), ("invoice_id",)),
    ("/api/apply/apply/applyDetail", "/api/apply/apply/cancelApply",
     ("data", "apply_id"), ("apply_id",)),
])
def test_real_binding_pair_exists(upstream, downstream, from_path, to_path):
    """业务需求:真实业务依赖必须被 binding 表达。

    对应设计:§2.4 binding 落地表。
    业务影响:binding 缺失 = AI 不知道"调下游前必须调上游",Mock server 无法自动注入。
    """
    from Plate.core import registry

    # 找到下游端点
    downstream_spec = None
    for key, spec in registry._index.items():
        if key.service == "fin" and key.path == downstream:
            downstream_spec = spec
            break
    assert downstream_spec is not None, f"fin 服务找不到 {downstream}"

    # 校验下游有 binding,且 from_path / to_path 匹配
    assert len(downstream_spec.bindings) >= 1, (
        f"{downstream} 应至少有一个 binding,实际 0 个。"
        f"对应上游: {upstream}"
    )

    # 找 from_path == upstream_resp_path 的 binding
    matched = [
        b for b in downstream_spec.bindings
        if b.from_path == from_path and b.to_path == to_path
    ]
    assert matched, (
        f"{downstream} 缺 binding: from={from_path} to={to_path} (上游: {upstream})"
    )


# ════════════════════════════════════════════════════════════════════════════
# transform 真实落地验证
# ════════════════════════════════════════════════════════════════════════════

def test_pay_order_amount_binding_uses_int_to_str_transform():
    """业务需求:payOrder 的 amount binding 应使用 int->str transform。

    对应设计:§2.4 binding #4 特殊 case。
    业务影响:transform 错 = 注入时类型不匹配,Pydantic 校验失败 422。
    """
    from Plate.core import registry

    pay_order = None
    for key, spec in registry._index.items():
        if key.service == "fin" and key.path == "/api/order/order/payOrder":
            pay_order = spec
            break
    assert pay_order is not None

    amount_bindings = [
        b for b in pay_order.bindings
        if b.from_path == ("data", "amount") and b.to_path == ("amount",)
    ]
    assert amount_bindings, "payOrder 应有 amount binding"
    assert amount_bindings[0].transform == "int->str"


# ════════════════════════════════════════════════════════════════════════════
# 不变量聚合(binding from_path 在上游响应里真实存在)
# ════════════════════════════════════════════════════════════════════════════

# 在 test_invariants.py 加:
# def test_invariant_bindings_reference_real_paths():
#     """业务不变量:任何 binding 的 from_path 必须在某个上游响应模型里存在。
#
#     对应设计:§3 PR-D4 业务覆盖矩阵
#     业务影响:binding 引用幽灵路径 = AI 拿不到值,Mock server 注入失败。
#     """
#     from Plate.core import registry
#     from Plate.path_resolver import resolve_logical_path, PathResolutionError
#
#     # 收集所有 binding
#     all_bindings = []
#     for key, spec in registry._index.items():
#         for b in spec.bindings:
#             all_bindings.append((key.service, key.path, b))
#
#     # 找上游候选:同 service 下,所有 responses 包含 from_path[0] 对应字段的端点
#     # 简化:遍历所有 spec.response_model,验证 from_path 可解析
#     for service, path, b in all_bindings:
#         for key, upstream_spec in registry._index.items():
#             if key.service != service:
#                 continue
#             for status_code, resp_model in upstream_spec.responses.items():
#                 try:
#                     resolve_logical_path(resp_model, b.from_path)
#                     # 找到一个能解析的上游即可
#                     break
#                 except PathResolutionError:
#                     continue
#             else:
#                 continue
#             break
#         else:
#             pytest.fail(
#                 f"{service} {path}: binding from_path={b.from_path} "
#                 f"找不到任何上游响应能解析(可能是 from_path 写错或上游已删除)"
#             )


def test_invariant_no_orphan_bindings():
    """业务不变量:每个 binding 至少有一个同 service 的上游能解析 from_path。

    对应设计:§3 binding 落地表 + PR-D1 路径解析器。
    业务影响:orphan binding = 死代码,review pipeline 报警。
    """
    from Plate.core import registry
    from Plate.path_resolver import resolve_logical_path, PathResolutionError

    for key, spec in registry._index.items():
        for i, b in enumerate(spec.bindings):
            # 在同 service 内找上游
            found_upstream = False
            for uk, upstream_spec in registry._index.items():
                if uk.service != key.service:
                    continue
                for resp_model in upstream_spec.responses.values():
                    try:
                        resolve_logical_path(resp_model, b.from_path)
                        found_upstream = True
                        break
                    except PathResolutionError:
                        continue
                if found_upstream:
                    break
            assert found_upstream, (
                f"{key.service} {key.path}: bindings[{i}].from_path={b.from_path} "
                f"找不到任何上游响应能解析"
            )


# ════════════════════════════════════════════════════════════════════════════
# 不强凑:无上游的 QUERY 端点 bindings 应为空
# ════════════════════════════════════════════════════════════════════════════

def test_login_query_has_no_bindings():
    """业务需求:login 等独立 QUERY 端点 bindings=空是正确状态。

    对应设计:§1.2 "不强凑"。
    业务影响:强凑 binding = 引入假依赖,AI 误判调用前置条件。
    """
    from Plate.core import registry

    for key, spec in registry._index.items():
        if key.service == "fin" and "login" in key.path.lower():
            assert spec.category is EndpointCategory.QUERY
            assert spec.bindings == (), (
                f"{key.path} 是登录类独立查询,bindings 应为空,实际 {spec.bindings}"
            )


def test_dict_query_has_no_bindings():
    """业务需求:字典类 TOOL/QUERY 端点无业务实体依赖。

    对应设计:§1.2 "不强凑"。
    业务影响:字典类接口依赖业务实体 = 设计错乱(字典是系统级能力)。
    """
    from Plate.core import registry

    for key, spec in registry._index.items():
        if key.service == "fin" and "dict" in key.path.lower():
            assert spec.bindings == (), (
                f"{key.path} 是字典类接口,bindings 应为空"
            )


# ════════════════════════════════════════════════════════════════════════════
# 总数约束
# ════════════════════════════════════════════════════════════════════════════

def test_fin_total_binding_count_in_expected_range():
    """业务需求:fin 服务的 binding 总数应在 [8, 15] 区间。

    对应设计:§1.3 预估 9-12 个 binding。
    业务影响:总数过少(< 8) = 漏标;过多(> 15) = 强凑假依赖。
    """
    from Plate.core import registry

    total = sum(
        len(spec.bindings)
        for key, spec in registry._index.items()
        if key.service == "fin"
    )
    assert 8 <= total <= 15, (
        f"fin 服务的 binding 总数 {total} 不在预期区间 [8, 15],"
        f"可能漏标或强凑假依赖"
    )


def test_fin_query_endpoints_with_bindings_have_valid_upstream():
    """业务需求:任何有 binding 的 QUERY 端点,from_path 在至少一个上游响应里。

    对应设计:§3 binding 真实性。
    业务影响:binding 引用幽灵路径 = Mock server 注入时崩溃。
    """
    from Plate.core import registry
    from Plate.path_resolver import resolve_logical_path, PathResolutionError

    for key, spec in registry._index.items():
        if key.service != "fin" or not spec.bindings:
            continue
        assert spec.category is EndpointCategory.QUERY, (
            f"{key.path}: 只有 QUERY 端点应标 binding,实际 category={spec.category}"
        )

        for b in spec.bindings:
            # 在同 service 内尝试解析
            found = False
            for uk, upstream_spec in registry._index.items():
                if uk.service != "fin":
                    continue
                for resp_model in upstream_spec.responses.values():
                    try:
                        resolve_logical_path(resp_model, b.from_path)
                        found = True
                        break
                    except PathResolutionError:
                        continue
                if found:
                    break
            assert found, (
                f"{key.path}: binding from_path={b.from_path} 找不到上游"
            )
```

### 3.3 业务核心测试矩阵

| 业务承诺 | 测试函数 | 业务影响 |
|---|---|---|
| 真实 binding 落地 | `test_real_binding_pair_exists`(9 个参数化) | 跨端点依赖可被 AI 消费 |
| transform 正确性 | `test_pay_order_amount_binding_uses_int_to_str_transform` | 注入类型匹配 |
| 不强凑独立 QUERY | `test_login_query_has_no_bindings` / `test_dict_query_has_no_bindings` | 防假依赖 |
| 总数约束 | `test_fin_total_binding_count_in_expected_range` | 防漏标 / 强凑 |
| 不变量 | `test_invariant_no_orphan_bindings` / `test_fin_query_endpoints_with_bindings_have_valid_upstream` | 防幽灵 binding |

---

## 4. 收口验证

### 4.1 执行命令

```bash
# 1. 跑本 PR 专属测试
pytest tests/plate/test_fin_bindings.py -v

# 2. 跑不变量聚合
pytest tests/plate/test_invariants.py::test_invariant_no_orphan_bindings -v

# 3. 跑全量基线
pytest tests/  # 应 ≥ 206 + 15 = 221 个测试全过

# 4. 手动统计 binding 总数
python -c "
from Plate.core import registry
total = 0
for key, spec in registry._index.items():
    if key.service == 'fin':
        for b in spec.bindings:
            print(f'{key.path:60s} <- {b.from_path} -> {b.to_path} (transform={b.transform})')
            total += 1
print(f'总计: {total} bindings')
"

# 5. 故意制造"binding 引用幽灵路径"验证断言
python -c "
from Plate.spec import EndpointSpec
from Plate.binding import FieldBinding
from pydantic import BaseModel, ConfigDict
class R(BaseModel):
    model_config = ConfigDict(extra='forbid')
    x: str = ''
class M(BaseModel):
    model_config = ConfigDict(extra='forbid')
    y: str = ''
try:
    EndpointSpec(
        method='POST', path='/x',
        request=R, responses={200: M},
        bindings=(FieldBinding(from_path=('ghost', 'path'), to_path=('x',)),)
    )
    print('FAIL: 应抛 ValueError 或 PathResolutionError')
except Exception as e:
    print(f'OK: 拒绝幽灵 binding, {type(e).__name__}: {e}')
"
```

### 4.2 验收

| 项 | 值 |
|---|---|
| `test_fin_bindings.py` 测试数 | ≥ 15 |
| 失败 | 0 |
| fin binding 总数 | 在 [8, 15] 区间 |
| 故意制造幽灵 binding | 输出 `OK: 拒绝幽灵 binding` |

### 4.3 风险

| 风险 | 缓解 |
|---|---|
| 漏标真实 binding | `test_real_binding_pair_exists` 参数化覆盖 9 个候选对 |
| 强凑假 binding | `test_fin_total_binding_count_in_expected_range` 约束上限 |
| binding 引用幽灵路径 | `test_invariant_no_orphan_bindings` 聚合检查 |
| transform 拼写错 | `_KNOWN_TRANSFORMS` 白名单(PR-D2 已立) |

---

## 5. 与后续 PR 的衔接

- **PR-EOP**(收口 review pipeline):review pipeline 复用 `test_invariant_no_orphan_bindings` 逻辑做 CI gate
- **Phase 2**(service 化):AI skill 按 `bindings` 自动排调用顺序
- **Phase 3**(动态服务能力):Mock server 按 `bindings` 自动注入请求体
- **Phase 4**(CT 主动保活):CT 探测时按 `bindings` 反向找"前置未满足"的端点跳过