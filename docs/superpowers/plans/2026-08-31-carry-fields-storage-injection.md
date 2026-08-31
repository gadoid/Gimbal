# Carry 字段存储与注入 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 非绑定传递字段(备注/通知人等)统一存储于 platform 两张值表,materialize 单点在执行/导出前注入,plate 契约只声明字段面(`RequestSpec.carry`)。

**Architecture:** 三层:plate 契约层声明 carry 字段面(类型+描述,不带值)→ platform 值层(服务绑定表 + 全局默认表,PG)→ 注入层(dispatch 阶段预解析 `CarryContext`,`materialize_run_copy` 纯函数单点填充)。适配中心复用既有批机制管理值表 CRUD(CARRY_OPS)。

**Tech Stack:** Pydantic v2(plate 契约)/ FastAPI + SQLAlchemy async + SQLite(create_all 重建纪律)/ Vue 3 + vitest(前端)。

**Spec:** `docs/superpowers/specs/2026-08-31-carry-fields-storage-injection-design.md`(本计划从 spec 立论,执行者须同时读 spec)

## Global Constraints

- **测试命令**:plate = repo 根 `python -m pytest tests/plate/<file> -v`;backend = `cd src/gimbal-platform/backend && python -m pytest tests/<file> -v`;前端 = `cd src/gimbal-platform/frontend && npm test -- <路径>`(vitest run 过滤)。
- **PG 纪律**:普通列、无生成列;schema 变更 = DB 重建(create_all),**不做数据迁移**(spec 已拍板)。
- **契约禁令**(spec 2026-08-27 §1.6):任何 plate 目录驱动的回写不得触碰 `api.service`(用户引用键);`view_hints.endpoint_id` 才是目录锚点。
- **纯函数纪律**:`materialize_run_copy` 保持纯函数——plate 查询/DB 访问只出现在 dispatch 预解析阶段,以 `CarryContext` 纯值传入。
- **降级哲学**:plate 不可达/服务名解析失败 → 跳过填充 + 黄警日志,绝不阻塞执行/导出。
- **术语唯一化**:代码库中 "carry" 一词只指请求侧传递字段;响应侧 `field-defaults` 动作旧输出键 `carry_fields` 改名 `generated_fields`(Task 4)。
- 工作分支:`feat/scenario-vars-and-generator`。commit 信息中文,尾部加 `Co-Authored-By: Claude <noreply@anthropic.com>`。

---

### Task 1: plate 契约层 — CarryEntry + RequestSpec.carry

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py`(IOFieldBinding 之后、`_bindings_from_model` 之前插 CarryEntry;RequestSpec 加字段/校验/序列化)
- Test: `tests/plate/test_schema_endpoint.py`(文件末尾追加测试类)

**Interfaces:**
- Consumes: `gimbal_plate.utils.path`(io_spec 内已 import 为 `_path`,含 `is_valid_path`/`normalize`)
- Produces: `CarryEntry(BaseModel)`(字段 `description: str = ""`、`type: str = "string"`,extra=forbid);`RequestSpec.carry: dict[str, CarryEntry]`(键 = 归一化 JSONPath);序列化键 `carry`(dict[path → {description, type}])。Task 4/13 依赖此形状。

- [ ] **Step 1: 写失败测试**

在 `tests/plate/test_schema_endpoint.py` 末尾追加(文件已 import `RequestSpec`、`IOFieldBinding`;补 import `CarryEntry` 到既有 `from gimbal_plate.schema.endpoint.io_spec import ...`):

```python
class TestCarryEntry:
    """RequestSpec.carry —— 传递字段面(spec §2.1)。"""

    def test_carry_accepts_and_normalizes_keys(self) -> None:
        spec = RequestSpec(body_type="json", schema_={}, carry={"remark": CarryEntry()})
        assert list(spec.carry) == ["$.remark"]

    def test_carry_rejects_invalid_path(self) -> None:
        with pytest.raises(ValueError, match="不是合法 path"):
            RequestSpec(body_type="json", schema_={}, carry={"$[0]": CarryEntry()})

    def test_carry_disjoint_from_fields_paths(self) -> None:
        with pytest.raises(ValueError, match="交集非空"):
            RequestSpec(
                body_type="json", schema_={},
                fields=[IOFieldBinding(name="remark", path="$.remark")],
                carry={"$.remark": CarryEntry()},
            )

    def test_carry_type_vocabulary(self) -> None:
        CarryEntry(type="integer")  # 合法词表内
        with pytest.raises(ValueError, match="词表"):
            CarryEntry(type="timestamp")

    def test_carry_entry_extra_forbid(self) -> None:
        with pytest.raises(ValueError):
            CarryEntry(value="x")

    def test_serialize_carries_carry_key(self) -> None:
        spec = RequestSpec(
            body_type="json", schema_={},
            carry={"$.remark": CarryEntry(description="备注", type="string")},
        )
        data = spec.model_dump(mode="json")
        assert data["carry"] == {"$.remark": {"description": "备注", "type": "string"}}

    def test_serialize_omits_empty_carry(self) -> None:
        data = RequestSpec(body_type="json", schema_={}).model_dump(mode="json")
        assert "carry" not in data
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/plate/test_schema_endpoint.py::TestCarryEntry -v`
Expected: FAIL — `ImportError: cannot import name 'CarryEntry'`

- [ ] **Step 3: 最小实现**

`io_spec.py` 在 `IOFieldBinding` 类之后插入:

```python
class CarryEntry(BaseModel):
    """非绑定传递字段:不进表单,值随 platform 配置走(spec §2.1)。

    与 IOFieldBinding 正交(fields[] = 表单面,carry = 传递面):
    无 value / 无 ui_kind / 无 source_kind —— 值在 platform 两张值表,
    path 复用外层 dict 的键,不在 entry 内重复。
    """

    model_config = ConfigDict(extra="forbid")

    description: str = ""
    # JSON Schema 原语词表;materialize 注入时按此做宽松类型转换。
    # 自持 —— 不依赖 schema_ 反查,端点没有 schema_ 也能声明 carry。
    type: str = "string"

    @model_validator(mode="after")
    def _validate(self) -> "CarryEntry":
        if self.type not in (
            "string", "number", "integer", "boolean", "object", "array",
        ):
            raise ValueError(
                f"CarryEntry.type={self.type!r} 不在 JSON Schema 原语词表"
                f"(string/number/integer/boolean/object/array)"
            )
        return self
```

`RequestSpec` 加字段(在 `fields` 之后):

```python
    carry: dict[str, CarryEntry] = Field(default_factory=dict)
```

`RequestSpec._validate` 末尾(`return self` 之前)追加:

```python
        # carry 键:归一化 JSONPath,且与 fields[].path 互斥(一个字段
        # 不得同时出现在表单面与传递面,spec §2.1)
        if self.carry:
            normalized: dict[str, CarryEntry] = {}
            for raw, entry in self.carry.items():
                if not _path.is_valid_path(raw):
                    raise ValueError(
                        f"RequestSpec.carry 键 {raw!r} 不是合法 path"
                        f"(须为 JSONPath 形式或合法短名)"
                    )
                norm = _path.normalize(raw)
                if norm in normalized:
                    raise ValueError(f"RequestSpec.carry 归一后重复键 {norm!r}")
                normalized[norm] = entry
            overlap = {f.path for f in self.fields} & set(normalized)
            if overlap:
                raise ValueError(
                    f"carry 键与 fields[].path 交集非空: {sorted(overlap)}"
                )
            self.carry = normalized
```

`RequestSpec._serialize` 的 `out` 组装末尾(`schema` 分支之后)追加:

```python
        if self.carry:
            out["carry"] = {k: v.model_dump(mode="json")
                            for k, v in self.carry.items()}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/plate/test_schema_endpoint.py -v`
Expected: 全 PASS(含既有用例——carry 缺省 `{}`,不影响现状)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py tests/plate/test_schema_endpoint.py
git commit -m "feat(plate): RequestSpec.carry 传递字段面 — CarryEntry 契约与校验"
```

---

### Task 2: plate 契约层 — model 机制移除(schema 层)

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py`(删 model/_bindings_from_model/validate_body/rule B 收敛/序列化去 model 键)
- Modify: `src/gimbal-plate/gimbal_plate/design/ENDPOINT_SPEC_V2.md`(model 段落加退役注记)
- Modify: `tests/plate/conftest.py:112-126,162-163`(fixtures 去 model=)
- Modify: `tests/plate/fixtures/sample_endpoint.py:40-54`(同上)
- Test: `tests/plate/test_schema_endpoint.py`(规则用例改写)、`tests/plate/test_e2e_c1_c2.py:70-73`

**Interfaces:**
- Consumes: Task 1 的 carry(序列化保留)。
- Produces: `RequestSpec`/`ResponseSpec` 不再有 `model` 字段、`validate_body` 方法、`_bindings_from_model`;`json_schema()` 恒返回 `schema_`;序列化输出只有 `body_type/fields/schema/carry`(request)与 `status/description/fields/assertable_fields/schema`(response)。Task 3/4 依赖。

- [ ] **Step 1: 改写规则测试(先行 — 旧断言在新行为下必炸,等价 TDD 红)**

`tests/plate/test_schema_endpoint.py`:

1. `test_body_type_none_with_empty_model_and_schema_passes`(L148):去掉 model 语境,改为:
```python
    def test_body_type_none_with_nothing_passes(self) -> None:
        spec = RequestSpec(body_type="none")
        assert spec.schema_ is None
```
2. `test_body_type_none_with_model_rejected`(L155-161):**删除**。
3. `test_body_type_none_with_schema_rejected`(L165):保留(错误信息里 model 字样改掉,见 Step 3 实现)。
4. `test_body_type_json_with_model_only_passes`(L173-178):改写为 schema_ 单轴 + 无派生断言:
```python
    def test_body_type_json_with_schema_only_passes_no_derivation(self) -> None:
        # model 派生已退役:fields 只来自显式声明,不再自动填充
        spec = RequestSpec(body_type="json", schema_=_OrderReq.model_json_schema())
        assert spec.fields == []
```
(原 `test_body_type_json_with_schema_only_passes` L182 保留;上面这条并入或替换 L173 用例均可,保留一条即可——执行时删除 L173-180 原用例,用此新用例顶替。)
5. `test_body_type_json_with_both_model_and_schema_passes`(L189-197):**删除**(rule C/model 并存语境消失)。
6. `test_body_type_json_empty_both_rejected`(L203):保留;match 文案对齐新报错(见 Step 3)。
7. `test_body_type_json_with_empty_dict_schema_rejected_when_no_model`(L220-225):改名为 `test_body_type_json_with_empty_dict_schema_passes_per_q_a`,参数里去 `model=None`:
```python
    def test_body_type_json_with_empty_dict_schema_passes_per_q_a(self) -> None:
        # Q-A a2:schema_={} 视为"已声明",合法
        spec = RequestSpec(body_type="json", schema_={})
        assert spec.schema_ == {}
```
8. `test_model_dump_json_carries_key_fields`(L621-629,用 order_endpoint fixture):model_schema 断言改为:
```python
        assert "model_schema" not in data["request"]
        assert "model_name" not in data["request"]
        assert "schema" in data["request"]   # fixture 改写后 schema_ 在
```

`tests/plate/test_e2e_c1_c2.py` L70-73 改为:

```python
    assert "schema" in data["request"]
    assert "model_schema" not in data["request"]
    assert "schema" in data["responses"]["200"]
    assert "model_schema" not in data["responses"]["200"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/plate/test_schema_endpoint.py tests/plate/test_e2e_c1_c2.py -v`
Expected: FAIL —— `RequestSpec.__init__` 收到未知关键字 `model`(fixtures 还在用 model=)/ 断言不匹配

- [ ] **Step 3: 实现 — io_spec.py 删改**

`RequestSpec`:
- 删字段 `model: type[BaseModel] | None = None`;
- `_validate` 规则 A 收敛(去 model 分支):
```python
        if self.body_type == "none":
            if self.schema_ is not None:
                raise ValueError(
                    f"RequestSpec.body_type='none' 时 schema_ 必须为 None,"
                    f"实际为 {self.schema_!r}"
                )
        # 规则 B(model 机制退役后单轴):body_type != none 时 schema_ 必须非 None。
        # schema_={} 视为"已声明"(Q-A a2)。
        elif self.schema_ is None:
            raise ValueError(
                f"RequestSpec.body_type={self.body_type!r} 时 schema_ 必须非 None"
            )
```
- 删派生块(`if not self.fields and self.model is not None: ...`)与规则 C 注释;
- `json_schema()` 改为 `return self.schema_`;
- **删** `validate_body` 方法;
- `_serialize` 删 model 分支,最终为:
```python
    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "body_type": self.body_type,
            "fields": [f.model_dump(mode="json") for f in self.fields],
        }
        if self.schema_ is not None:
            out["schema"] = self.schema_
        if self.carry:
            out["carry"] = {k: v.model_dump(mode="json")
                            for k, v in self.carry.items()}
        return out
```
- `model_config` 里 `arbitrary_types_allowed=True` 可一并删除(model 类引用是唯一 arbitrary 类型;若 ResponseSpec 尚未删净则先留,本 Task 内两处都删)。

`ResponseSpec`:删 `model` 字段、`json_schema()` 的 model 分支(改 `return self.schema_`)、`_serialize` 的 `if self.model is not None: ...` 两行块。

模块级:**删** `_bindings_from_model` 整个函数(L71-109)。

`tests/plate/conftest.py`:
- `order_endpoint`(L112-126):`model=OrderIn` → `schema_=OrderIn.model_json_schema()`;`model=OrderOut` → `schema_=OrderOut.model_json_schema()`(fields 原本显式,不动);
- `order_patch_endpoint`(L162-163):`model=OrderPatch` 且**无 fields** —— 必须显式补(否则 fields 派生断链):
```python
        request=RequestSpec(
            body_type="json",
            schema_=OrderPatch.model_json_schema(),
            fields=[
                IOFieldBinding(name="order_id", path="order_id", required=True,
                               ui_kind="text"),
                IOFieldBinding(name="status", path="status", required=True,
                               ui_kind="text"),
            ],
        ),
        responses={200: ResponseSpec(status=200, schema_=OrderOut.model_json_schema())},
```

`tests/plate/fixtures/sample_endpoint.py`(L42/54):`model=OrderIn` → `schema_=OrderIn.model_json_schema()`,`model=OrderOut` → `schema_=OrderOut.model_json_schema()`(fields 已显式)。

`ENDPOINT_SPEC_V2.md`:找到 model/Pydantic 派生段落,加一行注记:`> 2026-08-31:model 机制已退役(spec carry 设计 §2.1.1)——schema_ 为唯一结构真源,fields 只来自显式声明。`

- [ ] **Step 4: 跑受影响测试面**

Run: `python -m pytest tests/plate/test_schema_endpoint.py tests/plate/test_e2e_c1_c2.py tests/plate/test_v3_export_platform.py tests/plate/test_http_full_endpoint.py -v`
Expected: 全 PASS(fields_meta 覆盖断言靠显式 fields 成立)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py src/gimbal-plate/gimbal_plate/design/ENDPOINT_SPEC_V2.md tests/plate/conftest.py tests/plate/fixtures/sample_endpoint.py tests/plate/test_schema_endpoint.py tests/plate/test_e2e_c1_c2.py
git commit -m "refactor(plate): model 机制退役 — schema_ 单轴 + fields 显式声明(spec §2.1.1)"
```

---

### Task 3: plate 导出链 — _render_body 退恒等 + EndpointCaseExporter 适配

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/export/gimbal.py:191-195`(`_render_body`)
- Test: `tests/plate/test_case_exporter.py:118-140`(TestBodyValidation 改写)、`tests/plate/test_v3_export_gimbal.py:60-61,85`

**Interfaces:**
- Consumes: Task 2(model 已不存在,`validate_body` 已删)。
- Produces: `EndpointCaseExporter._render_body` = 插值恒等(与平台链路行为对齐:plate 从不校验 body)。

- [ ] **Step 1: 改写测试**

`tests/plate/test_case_exporter.py` 的 `TestBodyValidation`(L118 起)整体替换为:

```python
class TestBodyRendering:
    def test_request_body_passes_through_interpolated(self, order_endpoint) -> None:
        # model 机制退役(spec §2.1.1):_render_body 只做 ${var} 插值,不再校验
        case = EndpointCase(
            name="passthrough",
            parameters={"order_no": "X", "amount": 5},
        )
        exporter = EndpointCaseExporter(order_endpoint)
        step = exporter.to_gimbal_step(case)
        body = step["request"]["body"]
        assert body == {"order_no": "X", "amount": 5}

    def test_request_none_returns_interpolated(self, order_patch_endpoint) -> None:
        case = EndpointCase(
            name="raw",
            parameters={"order_id": "X", "status": "ok"},
        )
        exporter = EndpointCaseExporter(order_patch_endpoint)
        step = exporter.to_gimbal_step(case)
```

(第二个用例断言 `step["request"]["body"] == {"order_id": "X", "status": "ok"}` —— 原 L139 之后就是这句,保留。)

`tests/plate/test_v3_export_gimbal.py` `_endpoint()`(L60-61):

```python
            request=RequestSpec(body_type="json",
                                schema_=_InBody.model_json_schema()),
            responses={200: ResponseSpec(status=200,
                                         schema_=_OutBody.model_json_schema())},
```

L85 注释行 `# request body 应当经过 validate_body 链路(因为 _InBody 有 model)` 改为 `# model 退役:body 原样(插值后)透传`。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/plate/test_case_exporter.py tests/plate/test_v3_export_gimbal.py -v`
Expected: FAIL —— `export/gimbal.py` 还在调 `self.endpoint.request.validate_body`(AttributeError)

- [ ] **Step 3: 实现**

`export/gimbal.py` `_render_body`(L191-195)替换为:

```python
    def _render_body(self, params: dict[str, Any]) -> Any:
        """model 机制退役(spec §2.1.1):只做 ${var} 插值,不校验 —— 与
        平台主链路(plate /convert 从不校验 body)行为对齐。"""
        return _interpolate_params(params, self.variables)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/plate/test_case_exporter.py tests/plate/test_v3_export_gimbal.py tests/plate/test_e2e_c1_c2.py -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-plate/gimbal_plate/export/gimbal.py tests/plate/test_case_exporter.py tests/plate/test_v3_export_gimbal.py
git commit -m "refactor(plate): EndpointCaseExporter._render_body 退恒等 — validate_body 随 model 机制退役"
```

---

### Task 4: plate — fin 存量端点显式改写 + generated_fields 改名

**Files:**
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/settlement_create_order.py`
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/account_query_balance.py`
- Modify: `src/gimbal-plate/gimbal_plate/service/field_defaults.py:84-106`
- Test: `tests/plate/test_http_field_defaults.py:101,104-122`、`tests/plate/test_v3_systems_fin.py:102-104`

**Interfaces:**
- Consumes: Task 1 的 `CarryEntry`。
- Produces: `fin.settlement.create_order` 声明 `carry={"$.remark": ...}`(平台侧 E2E 的 carry 面样本);`field-defaults` 动作输出键 `generated_fields`。Task 9/10 的 plate mock face 依赖 `request.carry` 形状。

- [ ] **Step 1: 改写测试**

`tests/plate/test_http_field_defaults.py`:
- L101:`assert data["carry_fields"] == []` → `assert data["generated_fields"] == []`
- L104 测试名 `test_field_defaults_carry_fields_from_response` → `test_field_defaults_generated_fields_from_response`
- L120-122:
```python
    generated = resp.json()["data"]["generated_fields"]
    assert generated and generated[0]["name"] == "internal_note"
    assert generated[0]["carry"] is True
```
- `_build_endpoint`(L45-74):`model=_ReqIn` → `schema_=_ReqIn.model_json_schema()`;`model=_RespOut` → `schema_=_RespOut.model_json_schema()`(fields 显式,保留)。

`tests/plate/test_v3_systems_fin.py` L102-104(`test_create_order_request_validate_body`)替换为:

```python
    def test_create_order_request_face(self) -> None:
        rs = SETTLEMENT_CREATE_ORDER.request
        assert rs is not None
        assert [f.name for f in rs.fields] == ["order_id", "amount", "currency"]
        assert list(rs.carry) == ["$.remark"]
```

(文件顶部若未 import SETTLEMENT_CREATE_ORDER 则补;`rs.validate_body` 引用删除。)

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/plate/test_http_field_defaults.py tests/plate/test_v3_systems_fin.py -v`
Expected: FAIL —— 端点还在用 model=;输出键还是 carry_fields

- [ ] **Step 3: 实现**

`settlement_create_order.py`:import 区加 `IOFieldBinding`(from `gimbal_plate.schema.endpoint`)与 `CarryEntry`(from `gimbal_plate.schema.endpoint.io_spec`);`request`/`responses` 替换为:

```python
    request=RequestSpec(
        body_type="json",
        schema_=CreateOrderRequest.model_json_schema(),
        fields=[
            IOFieldBinding(name="order_id", path="$.order_id", required=True,
                           description="业务订单号"),
            IOFieldBinding(name="amount", path="$.amount", required=True,
                           description="结算金额,单位分", ui_kind="number"),
            IOFieldBinding(name="currency", path="$.currency", required=False,
                           default="CNY", description="币种"),
        ],
        # 传递面(spec §2):备注是典型 carry 字段 —— 值随 platform 配置走
        carry={"$.remark": CarryEntry(description="备注(随请求传递,不进表单)")},
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            schema_=CreateOrderResponse.model_json_schema(),
        ),
    },
```

`account_query_balance.py`:`model=QueryBalanceResponse` → `schema_=QueryBalanceResponse.model_json_schema()`。

`field_defaults.py` L84-106:`carry_fields` 变量与输出键改名 `generated_fields`,注释块改为:

```python
    # generated_fields: placeholders for the schema-only / generated channel.
    # (响应侧 generated 字段清单;2026-08-31 起 "carry" 一词专指请求侧
    #  传递字段 —— RequestSpec.carry,spec carry 设计 §2.1.1 术语唯一化。)
    generated_fields: list[dict[str, Any]] = []
    resp_200 = endpoint.responses.get(200)
    if resp_200 is not None:
        for f in resp_200.fields:
            if f.source_kind != "generated":
                continue
            generated_fields.append(
                {
                    "name": f.name,
                    "type": f.ui_kind if f.ui_kind != "unknown" else "string",
                    "carry": True,
                    "default": f.default if f.default is not None else "",
                }
            )

    return {
        "field_defaults": field_defaults,
        "generated_fields": generated_fields,
    }
```

(`"carry": True` 行内键是历史输出形状,零消费方,保留不动 —— 改的只是顶层键名。)

- [ ] **Step 4: 跑 plate 全量回归**

Run: `python -m pytest tests/plate -v`
Expected: 全 PASS(model 退役 + carry 落地后的完整回归面)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-plate/gimbal_plate/systems/fin/endpoint/settlement_create_order.py src/gimbal-plate/gimbal_plate/systems/fin/endpoint/account_query_balance.py src/gimbal-plate/gimbal_plate/service/field_defaults.py tests/plate/test_http_field_defaults.py tests/plate/test_v3_systems_fin.py
git commit -m "feat(plate): fin 端点显式 fields + carry 面声明;field-defaults 输出键 carry_fields→generated_fields"
```

---

### Task 5: backend 值层 — PG 两表 + carry_store

**Files:**
- Create: `src/gimbal-platform/backend/app/models/carry_binding.py`
- Modify: `src/gimbal-platform/backend/app/models/__init__.py`(注册两模型)
- Create: `src/gimbal-platform/backend/app/services/carry_store.py`
- Test: `src/gimbal-platform/backend/tests/test_carry_store.py`

**Interfaces:**
- Consumes: `app.core.db.Base`。
- Produces(Task 6/9/12 依赖):
  - `CarryServiceBinding` / `CarryGlobalDefault`(表 `carry_service_bindings` / `carry_global_defaults`)
  - `async def get_bindings(db, service_name: str) -> dict[str, str | None]`
  - `async def put_bindings(db, service_name: str, entries: dict[str, str | None], updated_by: str) -> None`(整体替换该服务行集;value=None 写 NULL 行)
  - `async def get_defaults(db) -> dict[str, str | None]`
  - `async def put_defaults(db, entries: dict[str, str | None], updated_by: str) -> None`

- [ ] **Step 1: 写失败测试**

`src/gimbal-platform/backend/tests/test_carry_store.py`:

```python
"""carry 值层两表 — 行存在即注入;value=None 显式 null;行不存在=未配置(spec §3.1)。"""
from __future__ import annotations

from app.core import db as db_module
from app.services import carry_store


async def _db():
    return db_module.SessionLocal()


async def test_put_get_bindings_roundtrip(fresh_db):
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(db, "fin-service",
                                       {"$.remark": "压测-张三",
                                        "$.notifyUsers": None}, "alice")
        await db.commit()
    async with db_module.SessionLocal() as db:
        got = await carry_store.get_bindings(db, "fin-service")
    assert got == {"$.remark": "压测-张三", "$.notifyUsers": None}


async def test_put_replaces_whole_row_set(fresh_db):
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(db, "s", {"$.a": "1", "$.b": "2"}, "u")
        await carry_store.put_bindings(db, "s", {"$.a": "1x"}, "u")
        await db.commit()
        assert await carry_store.get_bindings(db, "s") == {"$.a": "1x"}


async def test_defaults_null_semantics(fresh_db):
    async with db_module.SessionLocal() as db:
        await carry_store.put_defaults(db, {"$.appCode": "TRACE-V2",
                                            "$.remark": None}, "bob")
        await db.commit()
        defaults = await carry_store.get_defaults(db)
    assert defaults == {"$.appCode": "TRACE-V2", "$.remark": None}
    # 行不存在才是"未配置":键不在 dict 里
    assert "$.absent" not in defaults
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_carry_store.py -v`
Expected: FAIL — `No module named 'app.services.carry_store'`

- [ ] **Step 3: 实现**

`app/models/carry_binding.py`:

```python
"""carry 值层存储(spec §3.1):服务绑定表 + 全局默认表。

null 语义(写死):行存在即声明注入,value=NULL 注入 JSON null(显式空);
行不存在才是"未配置",走降级链。配置页 placeholder 依赖此语义。
值统一存 str(模板 ${var.x} 原样),注入时按契约 type 宽松转换。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class CarryServiceBinding(Base):
    __tablename__ = "carry_service_bindings"
    __table_args__ = (
        UniqueConstraint("service_name", "field_path", name="uq_carry_svc_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 目录服务名(derive_base 解析产物,非用户引用键)
    service_name: Mapped[str] = mapped_column(String(128), index=True)
    field_path: Mapped[str] = mapped_column(String(255))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class CarryGlobalDefault(Base):
    __tablename__ = "carry_global_defaults"
    __table_args__ = (
        UniqueConstraint("field_path", name="uq_carry_default_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    field_path: Mapped[str] = mapped_column(String(255))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

`app/models/__init__.py`:import 区加 `from .carry_binding import CarryGlobalDefault, CarryServiceBinding`,`__all__` 加 `"CarryGlobalDefault", "CarryServiceBinding"`。

`app/services/carry_store.py`:

```python
"""carry 值层读写(spec §3.2 API 的 store 面)。

PUT 语义 = 整体替换(行集 diff:删缺键、upsert 在键);调用方负责 commit。
"""
from __future__ import annotations

from sqlalchemy import delete, select

from ..models.carry_binding import CarryGlobalDefault, CarryServiceBinding


async def get_bindings(db, service_name: str) -> dict[str, str | None]:
    rows = (await db.execute(
        select(CarryServiceBinding).where(
            CarryServiceBinding.service_name == service_name)
    )).scalars().all()
    return {r.field_path: r.value for r in rows}


async def put_bindings(
    db, service_name: str, entries: dict[str, str | None], updated_by: str
) -> None:
    await db.execute(delete(CarryServiceBinding).where(
        CarryServiceBinding.service_name == service_name))
    for path, value in sorted(entries.items()):
        db.add(CarryServiceBinding(service_name=service_name,
                                   field_path=path, value=value,
                                   updated_by=updated_by))


async def get_defaults(db) -> dict[str, str | None]:
    rows = (await db.execute(select(CarryGlobalDefault))).scalars().all()
    return {r.field_path: r.value for r in rows}


async def put_defaults(
    db, entries: dict[str, str | None], updated_by: str
) -> None:
    await db.execute(delete(CarryGlobalDefault))
    for path, value in sorted(entries.items()):
        db.add(CarryGlobalDefault(field_path=path, value=value,
                                  updated_by=updated_by))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_carry_store.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/models/carry_binding.py src/gimbal-platform/backend/app/models/__init__.py src/gimbal-platform/backend/app/services/carry_store.py src/gimbal-platform/backend/tests/test_carry_store.py
git commit -m "feat(platform): carry 两表(服务绑定/全局默认)+ store — null 语义钉死"
```

---

### Task 6: backend — carry router(API 面)

**Files:**
- Create: `src/gimbal-platform/backend/app/schemas/carry.py`
- Create: `src/gimbal-platform/backend/app/routers/carry.py`
- Modify: `src/gimbal-platform/backend/app/main.py`(注册 router,在 scenarios 之前)
- Test: `src/gimbal-platform/backend/tests/test_carry_api.py`

**Interfaces:**
- Consumes: Task 5 store;`app.core.deps.AdminUser/CurrentUser`;conftest 的 `plate` fixture(EndpointPlateMock,处理 `/api/endpoint` 与 `/full`)。
- Produces(Task 11/14/15/16 依赖):
  - `GET /api/carry/defaults` → `{"defaults": {"$.path": "v" | null}}`(CurrentUser)
  - `PUT /api/carry/defaults` body 同形状(AdminUser)
  - `GET /api/carry/bindings` → `{"bindings": {"svc": {"$.p": v | null}}}`(CurrentUser;全部服务)
  - `GET /api/carry/bindings/{service}` → `{"bindings": {...}}`(CurrentUser)
  - `PUT /api/carry/bindings/{service}` body `{"bindings": {...}}`(AdminUser)
  - `GET /api/carry/bindings/{service}/fields` → `{"fields": [{"path","type","description"}]}`(AdminUser;plate /full 聚合该服务 carry 面并集)

- [ ] **Step 1: 写失败测试**

`src/gimbal-platform/backend/tests/test_carry_api.py`:

```python
"""carry API 面(spec §3.2)— 读写权限分治 + 字段面聚合。"""
from __future__ import annotations

from .test_scenario_visibility_and_copy import _member


async def _admin(client):
    from .helpers import register_and_login
    return await register_and_login(client, "carry-admin", "pw123456")


async def test_defaults_roundtrip_and_null_row(client):
    admin = await _admin(client)
    r = await client.put("/api/carry/defaults", headers=admin,
                         json={"defaults": {"$.appCode": "TRACE-V2",
                                            "$.remark": None}})
    assert r.status_code == 200, r.text
    r = await client.get("/api/carry/defaults", headers=admin)
    assert r.json()["defaults"] == {"$.appCode": "TRACE-V2", "$.remark": None}


async def test_bindings_put_get_per_service(client):
    admin = await _admin(client)
    r = await client.put("/api/carry/bindings/fin-service", headers=admin,
                         json={"bindings": {"$.remark": "压测-张三"}})
    assert r.status_code == 200, r.text
    r = await client.get("/api/carry/bindings/fin-service", headers=admin)
    assert r.json()["bindings"] == {"$.remark": "压测-张三"}
    r = await client.get("/api/carry/bindings", headers=admin)
    assert r.json()["bindings"] == {"fin-service": {"$.remark": "压测-张三"}}


async def test_write_requires_admin(client):
    member = await _member(client, "carry-mem")
    r = await client.put("/api/carry/defaults", headers=member,
                         json={"defaults": {}})
    assert r.status_code == 403


async def test_service_fields_aggregates_carry_face(client, plate):
    """该服务全部接口的 carry 面并集(plate /full 聚合)。"""
    plate.items = [{"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
                    "service": "fin-service"}]
    plate.fulls = {"fin.ep1": {"request": {"carry": {
        "$.remark": {"type": "string", "description": "备注"}}}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/bindings/fin-service/fields",
                         headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["fields"] == [
        {"path": "$.remark", "type": "string", "description": "备注"}]
```

注:`helpers.py` 若无 `register_and_login`,改用文件内既有注册登录 helper 的实际名字(执行时 `grep -n "def " tests/helpers.py` 确认,`test_scenario_visibility_and_copy._member` 同款写法)。plate mock 的列表过滤:EndpointPlateMock 不过滤 service → fields 聚合须按 full 的 `service` 字段比对,见 Step 3。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_carry_api.py -v`
Expected: FAIL — 404(路由不存在)

- [ ] **Step 3: 实现**

`app/schemas/carry.py`:

```python
"""carry API 请求/响应模型(spec §3.2)。dict 的 null 值 = 显式 null 行;
键缺席 = 未配置(spec §3.1)。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CarryMapIn(BaseModel):
    bindings: dict[str, str | None] = Field(default_factory=dict)


class DefaultsIn(BaseModel):
    defaults: dict[str, str | None] = Field(default_factory=dict)


class DefaultsOut(BaseModel):
    defaults: dict[str, str | None] = Field(default_factory=dict)


class BindingsOut(BaseModel):
    bindings: dict[str, dict[str, str | None]] = Field(default_factory=dict)


class ServiceBindingsOut(BaseModel):
    bindings: dict[str, str | None] = Field(default_factory=dict)


class CarryFieldFace(BaseModel):
    path: str
    type: str = "string"
    description: str = ""


class ServiceFieldsOut(BaseModel):
    fields: list[CarryFieldFace] = Field(default_factory=list)
```

`app/routers/carry.py`:

```python
"""carry 配置面路由(spec §3.2):读 CurrentUser(编排器提示要用),
写 AdminUser(平台配置维护者)。字段面聚合走 plate /full。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser, CurrentUser
from ..models.carry_binding import CarryServiceBinding
from ..schemas.carry import (
    BindingsOut,
    CarryFieldFace,
    CarryMapIn,
    DefaultsIn,
    DefaultsOut,
    ServiceBindingsOut,
    ServiceFieldsOut,
)
from ..services import carry_store
from ..services.plate_client import PlateUnavailableError

router = APIRouter(prefix="/carry", tags=["carry"])

DbSession = Depends(get_db)


def _svc_map(rows) -> dict[str, dict[str, str | None]]:
    out: dict[str, dict[str, str | None]] = {}
    for r in rows:
        out.setdefault(r.service_name, {})[r.field_path] = r.value
    return out


@router.get("/defaults", response_model=DefaultsOut)
async def get_defaults(user: CurrentUser, db=DbSession):
    return DefaultsOut(defaults=await carry_store.get_defaults(db))


@router.put("/defaults", response_model=DefaultsOut)
async def put_defaults(user: AdminUser, db=DbSession, body: DefaultsIn = None):
    await carry_store.put_defaults(db, body.defaults, user.username)
    await db.commit()
    return DefaultsOut(defaults=await carry_store.get_defaults(db))


@router.get("/bindings", response_model=BindingsOut)
async def list_bindings(user: CurrentUser, db=DbSession):
    rows = (await db.execute(select(CarryServiceBinding))).scalars().all()
    return BindingsOut(bindings=_svc_map(rows))


@router.get("/bindings/{service}", response_model=ServiceBindingsOut)
async def get_bindings(service: str, user: CurrentUser, db=DbSession):
    return ServiceBindingsOut(
        bindings=await carry_store.get_bindings(db, service))


@router.put("/bindings/{service}", response_model=ServiceBindingsOut)
async def put_bindings(service: str, user: AdminUser, db=DbSession,
                       body: CarryMapIn = None):
    await carry_store.put_bindings(db, service, body.bindings, user.username)
    await db.commit()
    return ServiceBindingsOut(
        bindings=await carry_store.get_bindings(db, service))


@router.get("/bindings/{service}/fields", response_model=ServiceFieldsOut)
async def service_fields(service: str, user: AdminUser, db=DbSession):
    """该服务全部接口 carry 面并集:GET /api/endpoint?service= → 逐 id /full。"""
    from ..services.adaptation_service import _plate_full_endpoint

    client_items = await _plate_list_endpoints_filtered(service)
    faces: dict[str, CarryFieldFace] = {}
    for item in client_items:
        try:
            full = await _plate_full_endpoint(item["id"])
        except PlateUnavailableError:
            continue  # 降级:该端点面缺席,不阻塞其余
        if full is None:
            continue
        carry = ((full.get("request") or {}).get("carry")) or {}
        for path, entry in carry.items():
            faces.setdefault(path, CarryFieldFace(
                path=path,
                type=str(entry.get("type") or "string"),
                description=str(entry.get("description") or ""),
            ))
    return ServiceFieldsOut(fields=sorted(faces.values(), key=lambda f: f.path))


async def _plate_list_endpoints_filtered(service: str) -> list[dict]:
    """轻量列表按 service 过滤(adaptation_service._plate_list_endpoints 复用)。"""
    from ..services.adaptation_service import _plate_list_endpoints

    items = await _plate_list_endpoints()
    return [it for it in items if it.get("service") == service]
```

`app/main.py`:import 区加 `carry`,注册行(在 `adaptations` 之后、`scenarios` 之前):

```python
    app.include_router(carry.router, prefix="/api")
```

注:`_plate_list_endpoints` 返回的轻量条目含 `service` 字段(EndpointView 轻视图有 id/method/path/description/module/tags —— 执行时确认;若无 service 字段,改为不过滤列表、逐 id 拉 full 后按 `full["service"]` 比对,测试同构)。PUT body 参数写成 `body: DefaultsIn = None` 防 FastAPI 对 body 的歧义 —— 执行时若 lint 报警,改为显式 `Body(...)` 默认工厂。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_carry_api.py tests/test_carry_store.py -v`
Expected: 4 + 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/schemas/carry.py src/gimbal-platform/backend/app/routers/carry.py src/gimbal-platform/backend/app/main.py src/gimbal-platform/backend/tests/test_carry_api.py
git commit -m "feat(platform): /api/carry API 面 — defaults/bindings/字段面聚合"
```

---

### Task 7: backend — 服务名推导 derive_base 移植

**Files:**
- Create: `src/gimbal-platform/backend/app/services/service_names.py`
- Test: `src/gimbal-platform/backend/tests/test_service_names.py`

**Interfaces:**
- Consumes: `plate_client.get_client()`。
- Produces(Task 9/10 依赖):
  - `def derive_base(key: str, catalog_names: set[str]) -> str | None`(纯函数)
  - `async def catalog_service_names() -> set[str]`(GET /api/service → data.items[].name;plate 失败 → 空集,降级)

- [ ] **Step 1: 写失败测试**

`src/gimbal-platform/backend/tests/test_service_names.py`:

```python
"""derive_base 后端移植(spec §4.2)—— 前端 service-alias.ts 的同逻辑。"""
from __future__ import annotations

import httpx
import pytest

from app.services import service_names
from app.services import plate_client


def test_direct_catalog_hit():
    names = {"fin-service", "fin-order-service"}
    assert service_names.derive_base("fin-service", names) == "fin-service"


def test_alias_suffix_stripped_at_last_dash():
    names = {"fin-service"}
    # 最后一个 "-" 切分:目录名自身可含 "-",base 永远是最长候选
    assert service_names.derive_base("fin-service-qa1", names) == "fin-service"
    assert service_names.derive_base("fin-service-x-y", names) == "fin-service"


def test_bare_declaration_returns_null_no_guess():
    assert service_names.derive_base("unknown-svc", {"fin-service"}) is None
    assert service_names.derive_base("", {"fin-service"}) is None


async def test_catalog_service_names_fetches_plate():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/service"
        return httpx.Response(200, json={
            "ok": True, "dim": "service",
            "data": {"items": [{"name": "fin-service"},
                               {"name": "track-trace-service"}],
                     "total": 2},
        })

    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://plate-test"))
    try:
        names = await service_names.catalog_service_names()
    finally:
        plate_client.set_client_for_tests(None)
    assert names == {"fin-service", "track-trace-service"}


async def test_catalog_unavailable_degrades_to_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://plate-test"))
    try:
        assert await service_names.catalog_service_names() == set()
    finally:
        plate_client.set_client_for_tests(None)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_service_names.py -v`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 实现**

`app/services/service_names.py`:

```python
"""服务名别名推导(spec §4.2)—— 前端 service-alias.ts deriveBase 的后端移植。

别名 = <目录服务名>-<后缀>;切分点固定在最后一个 "-",base 必须落在目录
集合内才生效(裸声明不猜)。目录集合来自 plate services 列表;plate 不可达
→ 空集 → 全部裸声明(该 step 跳过填充 + 黄警,不阻塞执行)。
"""
from __future__ import annotations

import httpx

from .plate_client import PlateUnavailableError, get_client


def derive_base(key: str, catalog_names: set[str]) -> str | None:
    if not key:
        return None
    if key in catalog_names:
        return key
    i = key.rfind("-")
    if i <= 0:
        return None
    base = key[:i]
    return base if base in catalog_names else None


async def catalog_service_names() -> set[str]:
    """GET /api/service → data.items[].name;失败 → 空集(降级)。"""
    client = get_client()
    try:
        resp = await client.get("/api/service")
    except httpx.HTTPError:
        return set()
    if resp.status_code != 200:
        return set()
    items = (resp.json().get("data") or {}).get("items")
    if not isinstance(items, list):
        return set()
    return {str(it.get("name")) for it in items
            if isinstance(it, dict) and it.get("name")}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_service_names.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/service_names.py src/gimbal-platform/backend/tests/test_service_names.py
git commit -m "feat(platform): derive_base 后端移植 — 目录服务名推导 + 降级空集"
```

---

### Task 8: backend — materialize carry 填充(纯函数)

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/run_materialize.py`(CarryContext + _apply_carry + 类型转换)
- Test: `src/gimbal-platform/backend/tests/test_run_materialize.py`(追加测试类)

**Interfaces:**
- Consumes: Task 1 定下的 carry 面(经 Task 9 预解析进入 context;本 Task 不触 plate/DB)。
- Produces(Task 9/10 依赖):
  - `@dataclass(frozen=True) class CarryContext`:`step_fields: dict[int, dict[str, str]]`(step 索引 → {path: 契约类型};键缺席 = 无锚点)、`service_bindings: dict[str, dict[str, str | None] | None]`(键 = step.api.service 原始引用串;值 None = 解析失败整步跳过)、`global_defaults: dict[str, str | None]`
  - `materialize_run_copy(..., carry_context: CarryContext | None = None)`(缺省 None 行为与现状逐字段一致)

- [ ] **Step 1: 写失败测试**

`tests/test_run_materialize.py` 末尾追加:

```python
# ─── carry 填充(spec §4)────────────────────────────────────────
from app.services.run_materialize import CarryContext


def _carry_converted() -> dict:
    return {
        "kind": "scenario",
        "config": {"services": {}, "users": {}, "vars": {}},
        "steps": [
            {"kind": "step",
             "api": {"service": "fin-service", "path": "/x",
                     "view_hints": {"endpoint_id": "fin.ep1"}},
             "request": {"kind": "request", "body": {"order_id": "o-1"}}},
        ],
    }


def _ctx(**over) -> CarryContext:
    base = dict(
        step_fields={0: {"$.remark": "string", "$.appCode": "string",
                          "$.count": "integer", "$.flag": "boolean",
                          "$.meta": "object", "$.tpl": "string"}},
        service_bindings={"fin-service": {"$.remark": "压测-张三",
                                           "$.count": "3"}},
        global_defaults={"$.appCode": "TRACE-V2", "$.flag": "true",
                          "$.meta": "{\"k\": 1}"},
    )
    base.update(over)
    return CarryContext(**base)


class TestCarryFill:
    def test_service_binding_wins_over_default(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            global_defaults={"$.remark": "全局备注", "$.appCode": "V2"}))
        body = out["steps"][0]["request"]["body"]
        assert body["remark"] == "压测-张三"

    def test_global_default_fills_unbound_path(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx())
        assert out["steps"][0]["request"]["body"]["appCode"] == "TRACE-V2"

    def test_body_existing_key_skipped(self):
        src = _carry_converted()
        src["steps"][0]["request"]["body"]["remark"] = "手填值"
        out = materialize_run_copy(src, carry_context=_ctx())
        assert out["steps"][0]["request"]["body"]["remark"] == "手填值"

    def test_two_layers_absent_skips(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            step_fields={0: {"$.nosuch": "string"}}))
        assert "nosuch" not in out["steps"][0]["request"]["body"]

    def test_null_row_injects_json_null(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            service_bindings={"fin-service": {"$.remark": None}}))
        assert out["steps"][0]["request"]["body"]["remark"] is None

    def test_type_coercion(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx())
        body = out["steps"][0]["request"]["body"]
        assert body["count"] == 3            # integer
        assert body["flag"] is True          # boolean 严格 true/false
        assert body["meta"] == {"k": 1}      # object JSON 解析

    def test_coerce_failure_keeps_original_string(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            service_bindings={"fin-service": {"$.count": "3x"}},
            global_defaults={"$.meta": "{not-json}"}))
        body = out["steps"][0]["request"]["body"]
        assert body["count"] == "3x"
        assert body["meta"] == "{not-json}"

    def test_template_value_passes_through_uncoerced(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            service_bindings={"fin-service": {"$.tpl": "${var.envId}",
                                              "$.count": "${var.n}"}}))
        body = out["steps"][0]["request"]["body"]
        assert body["tpl"] == "${var.envId}"
        assert body["count"] == "${var.n}"   # 模板不做二次 coerce

    def test_unresolved_service_skips_whole_step(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            service_bindings={"fin-service": None}))
        body = out["steps"][0]["request"]["body"]
        assert "appCode" not in body and "remark" not in body

    def test_no_anchor_falls_back_to_value_table_keys(self):
        out = materialize_run_copy(_carry_converted(), carry_context=_ctx(
            step_fields={}))
        body = out["steps"][0]["request"]["body"]
        # 降级门控:候选 = 绑定键 ∪ 全局默认键
        assert body["remark"] == "压测-张三"
        assert body["appCode"] == "TRACE-V2"

    def test_carry_context_none_behaves_as_today(self):
        out = materialize_run_copy(_carry_converted())
        assert out["steps"][0]["request"]["body"] == {"order_id": "o-1"}

    def test_pure_function_input_not_mutated_carry(self):
        src = _carry_converted()
        materialize_run_copy(src, carry_context=_ctx())
        assert src["steps"][0]["request"]["body"] == {"order_id": "o-1"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_run_materialize.py -v`
Expected: FAIL — `ImportError: CarryContext`

- [ ] **Step 3: 实现**

`run_materialize.py`:

文件头 import 区改/加:

```python
import copy
import json
from dataclasses import dataclass
from typing import Any
```

`materialize_run_copy` 签名加参(在 `built_in_users` 之后):

```python
    carry_context: "CarryContext | None" = None,
```

docstring 追加一行:`* carry:预解析上下文注入(填缺失语义;spec §4)`。函数体 `return out` 之前加:

```python
    if carry_context is not None:
        _apply_carry(out, carry_context)
```

模块级追加:

```python
@dataclass(frozen=True)
class CarryContext:
    """dispatch 阶段预解析的注入上下文(纯值,spec §4.1)。

    * step_fields:step 索引 → 该 endpoint 的 carry 面 {path: 契约类型}。
      键缺席 = 该 step 无锚点(存量无 view_hints)→ 降级门控。
    * service_bindings:键 = step.api.service 原始引用串(可含别名前缀);
      值 = 该目录服务的 {path: value};值 None = 服务名解析失败,
      整步跳过(黄警由 dispatch 记)。
    * global_defaults:path → value(全局默认表整表)。
    * 二期预留:数据集行值层插在服务绑定之前(订单组绑定,spec §8)。
    """
    step_fields: dict[int, dict[str, str]]
    service_bindings: dict[str, dict[str, str | None] | None]
    global_defaults: dict[str, str | None]
```

`_apply_carry` 及辅助:

```python
def _path_parts(path: str) -> list[str]:
    return path[2:].split(".") if path.startswith("$.") else path.split(".")


def _body_has(body: dict, path: str) -> bool:
    cur: Any = body
    for seg in _path_parts(path):
        if not isinstance(cur, dict) or seg not in cur:
            return False
        cur = cur[seg]
    return True


def _body_set(body: dict, path: str, value: Any) -> None:
    parts = _path_parts(path)
    cur = body
    for seg in parts[:-1]:
        if not isinstance(cur.get(seg), dict):
            cur[seg] = {}
        cur = cur[seg]
    cur[parts[-1]] = value


def _coerce_carry_value(value: str, ftype: str) -> Any:
    """宽松转换(与数据集 _coerce_row_value 同哲学);失败保留原串。"""
    try:
        if ftype == "integer":
            return int(value)
        if ftype == "number":
            return float(value)
        if ftype == "boolean":
            if value in ("true", "True"):
                return True
            if value in ("false", "False"):
                return False
            return value
        if ftype in ("object", "array"):
            return json.loads(value)
    except (ValueError, json.JSONDecodeError):
        pass
    return value


def _apply_carry(out: dict[str, Any], ctx: CarryContext) -> None:
    """carry 填充(spec §4.2):填缺失语义 — body 已有键绝不覆盖。"""
    for i, step in enumerate(out.get("steps") or []):
        if not isinstance(step, dict):
            continue
        api = step.get("api")
        svc = api.get("service") if isinstance(api, dict) else None
        if not isinstance(svc, str) or not svc:
            continue
        if svc in ctx.service_bindings and ctx.service_bindings[svc] is None:
            continue  # 服务名解析失败(dispatch 已黄警):整步跳过
        bound = ctx.service_bindings.get(svc) or {}
        candidates = ctx.step_fields.get(i)
        if candidates is None:
            # 降级门控(无锚点存量 step):候选 = 绑定键 ∪ 全局默认键
            candidates = {**bound, **ctx.global_defaults}
        request = step.get("request")
        if not isinstance(request, dict):
            continue
        body = request.get("body")
        if not isinstance(body, dict):
            continue
        for path, ftype in candidates.items():
            if _body_has(body, path):
                continue                    # body 显式值最优先
            if path in bound:
                value = bound[path]
            elif path in ctx.global_defaults:
                value = ctx.global_defaults[path]
            else:
                continue                    # 两层皆无 → 本次不注入
            if value is None:
                _body_set(body, path, None)  # 行存在+null → 显式 JSON null
            elif isinstance(value, str) and "${" in value:
                _body_set(body, path, value)  # 模板原样透传,gimbal 解析
            else:
                _body_set(body, path,
                          _coerce_carry_value(str(value), ftype))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_run_materialize.py -v`
Expected: 全 PASS(含既有 12 条 —— carry_context 缺省 None 等价现状)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/run_materialize.py src/gimbal-platform/backend/tests/test_run_materialize.py
git commit -m "feat(platform): materialize carry 填充 — CarryContext 纯函数单点(spec §4)"
```

---

### Task 9: backend — 执行链 dispatch 预解析

**Files:**
- Create: `src/gimbal-platform/backend/app/services/carry_injection.py`
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py`(fanout 内构造 + 传参,L575-578 区域与 L660-668 调用点)
- Test: `src/gimbal-platform/backend/tests/test_run_carry_injection.py`

**Interfaces:**
- Consumes: Task 7 `derive_base`/`catalog_service_names`;Task 8 `CarryContext`/`materialize_run_copy(carry_context=)`;Task 5 store;`scenario_store.definition_from_payload`。
- Produces: `async def build_carry_context(db, definition: dict) -> CarryContext`(db = AsyncSession;plate 全部失败 → 空 face/空目录,不 raise;黄警 logger.warning)。Task 10 复用。

- [ ] **Step 1: 写失败测试**

`src/gimbal-platform/backend/tests/test_run_carry_injection.py`:

```python
"""执行链 carry 注入 E2E(spec §4)— dispatch 预解析 + materialize 填充。"""
from __future__ import annotations

from app.core import db as db_module
from app.services import carry_store

from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member


def _carry_step() -> dict:
    return {"kind": "step",
            "api": {"service": "fin-service", "path": "/x",
                    "view_hints": {"endpoint_id": "fin.settlement.create_order"}},
            "request": {"kind": "request", "body": {"order_id": "o-1"}}}


async def _seed_values():
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "压测-张三"}, "alice")
        await carry_store.put_defaults(db, {"$.appCode": "TRACE-V2"}, "alice")
        await db.commit()


async def test_run_injects_carry_into_case_body(
        client, plate_mock: PlateMock, monkeypatch):
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]
    plate_mock.fulls = {
        "fin.settlement.create_order": {"request": {"carry": {
            "$.remark": {"type": "string"},
            "$.appCode": {"type": "string"}}}},
    }
    await _seed_values()
    bob = await _member(client, "bob")
    r = await client.post("/api/scenarios", headers=bob,
                          json={"definition": {"steps": [_carry_step()]},
                                "orchestration": {}})
    assert r.status_code in (200, 201), r.text

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload())
    assert r.status_code == 201, r.text
    from .helpers import wait_until as _wait
    await _wait(lambda: len(cases) >= 1)
    body = cases[0]["steps"][0]["request"]["body"]
    assert body["remark"] == "压测-张三"   # 服务绑定
    assert body["appCode"] == "TRACE-V2"   # 全局默认
    assert body["order_id"] == "o-1"       # body 原值不动


async def test_run_carry_degrades_when_plate_face_unavailable(
        client, plate_mock: PlateMock, monkeypatch):
    """face 拉不到 → 无锚点候选(绑定∪默认),仍可注入;不阻塞执行。"""
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]  # 无 fulls → face 空
    await _seed_values()
    bob = await _member(client, "bob")
    await client.post("/api/scenarios", headers=bob,
                      json={"definition": {"steps": [_carry_step()]},
                            "orchestration": {}})
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    await client.post("/api/runs", headers=bob, json=_run_payload())
    from .helpers import wait_until as _wait
    await _wait(lambda: len(cases) >= 1)
    body = cases[0]["steps"][0]["request"]["body"]
    assert body["remark"] == "压测-张三"
```

(draft 形状与 `_run_payload`/`_member` 的确切签名执行时从 `test_run_m1_capabilities.py`/`test_export_overlay_equivalence.py` 抄 —— 那里是同款 run E2E 的现成写法;`make_draft` helper(`tests/helpers.py`)若适用则直接 `make_draft(steps=[_carry_step()])`。)

另:`PlateMock` 需扩展 `services`/`fulls` 属性(见 Step 3,属本 Task 的测试基建改动)。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_run_carry_injection.py -v`
Expected: FAIL — `PlateMock` 无 `services` 属性 / body 无注入

- [ ] **Step 3: 实现**

先扩展 `tests/test_scenario_composer_plate_integration.py` 的 `PlateMock.__init__`(L37-40 区域)加两个属性:

```python
        self.fulls: dict[str, dict] = {}   # endpoint_id → full spec(carry 面)
        # 空目录 → derive_base 全失败 → carry 全跳过:
        # 既有等价测试行为不变(兼容关键),carry 用例自行注入服务
        self.services: list[dict] = []
```

`install()` 的 handler 里(convert 分支之外)追加:

```python
            if path == "/api/service":
                return httpx.Response(200, json={
                    "ok": True, "dim": "service",
                    "data": {"items": self.services,
                             "total": len(self.services)},
                })
            if path.endswith("/full") and path.startswith("/api/endpoint/"):
                eid = path.rsplit("/", 2)[-2]
                if eid in self.fulls:
                    return httpx.Response(200, json={
                        "ok": True, "dim": "endpoint",
                        "data": {"item": self.fulls[eid], "total": 1},
                    })
                return httpx.Response(404, json={"ok": False})
```

`app/services/carry_injection.py`:

```python
"""carry 注入预解析(spec §4.1)— dispatch/导出共用的 CarryContext 构造。

纯 IO 组装:plate 查询(锚点 → carry 面、services 目录)+ 两张值表读取
+ derive_base 服务名解析。任何 plate 故障都降级(空面/空目录),绝不
阻塞执行/导行;DB 故障向上传播(本地存储,属 5xx 语义)。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from . import carry_store, plate_client, service_names
from .run_materialize import CarryContext

logger = logging.getLogger(__name__)


async def _carry_face(endpoint_id: str) -> dict[str, str]:
    """plate /full → {path: type};任何失败 → {}(降级)。"""
    client = plate_client.get_client()
    try:
        resp = await client.get(f"/api/endpoint/{endpoint_id}/full")
    except Exception:  # noqa: BLE001 — httpx 全家 + 超时,统一降级
        return {}
    if resp.status_code != 200:
        return {}
    item = (resp.json().get("data") or {}).get("item")
    if not isinstance(item, dict):
        return {}
    carry = ((item.get("request") or {}).get("carry")) or {}
    return {str(p): str(e.get("type") or "string")
            for p, e in carry.items() if isinstance(e, dict)}


async def build_carry_context(db: AsyncSession, definition: dict) -> CarryContext:
    steps = [s for s in (definition.get("steps") or [])
             if isinstance(s, dict)]

    # ① 锚点 → carry 面(按 endpoint_id 去重批量,不逐 step 打 plate)
    endpoint_ids: dict[str, None] = {}
    for step in steps:
        hints = ((step.get("api") or {}).get("view_hints")) or {}
        eid = hints.get("endpoint_id") if isinstance(hints, dict) else None
        if eid:
            endpoint_ids.setdefault(eid, None)
    faces: dict[str, dict[str, str]] = {
        eid: await _carry_face(eid) for eid in endpoint_ids
    }
    step_fields: dict[int, dict[str, str]] = {}
    for i, step in enumerate(steps):
        hints = ((step.get("api") or {}).get("view_hints")) or {}
        eid = hints.get("endpoint_id") if isinstance(hints, dict) else None
        if eid and faces.get(eid):
            step_fields[i] = faces[eid]

    # ② 服务引用 → derive_base 解析 → 绑定值(None = 解析失败,整步跳过)
    catalog = await service_names.catalog_service_names()
    defaults = await carry_store.get_defaults(db)
    raw_services: dict[str, None] = {}
    for step in steps:
        svc = (step.get("api") or {}).get("service")
        if isinstance(svc, str) and svc:
            raw_services.setdefault(svc, None)
    service_bindings: dict[str, dict[str, str | None] | None] = {}
    for raw in raw_services:
        base = service_names.derive_base(raw, catalog)
        if base is None:
            logger.warning(
                "carry_injection: service %r 不在目录(裸声明)— 该 step "
                "跳过 carry 填充", raw)
            service_bindings[raw] = None
        else:
            service_bindings[raw] = await carry_store.get_bindings(db, base)

    return CarryContext(step_fields=step_fields,
                        service_bindings=service_bindings,
                        global_defaults=defaults)
```

`run_dispatcher.py` `_fanout`(L575 `built_in_users = ...` 之后):

```python
    # carry 预解析(spec §4.1):dispatch 阶段一次,run 内快照一致 —
    # 绑定/契约编辑的生效边界是下次执行。plate 故障在 build 内部降级;
    # DB 故障属本地 5xx,让 fanout 的既有异常面接住(整单失败)。
    from .carry_injection import build_carry_context
    try:
        async with db_factory() as _carry_db:
            carry_ctx = await build_carry_context(
                _carry_db, definition_from_payload(scenario_payload))
    except Exception:  # noqa: BLE001 — carry 绝不阻塞执行
        logger.warning("run_dispatcher: carry context build failed; skipped",
                       exc_info=True)
        carry_ctx = None
```

(`db_factory` 的会话开法执行时对齐 `_resolve_exec_auths` 内既有写法 —— `grep -n "db_factory()" app/services/run_dispatcher.py`。)

`materialize_run_copy` 调用点(L660-668)追加参数:

```python
                    composed_exec = materialize_run_copy(
                        converted,
                        service_bindings={...},
                        resolved_auths=exec_auths,
                        built_in_users=built_in_users,
                        carry_context=carry_ctx,
                    )
```

- [ ] **Step 4: 跑测试确认通过 + 回归**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_run_carry_injection.py tests/test_run_materialize.py tests/test_export_overlay_equivalence.py -v`
Expected: 全 PASS(等价测试不破 —— PlateMock 默认空 services → carry 全跳过)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/services/carry_injection.py src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/tests/test_run_carry_injection.py src/gimbal-platform/backend/tests/test_scenario_composer_plate_integration.py
git commit -m "feat(platform): 执行链 carry 预解析 — dispatch 构造 CarryContext,plate 故障降级"
```

---

### Task 10: backend — 导出链 wiring + 黄金等价扩展

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/scenarios.py:151-179`(overlay 分支)
- Test: `src/gimbal-platform/backend/tests/test_export_overlay_equivalence.py`(追加用例)

**Interfaces:**
- Consumes: Task 9 `build_carry_context`;既有 overlay 分支结构。
- Produces: 导出产物 body 含按当前绑定物化的 carry 值(快照语义);黄金等价 carry 扩展。

- [ ] **Step 1: 写失败测试**

`tests/test_export_overlay_equivalence.py` 追加(文件末尾):

```python
# ─── carry 黄金等价(spec §4.3)────────────────────────────────────
from app.core import db as db_module
from app.services import carry_store


def _carry_step() -> dict:
    return {"kind": "step",
            "api": {"service": "fin-service", "path": "/x",
                    "view_hints": {"endpoint_id": "fin.ep1"}},
            "request": {"kind": "request", "body": {"order_id": "o-1"}}}


async def test_golden_equivalence_with_carry(
        client, plate_mock: PlateMock, monkeypatch):
    """carry 物化同源:导出产物 ≡ 基线单行 case.json,含注入后的 carry 值。"""
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]
    plate_mock.fulls = {"fin.ep1": {"request": {"carry": {
        "$.remark": {"type": "string"},
        "$.appCode": {"type": "string"}}}}}
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "压测-张三"}, "bob")
        await carry_store.put_defaults(db, {"$.appCode": "TRACE-V2"}, "bob")
        await db.commit()

    bob = await _member(client, "bob")
    await client.post("/api/scenarios", headers=bob,
                      json=_draft(steps=[_carry_step()], vars_map={},
                                  **_META))
    await _seed_owner_auth("qa1")
    await _seed_owner_auth("qa2")

    exported = (await client.post(
        "/api/scenarios/preview-plate", headers=bob,
        json={**_eq_draft_with_carry(), "overlay": OVERLAY})).json()["converted"]
    body = exported["steps"][0]["request"]["body"]
    assert body["remark"] == "压测-张三"
    assert body["appCode"] == "TRACE-V2"

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    r = await client.post("/api/runs", headers=bob, json=_run_payload(
        dataSetIds=[], serviceBindings=OVERLAY["serviceBindings"]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert cases[0] == exported


def _eq_draft_with_carry() -> dict:
    """同 _eq_draft 但 step 换成带 carry 锚点的形态。"""
    return _draft(steps=[_carry_step()], vars_map={}, **_META)
```

注意:`_eq_draft` 的 `_STEP` 模板引用 qa1/qa2;carry step 的 headers 也带上同样的 Authorization/X-Api-Key(保持并集断言成立):

```python
def _carry_step() -> dict:
    return {"kind": "step",
            "api": {"service": "fin-service", "path": "/x",
                    "headers": {"Authorization": "${auth.qa1.token}",
                                "X-Api-Key": "${auth.qa2.token}"},
                    "view_hints": {"endpoint_id": "fin.ep1"}},
            "request": {"kind": "request", "body": {"order_id": "o-1"}}}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_export_overlay_equivalence.py -v`
Expected: 新用例 FAIL(exported body 无 remark/appCode —— 导出链还没接 carry)

- [ ] **Step 3: 实现**

`scenarios.py` overlay 分支(`built_in = ...` 之后、`converted = materialize_run_copy(` 之前)插入:

```python
        # carry 同源注入(spec §4.3):与 dispatch 共用 build_carry_context
        # → 导出产物 = 绑定状态的当时快照。plate 故障在 build 内部降级
        # (不注入,不 5xx);DB 故障走既有 500 面。
        from ..services.carry_injection import build_carry_context
        try:
            carry_ctx = await build_carry_context(db, body.definition)
        except Exception:  # noqa: BLE001 — carry 绝不阻塞导出
            carry_ctx = None
```

`materialize_run_copy(...)` 调用(L173-179)追加:

```python
        converted = materialize_run_copy(
            converted,
            service_bindings={k: b.model_dump(by_alias=True)
                              for k, b in body.overlay.service_bindings.items()},
            resolved_auths=exec_auths,
            built_in_users=dict(built_in or {}),
            carry_context=carry_ctx,
        )
```

(顶部 import 区加 `from ..services.carry_injection import build_carry_context`,函数内 import 删除。)

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_export_overlay_equivalence.py tests/test_run_carry_injection.py -v`
Expected: 全 PASS(既有 4 条不破 + 新 carry 等价成立)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/routers/scenarios.py src/gimbal-platform/backend/tests/test_export_overlay_equivalence.py
git commit -m "feat(platform): 导出链 carry 同源注入 — 黄金等价扩展至 carry 值"
```

---

### Task 11: backend — drift 漂移端点

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/carry_store.py`(追加 drift 计算)
- Modify: `src/gimbal-platform/backend/app/routers/carry.py`(GET /api/carry/drift)
- Modify: `src/gimbal-platform/backend/app/schemas/carry.py`(drift 模型)
- Test: `src/gimbal-platform/backend/tests/test_carry_drift.py`

**Interfaces:**
- Consumes: Task 6 router/store;plate 列表 + /full(Task 6 已引入的 helper)。
- Produces(Task 16 依赖):`GET /api/carry/drift`(AdminUser)→ `{"services": [{"service", "orphaned": [path], "uncovered": [path], "renamedSuggestions": [{"from","to"}]}]}`。

- [ ] **Step 1: 写失败测试**

`src/gimbal-platform/backend/tests/test_carry_drift.py`:

```python
"""carry 漂移 diff(spec §7)— plate 面 vs 两表 paths 三类结果。"""
from __future__ import annotations

from app.core import db as db_module
from app.services import carry_store

from .test_carry_api import _admin


async def _seed():
    async with db_module.SessionLocal() as db:
        # fin-service:$.old 绑了但 plate 面已无(orphaned);
        # $.new 面上有但没绑(uncovered);$.remark 面上有且有绑(对齐)
        await carry_store.put_bindings(
            db, "fin-service", {"$.old": "x", "$.remark": "r"}, "alice")
        await db.commit()


async def test_drift_three_classes(client, plate):
    await _seed()
    plate.items = [{"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
                    "service": "fin-service"}]
    plate.fulls = {"fin.ep1": {"request": {"carry": {
        "$.remark": {"type": "string"},
        "$.new": {"type": "string"}}}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    assert r.status_code == 200, r.text
    services = r.json()["services"]
    fin = next(s for s in services if s["service"] == "fin-service")
    assert fin["orphaned"] == ["$.old"]
    assert sorted(fin["uncovered"]) == ["$.new"]
    # 单 orphaned × 单 uncovered(同 string)→ rename 建议
    assert fin["renamedSuggestions"] == [{"from": "$.old", "to": "$.new"}]


async def test_drift_empty_when_aligned(client, plate):
    await _seed()
    plate.items = [{"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
                    "service": "fin-service"}]
    plate.fulls = {"fin.ep1": {"request": {"carry": {
        "$.remark": {"type": "string"}, "$.old": {"type": "string"}}}}}
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    fin = next(s for s in r.json()["services"] if s["service"] == "fin-service")
    assert fin["orphaned"] == [] and fin["uncovered"] == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_carry_drift.py -v`
Expected: FAIL — 404(无 /drift 路由)

- [ ] **Step 3: 实现**

`schemas/carry.py` 追加:

```python
class ServiceDrift(BaseModel):
    service: str
    orphaned: list[str] = Field(default_factory=list)
    uncovered: list[str] = Field(default_factory=list)
    renamedSuggestions: list[dict[str, str]] = Field(default_factory=list)


class DriftReport(BaseModel):
    services: list[ServiceDrift] = Field(default_factory=list)
```

`carry_store.py` 追加:

```python
async def carry_drift(db) -> list[dict]:
    """plate carry 面 vs 绑定表 paths 三类 diff(spec §7;结构 diff,非 semver)。

    renamed 启发式:单 orphaned × 单 uncovered(同 type 不可知 —— 绑定行
    无类型)→ 配对建议;多候选不猜,人工构造 op。
    """
    from .adaptation_service import _plate_list_endpoints, _plate_full_endpoint
    from .plate_client import PlateUnavailableError

    rows = (await db.execute(select(CarryServiceBinding))).scalars().all()
    bound_by_service: dict[str, set[str]] = {}
    for r in rows:
        bound_by_service.setdefault(r.service_name, set()).add(r.field_path)

    # 面并集(按服务)
    face_by_service: dict[str, set[str]] = {}
    try:
        items = await _plate_list_endpoints()
    except PlateUnavailableError:
        items = []
    for item in items:
        svc = item.get("service")
        eid = item.get("id")
        if not svc or not eid:
            continue
        try:
            full = await _plate_full_endpoint(eid)
        except PlateUnavailableError:
            continue
        if full is None:
            continue
        carry = ((full.get("request") or {}).get("carry")) or {}
        face_by_service.setdefault(svc, set()).update(carry.keys())

    out: list[dict] = []
    for svc in sorted(set(bound_by_service) | set(face_by_service)):
        bound = bound_by_service.get(svc, set())
        face = face_by_service.get(svc, set())
        orphaned = sorted(bound - face)
        uncovered = sorted(face - bound)
        suggestions = ([{"from": orphaned[0], "to": uncovered[0]}]
                       if len(orphaned) == 1 and len(uncovered) == 1 else [])
        if orphaned or uncovered:
            out.append({"service": svc, "orphaned": orphaned,
                        "uncovered": uncovered,
                        "renamedSuggestions": suggestions})
    return out
```

`routers/carry.py` 追加:

```python
@router.get("/drift", response_model=DriftReport)
async def drift(user: AdminUser, db=DbSession):
    return DriftReport(services=[
        ServiceDrift(**s) for s in await carry_store.carry_drift(db)])
```

(注意路由顺序:`/drift` 是字面量,须注册在 `/bindings/{service}` 之类参数路由**不冲突**(前缀不同)—— FastAPI 按声明序匹配,`/drift` 与 `/defaults`/`/bindings` 平级无冲突。)

- [ ] **Step 4: 跑测试确认通过**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_carry_drift.py tests/test_carry_api.py -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/schemas/carry.py src/gimbal-platform/backend/app/services/carry_store.py src/gimbal-platform/backend/app/routers/carry.py src/gimbal-platform/backend/tests/test_carry_drift.py
git commit -m "feat(platform): GET /api/carry/drift — orphaned/uncovered/renamed 三类漂移"
```

---

### Task 12: backend — AdaptationOp 可空 + CARRY_OPS + carry 批

**Files:**
- Modify: `src/gimbal-platform/backend/app/models/adaptation_op.py:23`(scenario_id 可空)
- Modify: `src/gimbal-platform/backend/app/schemas/adaptations.py:54-65,94-100`(OpOut/OpCreateIn 可空)
- Modify: `src/gimbal-platform/backend/app/services/adaptation_ops.py`(CARRY_OPS 族)
- Modify: `src/gimbal-platform/backend/app/services/adaptation_service.py`(open_carry_batch/apply 分流/快照/回滚/stamp 跳过)
- Modify: `src/gimbal-platform/backend/app/routers/adaptations.py`(POST /carry-batches)
- Test: `src/gimbal-platform/backend/tests/test_adaptation_carry_ops.py`

**Interfaces:**
- Consumes: Task 5 carry_store;既有批机制(AdaptationBatch/AdaptationSnapshot/AdaptationOp)。
- Produces(Task 16 依赖):
  - `CARRY_OPS = ("renameCarryPath", "addCarryBinding", "removeCarryBinding")`,payload `{service?: str, from?/to?/path?/value?}`(service 缺省 = 全局默认表)
  - `POST /api/adaptations/carry-batches` body `{"service": str | null}` → BatchDetail(batch.endpoint_id = `carry:{service or 'global'}`)
  - `create_op` 对 CARRY_OPS 免 scenario_id;快照 entity_type `carry_binding`(entity_id=service)/ `carry_default`(entity_id=`__global__`),before_json = `{path: value}`
  - apply/rollback 对称;carry 批完成**不推**CatalogVersion 戳。

- [ ] **Step 1: 写失败测试**

`src/gimbal-platform/backend/tests/test_adaptation_carry_ops.py`:

```python
"""CARRY_OPS 值表批(spec §7)— 开批/快照/应用/回滚;场景定义零变化。"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models import AdaptationOp, ComposerScenario
from app.services import carry_store

from .test_carry_api import _admin


async def _open_carry_batch(client, admin, service=None):
    r = await client.post("/api/adaptations/carry-batches", headers=admin,
                          json={"service": service})
    assert r.status_code == 201, r.text
    return r.json()["batchId"]


async def _add_op(client, admin, batch_id, op_type, payload):
    r = await client.post(f"/api/adaptations/batches/{batch_id}/ops",
                          headers=admin,
                          json={"opType": op_type, "payload": payload})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_carry_ops_apply_and_snapshot(client):
    admin = await _admin(client)
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.old": "v1"}, "alice")
        await db.commit()

    batch_id = await _open_carry_batch(client, admin, "fin-service")
    op1 = await _add_op(client, admin, batch_id, "renameCarryPath",
                        {"service": "fin-service", "from": "$.old",
                         "to": "$.new"})
    op2 = await _add_op(client, admin, batch_id, "addCarryBinding",
                        {"service": None, "path": "$.appCode",
                         "value": "TRACE-V2"})

    for op_id in (op1, op2):
        r = await client.post(f"/api/adaptations/ops/{op_id}/apply",
                              headers=admin)
        assert r.status_code == 200, r.text

    async with db_module.SessionLocal() as db:
        assert await carry_store.get_bindings(db, "fin-service") == {"$.new": "v1"}
        assert await carry_store.get_defaults(db) == {"$.appCode": "TRACE-V2"}


async def test_carry_batch_rollback_restores(client):
    admin = await _admin(client)
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.old": "v1"}, "alice")
        await db.commit()

    batch_id = await _open_carry_batch(client, admin, "fin-service")
    op_id = await _add_op(client, admin, batch_id, "renameCarryPath",
                          {"service": "fin-service", "from": "$.old",
                           "to": "$.new"})
    await client.post(f"/api/adaptations/ops/{op_id}/apply", headers=admin)

    r = await client.post(f"/api/adaptations/batches/{batch_id}/rollback",
                          headers=admin)
    assert r.status_code == 200, r.text
    async with db_module.SessionLocal() as db:
        assert await carry_store.get_bindings(db, "fin-service") == {"$.old": "v1"}


async def test_carry_batch_never_touches_scenarios(client):
    """D1 红利断言:carry 批前后场景定义零变化。"""
    admin = await _admin(client)
    bob_headers = await _member_headers(client)
    r = await client.post("/api/scenarios", headers=bob_headers,
                          json={"definition": {"steps": []},
                                "orchestration": {}})
    sid = r.json()["scenarioId"]
    async with db_module.SessionLocal() as db:
        before = (await db.execute(
            select(ComposerScenario).where(
                ComposerScenario.scenario_id == sid))).scalar_one().payload

    batch_id = await _open_carry_batch(client, admin)
    op_id = await _add_op(client, admin, batch_id, "addCarryBinding",
                          {"service": None, "path": "$.x", "value": "1"})
    await client.post(f"/api/adaptations/ops/{op_id}/apply", headers=admin)

    async with db_module.SessionLocal() as db:
        after = (await db.execute(
            select(ComposerScenario).where(
                ComposerScenario.scenario_id == sid))).scalar_one().payload
    assert before == after


async def _member_headers(client):
    from .test_scenario_visibility_and_copy import _member
    return await _member(client, "carry-bob")
```

(空 steps 的 draft 若被 scenario_store 拒绝,改用 `tests/helpers.py` 的 `make_draft(steps=[...一条最小 step...])`。)

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_adaptation_carry_ops.py -v`
Expected: FAIL — 404(carry-batches 路由不存在)/ OpCreateIn scenario_id min_length 拒绝

- [ ] **Step 3: 实现**

1. `models/adaptation_op.py` L23:
```python
    # carry 值表类 op 无场景落点(spec §7/D1 红利)→ 可空
    scenario_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
```

2. `schemas/adaptations.py`:`OpCreateIn.scenario_id` → `scenario_id: str | None = Field(default=None, alias="scenarioId")`;`OpOut.scenario_id` → `scenario_id: str | None = Field(default=None, alias="scenarioId")`。

3. `adaptation_ops.py` 族声明区追加:
```python
# carry 值表类 op(触 platform 两张值表;service 缺省 = 全局默认表)
CARRY_OPS = ("renameCarryPath", "addCarryBinding", "removeCarryBinding")
ALL_OPS = STEP_OPS + DATASET_OPS + GLOBAL_OPS + CARRY_OPS
```

4. `adaptation_service.py`:
- `apply_op` 分流(L444 `if op.op_type in DATASET_OPS:` 之前)插:
```python
        if op.op_type in CARRY_OPS:
            await _apply_carry_op(db, op, payload)
        elif op.op_type in DATASET_OPS:
```
- 新增(文件 carry 段,`_apply_dataset_op` 之后):
```python
async def _apply_carry_op(db: AsyncSession, op: AdaptationOp,
                          payload: dict) -> None:
    """CARRY_OPS 收敛应用到值表(service 缺省 = 全局默认表)。"""
    service = payload.get("service")
    if op.op_type == "renameCarryPath":
        src, dst = payload["from"], payload["to"]
        if service:
            entries = await carry_store.get_bindings(db, service)
        else:
            entries = await carry_store.get_defaults(db)
        if src not in entries:
            raise KeyError(f"carry_path_not_found: {src}")
        if dst in entries:
            raise ValueError(f"carry_path_conflict: {dst} already present")
        entries[dst] = entries.pop(src)
        if service:
            await carry_store.put_bindings(db, service, entries, "adaptation")
        else:
            await carry_store.put_defaults(db, entries, "adaptation")
    elif op.op_type == "addCarryBinding":
        path, value = payload["path"], payload.get("value")
        if service:
            entries = await carry_store.get_bindings(db, service)
            entries[path] = value
            await carry_store.put_bindings(db, service, entries, "adaptation")
        else:
            entries = await carry_store.get_defaults(db)
            entries[path] = value
            await carry_store.put_defaults(db, entries, "adaptation")
    else:  # removeCarryBinding
        path = payload["path"]
        if service:
            entries = await carry_store.get_bindings(db, service)
        else:
            entries = await carry_store.get_defaults(db)
        entries.pop(path, None)  # 收敛:缺行 = 已达终态
        if service:
            await carry_store.put_bindings(db, service, entries, "adaptation")
        else:
            await carry_store.put_defaults(db, entries, "adaptation")


async def open_carry_batch(db: AsyncSession, *, service: str | None,
                           operator_id: int) -> dict:
    """开 carry 值表批(spec §7):漂移面板勾选生成。无版本语义 ——
    endpoint_id 用 `carry:{service|global}` 展示锚,完成不推戳。"""
    batch_id = f"bt-{uuid4().hex[:12]}"
    db.add(AdaptationBatch(
        batch_id=batch_id,
        endpoint_id=f"carry:{service or 'global'}",
        from_version="-", to_version="-",
        status="open", operator_id=operator_id,
    ))
    await _ensure_carry_snapshot(db, batch_id, service)
    await db.commit()
    return await _batch_detail(db, batch_id)


async def _ensure_carry_snapshot(db: AsyncSession, batch_id: str,
                                 service: str | None) -> None:
    entity_type = "carry_binding" if service else "carry_default"
    entity_id = service or "__global__"
    existing = (await db.execute(
        select(AdaptationSnapshot).where(
            AdaptationSnapshot.batch_id == batch_id,
            AdaptationSnapshot.entity_type == entity_type,
            AdaptationSnapshot.entity_id == entity_id,
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return
    rows = (await carry_store.get_bindings(db, service)
            if service else await carry_store.get_defaults(db))
    db.add(AdaptationSnapshot(
        batch_id=batch_id, entity_type=entity_type, entity_id=entity_id,
        before_json={"entries": dict(rows)},
    ))
```
- `create_op`(L778):签名 `scenario_id: str | None`;校验段追加:
```python
    if op_type in CARRY_OPS:
        pass  # 无场景/数据集寻址;快照在开批时已建(整服务粒度)
    elif op_type in DATASET_OPS and not dataset_id:
```
(原 `if op_type in DATASET_OPS and not dataset_id:` 逻辑保持;`_ensure_scenario_snapshot` 调用对 CARRY_OPS 跳过。)
- `_maybe_complete`(L555):`_advance_stamp` 调用包一层条件:
```python
    if not batch.endpoint_id.startswith("carry:"):
        try:
            full = await _plate_full_endpoint(batch.endpoint_id)
        except PlateUnavailableError:
            full = None
        await _advance_stamp(
            db, endpoint_id=batch.endpoint_id,
            to_version=batch.to_version, full=full,
        )
```
- `rollback_batch`:在 dataset 快照恢复循环之后追加:
```python
    for snap in _snap("carry_binding") + _snap("carry_default"):
        try:
            await _rollback_carry(db, snap, applied_ops)
            restored.append(
                {"entityType": snap.entity_type, "entityId": snap.entity_id}
            )
        except _RollbackConflict as e:
            conflicts.append({
                "entityType": snap.entity_type, "entityId": snap.entity_id,
                "note": str(e),
            })
```
- 新增:
```python
async def _rollback_carry(db: AsyncSession, snap: AdaptationSnapshot,
                          applied_ops: list[AdaptationOp]) -> None:
    """值表回滚:期望态 = before + applied carry ops 内存重放,比对后恢复。"""
    before = dict((snap.before_json or {}).get("entries") or {})
    service = snap.entity_id if snap.entity_type == "carry_binding" else None
    expected = dict(before)
    for op in applied_ops:
        if op.op_type not in CARRY_OPS:
            continue
        payload = {**(op.payload or {})}
        if payload.get("service") != service:
            continue
        kind = op.op_type
        if kind == "renameCarryPath":
            if payload["from"] in expected:
                expected[payload["to"]] = expected.pop(payload["from"])
        elif kind == "addCarryBinding":
            expected[payload["path"]] = payload.get("value")
        else:
            expected.pop(payload.get("path"), None)
    current = (await carry_store.get_bindings(db, service)
               if service else await carry_store.get_defaults(db))
    if current != expected:
        raise _RollbackConflict(
            "edited_beyond_batch: current != before+ops replay")
    if service:
        await carry_store.put_bindings(db, service, before, "rollback")
    else:
        await carry_store.put_defaults(db, before, "rollback")
```
- 顶部 import:`from . import carry_store` 与 `from .adaptation_ops import CARRY_OPS`(并入既有 import 块)。

5. `routers/adaptations.py` 追加:

```python
class CarryBatchIn(BaseModel):
    service: str | None = None


@router.post("/carry-batches", response_model=BatchDetail, status_code=201)
async def open_carry_batch(
    user: AdminUser, body: CarryBatchIn, db: DbSession,
) -> BatchDetail:
    """开 carry 值表批(漂移面板入口);ops 经既有 POST /batches/{id}/ops。"""
    detail = await adaptation_service.open_carry_batch(
        db, service=body.service, operator_id=user.id)
    return BatchDetail.model_validate(detail)
```

(`CarryBatchIn` 放 `schemas/adaptations.py` 更合拍 —— 执行时移动过去,router 只 import。)

- [ ] **Step 4: 跑测试确认通过 + 适配域回归**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_adaptation_carry_ops.py tests/test_adaptation_ops.py tests/test_adaptation_batches.py tests/test_adaptations_api.py -v`
Expected: 全 PASS(既有 op 流不破 —— scenario_id 仅放宽)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/backend/app/models/adaptation_op.py src/gimbal-platform/backend/app/schemas/adaptations.py src/gimbal-platform/backend/app/services/adaptation_ops.py src/gimbal-platform/backend/app/services/adaptation_service.py src/gimbal-platform/backend/app/routers/adaptations.py src/gimbal-platform/backend/tests/test_adaptation_carry_ops.py
git commit -m "feat(platform): CARRY_OPS 值表批 — AdaptationOp 场景可空 + carry 批开/用/回滚"
```

---

### Task 13: 前端 — 类型 + deepDefaults 收敛 + reqTypeC 过滤

**Files:**
- Modify: `src/gimbal-platform/frontend/src/types/plate.ts:87-93`(RequestSpecView.carry)
- Modify: `src/gimbal-platform/frontend/src/utils/jsonpath.ts:37-59`(deepDefaults 去 unbound)
- Modify: `src/gimbal-platform/frontend/src/utils/__tests__/jsonpath.test.ts`(删第二 describe)
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue:990-992,1177-1180`

**Interfaces:**
- Consumes: Task 1 的 /full 序列化键 `request.carry`。
- Produces: `RequestSpecView.carry?: Record<string, { description?: string; type?: string }>`;`deepDefaults(bindings)` 单参(Task 15 无关,Task 14 消费 carry 面)。

- [ ] **Step 1: 改测试**

`jsonpath.test.ts`:文件头注释改单来源描述;**删除**整个 `describe('deepDefaults — 契约字段默认值(plate schema 非绑定)')` 块(L27-51);首个 describe 保持不变。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npm test -- src/utils/__tests__/jsonpath.test.ts`
Expected: PASS(测试删除是收敛断言;真正的"红"在实现未删时 typecheck 会抓双参调用 —— 见 Step 3 同步改 Canvas)。若 vitest 对删除后文件全绿,继续 Step 3(行为变化由 Canvas 侧 `npm run typecheck` 把关)。

- [ ] **Step 3: 实现**

`types/plate.ts` `RequestSpecView`(L87-93)追加:

```ts
  /** 传递字段面(spec §2):path → {description, type};值在 platform 值表 */
  carry?: Record<string, { description?: string; type?: string }>
```

`jsonpath.ts`(L37-59)替换为:

```ts
/**
 * 新建步骤初始 body 合成(单来源):IOFieldBinding 的 default(缺省
 * example)按 path 写入。
 * 契约字段(schema 有、binding 无)的 schema default 不再拷贝 —— 该职责
 * 已移交 carry 通道(platform 值表 + materialize 注入,spec §5)。
 */
export function deepDefaults(
  bindings: Array<{ path: string; default: any; example: any }>,
): any {
  const root: any = {}
  for (const f of bindings) {
    const v = f.default !== null && f.default !== undefined ? f.default : f.example
    if (v === null || v === undefined) continue
    setByPath(root, f.path.replace(/^\$\./, ''), v)
  }
  return root
}
```

`CaseComposerCanvas.vue`:
- L1177-1180(初始 body):
```ts
    // 初始 body:只合成绑定 default/example(carry/契约默认移交注入通道)
    const initialBody = deepDefaults(fields)
```
(删除 `const req = full?.request as any` 与 `contracts` 两行 —— `req` 若他处不用则一并删。)
- L989-992(reqTypeC)替换为:
```ts
/** 请求侧 Type C(挂 Request 签页底部;carry 键排除 — 传递面零感知) */
const reqCarryPaths = computed<Set<string>>(() =>
  new Set(Object.keys((currentFull.value?.request as any)?.carry ?? {})))
const reqTypeC = computed<TypeCField[]>(() =>
  typeCFields(currentReqSchema.value, fieldBindings(currentStep.value).map((f) => f.path))
    .filter((f) => !reqCarryPaths.value.has(f.path))
)
```

- [ ] **Step 4: 跑测试 + typecheck**

Run: `cd src/gimbal-platform/frontend && npm test -- src/utils/__tests__/jsonpath.test.ts && npm run typecheck`
Expected: 测试 PASS;typecheck 无错(双参调用已清)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/types/plate.ts src/gimbal-platform/frontend/src/utils/jsonpath.ts src/gimbal-platform/frontend/src/utils/__tests__/jsonpath.test.ts src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue
git commit -m "feat(ui): 编排期 carry 零感知 — deepDefaults 收敛单来源 + Type C 差集滤 carry 键"
```

---

### Task 14: 前端 — step 卡只读注入提示 + api/carry.ts

**Files:**
- Create: `src/gimbal-platform/frontend/src/api/carry.ts`
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`(step-meta 徽标 + tooltip)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/` 若有 Canvas 相关测试目录则加;否则以 typecheck + 手动 dev 验证(见 Step 4)

**Interfaces:**
- Consumes: Task 6 API;Task 13 `RequestSpecView.carry`;Canvas 既有 `endpointFullByEndpoint` 缓存与 service-alias `deriveBase`。
- Produces(Task 15/16 依赖):`api/carry.ts` 全套 client(`getDefaults/putDefaults/getBindings/putBindings/getServiceFields/getDrift`);step 卡 `carryCountHint(step)`。

- [ ] **Step 1: 实现 api client(纯声明,先行)**

`src/gimbal-platform/frontend/src/api/carry.ts`:

```ts
/**
 * api/carry.ts —— carry 值层 client(spec §3.2)。
 * dict 的 null 值 = 显式 null 行;键缺席 = 未配置(§3.1)。
 */
import http from '@/api/http'

export type CarryValues = Record<string, string | null>

export async function getDefaults(): Promise<CarryValues> {
  return (await http.get('/api/carry/defaults')).defaults
}

export async function putDefaults(defaults: CarryValues): Promise<CarryValues> {
  return (await http.put('/api/carry/defaults', { defaults })).defaults
}

export async function getBindings(): Promise<Record<string, CarryValues>> {
  return (await http.get('/api/carry/bindings')).bindings
}

export async function getBindingsFor(service: string): Promise<CarryValues> {
  return (await http.get(`/api/carry/bindings/${encodeURIComponent(service)}`)).bindings
}

export async function putBindings(
  service: string, bindings: CarryValues,
): Promise<CarryValues> {
  return (await http.put(
    `/api/carry/bindings/${encodeURIComponent(service)}`, { bindings })).bindings
}

export interface CarryFieldFace { path: string; type: string; description: string }

export async function getServiceFields(service: string): Promise<CarryFieldFace[]> {
  return (await http.get(
    `/api/carry/bindings/${encodeURIComponent(service)}/fields`)).fields
}

export interface ServiceDrift {
  service: string
  orphaned: string[]
  uncovered: string[]
  renamedSuggestions: Array<{ from: string; to: string }>
}

export async function getDrift(): Promise<ServiceDrift[]> {
  return (await http.get('/api/carry/drift')).services
}
```

(http 返回形状按 `api/http.ts` 归一约定执行时对齐 —— `grep -n "export default" src/api/http.ts` 看是否自动解 `.data`。)

- [ ] **Step 2: Canvas 提示实现**

`CaseComposerCanvas.vue` script 区(onMounted 附近)加:

```ts
// ── carry 只读提示(spec §5):字段面 ∩ 值表非空集 → "将注入 N 个" ──
const carryValues = ref<{ defaults: CarryValues; bindings: Record<string, CarryValues> } | null>(null)
onMounted(async () => {
  try {
    const [defaults, bindings] = await Promise.all([getDefaults(), getBindings()])
    carryValues.value = { defaults, bindings }
  } catch { /* 降级:无提示,不阻塞编排 */ }
})

/** step → 可注入的 carry 键清单(path → 来源标签) */
function carryInjectable(step: StepView): Map<string, string> {
  if (!carryValues.value) return new Map()
  const hints = (step.api as any)?.view_hints
  const full = hints?.endpoint_id ? endpointFullByEndpoint.value[hints.endpoint_id] : undefined
  const face = Object.keys((full?.request as any)?.carry ?? {})
  if (!face.length) return new Map()
  const base = deriveBase(step.api.service, catalogServiceNames.value)
  const bound = base ? carryValues.value.bindings[base] ?? {} : {}
  const out = new Map<string, string>()
  for (const p of face) {
    if (p in bound) out.set(p, '服务绑定')
    else if (p in carryValues.value.defaults) out.set(p, '全局默认')
  }
  return out
}
```

(`catalogServiceNames`/`endpointFullByEndpoint`/`deriveBase` 均为 Canvas 既有或邻接既有 —— 执行时按实际变量名对齐:`grep -n "deriveBase\|catalogNames\|endpointFullByEndpoint" CaseComposerCanvas.vue`。)

模板 `.step-meta`(L52-56 区域)追加:

```html
          <el-tooltip
            v-if="carryInjectable(step).size"
            placement="top"
          >
            <template #content>
              <div v-for="[p, src] of carryInjectable(step)" :key="p">
                {{ p }} ← {{ src }}
              </div>
            </template>
            <span class="carry-badge">carry {{ carryInjectable(step).size }}</span>
          </el-tooltip>
```

样式区加 `.carry-badge`(与 `method-badge` 同款小徽标,灰底)。

- [ ] **Step 3: typecheck + 单测面**

Run: `cd src/gimbal-platform/frontend && npm run typecheck && npm test`
Expected: typecheck 无错;既有 vitest 全绿

- [ ] **Step 4: 手动冒烟(dev server)**

`npm run dev` → 打开编排器 → 选一个 carry 面 endpoint(Task 4 后 fin.settlement.create_order 有 $.remark)→ step 卡出现灰徽标;悬停列来源。值表为空时无徽标(面 ∩ 值表 = ∅)。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/api/carry.ts src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue
git commit -m "feat(ui): step 卡 carry 只读提示 — 面∩值表计数 + 来源悬停"
```

---

### Task 15: 前端 — 传递字段配置页

**Files:**
- Create: `src/gimbal-platform/frontend/src/views/CarryConfig.vue`
- Modify: `src/gimbal-platform/frontend/src/router/index.ts`(路由)
- Modify: `src/gimbal-platform/frontend/src/components/TopNav.vue`(入口,admin)

**Interfaces:**
- Consumes: Task 14 `api/carry.ts` 全套。
- Produces: `/carry-config` 页(服务绑定 tab + 全局默认 tab)。

- [ ] **Step 1: 路由与入口**

`router/index.ts`(/adaptations 之前任意位置):

```ts
  {
    path: '/carry-config',
    component: () => import('@/views/CarryConfig.vue'),
    meta: { requiresAuth: true },
  },
```

`TopNav.vue` nav 数组(admin 项区域,参考 `/admin/users` 的 admin 判定写法):

```ts
    { path: '/carry-config', label: '传递字段', icon: Postcard, adminOnly: true },
```

(icon 从 `@element-plus/icons-vue` 选一个未占用的,如 `Postcard`/`Stamp`;`adminOnly` 的过滤逻辑按 TopNav 既有写法 —— 若无此机制则把该项放进既有的 admin 条件分支。)

- [ ] **Step 2: 页面实现**

`views/CarryConfig.vue`(骨架对齐 Auths.vue 的页壳 + CaseComposerConfig 的 c-card 分区):

```vue
<script setup lang="ts">
/**
 * CarryConfig —— 传递字段配置(spec §6)。
 * 服务绑定 tab:选服务 → 拉该服务 carry 字段面并集 → 逐字段填值;
 *   placeholder = 全局默认值(无行时);空输入=删行(不注入);
 *   「设 null」= 显式注入 JSON null(§3.1)。
 * 全局默认 tab:整表编辑;常驻提示纯 path 跨服务生效(§6)。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getDefaults, putDefaults, getBindings, putBindings, getServiceFields,
  type CarryFieldFace, type CarryValues,
} from '@/api/carry'

const activeTab = ref('service')

// ── 服务绑定 ──
const service = ref('')
const face = ref<CarryFieldFace[]>([])
const rows = ref<Array<{ path: string; type: string; description: string; value: string | null | undefined }>>([])
const defaultsMap = ref<CarryValues>({})
const knownServices = ref<string[]>([])

async function loadAll() {
  defaultsMap.value = await getDefaults()
  const bindings = await getBindings()
  knownServices.value = Object.keys(bindings)
}

async function onServiceChange() {
  if (!service.value) return
  face.value = await getServiceFields(service.value)
  const bound = await getBindings().then((m) => m[service.value] ?? {})
  rows.value = face.value.map((f) => ({
    ...f,
    // undefined = 无行(placeholder 显全局默认);null = 显式 null 行
    value: f.path in bound ? bound[f.path] : undefined,
  }))
}

function saveService() {
  const entries: CarryValues = {}
  for (const r of rows.value) {
    if (r.value === undefined) continue   // 无行 → 不配置
    entries[r.path] = r.value             // null → 显式 null;'' → 空串值
  }
  putBindings(service.value, entries).then(() => ElMessage.success('已保存'))
}

// ── 全局默认 ──
const defaultRows = ref<Array<{ path: string; value: string | null }>>([])

async function loadDefaults() {
  const d = await getDefaults()
  defaultRows.value = Object.entries(d).map(([path, value]) => ({ path, value }))
}

function saveDefaults() {
  const entries: CarryValues = {}
  for (const r of defaultRows.value) {
    if (!r.path) continue
    entries[r.path] = r.value
  }
  putDefaults(entries).then(() => ElMessage.success('已保存'))
}

function addDefaultRow() { defaultRows.value.push({ path: '', value: '' }) }

loadAll(); loadDefaults()
</script>

<template>
  <div class="page">
    <h2>传递字段配置</h2>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="服务绑定" name="service">
        <el-select
          v-model="service" filterable allow-create
          placeholder="选择或输入目录服务名"
          @change="onServiceChange"
        >
          <el-option v-for="s in knownServices" :key="s" :label="s" :value="s" />
        </el-select>
        <el-table v-if="rows.length" :data="rows">
          <el-table-column prop="path" label="字段路径" width="240" />
          <el-table-column prop="type" label="类型" width="100" />
          <el-table-column prop="description" label="说明" />
          <el-table-column label="值">
            <template #default="{ row }">
              <el-input
                v-model="row.value"
                :placeholder="row.value === undefined
                  ? (defaultsMap[row.path] ?? '未配置(不注入)')
                  : '显式 null'"
              />
            </template>
          </el-table-column>
          <el-table-column label="" width="120">
            <template #default="{ row }">
              <el-button link @click="row.value = row.value === null ? '' : null">
                {{ row.value === null ? '取消 null' : '设 null' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-button type="primary" :disabled="!service" @click="saveService">保存</el-button>
      </el-tab-pane>
      <el-tab-pane label="全局默认" name="defaults">
        <el-alert type="info" :closable="false" show-icon
          title="全局默认按纯 path 跨服务生效 —— 契约门控只保证不注入未声明字段;"
          description="$.type 类语义敏感路径请用服务绑定覆盖兜底(配置纪律,spec §6)。" />
        <el-table :data="defaultRows">
          <el-table-column label="字段路径" width="280">
            <template #default="{ row }"><el-input v-model="row.path" /></template>
          </el-table-column>
          <el-table-column label="值">
            <template #default="{ row }"><el-input v-model="row.value" /></template>
          </el-table-column>
          <el-table-column label="" width="80">
            <template #default="{ $index }">
              <el-button link type="danger"
                @click="defaultRows.splice($index, 1)">删</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-button @click="addDefaultRow">加一行</el-button>
        <el-button type="primary" @click="saveDefaults">保存</el-button>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
```

(页壳 class 与 c-card 风格执行时对齐 Auths.vue/CaseComposerConfig.vue 的既有样式约定;`el-input v-model` 对 `null` 值的处理 —— el-input 会把 null 变 '',所以「设 null」状态建议用独立 boolean 列 `isNull` 承载,保存时 `row.isNull ? null : row.value`。执行时按此修正,交互不变。)

- [ ] **Step 3: typecheck + 手动冒烟**

Run: `cd src/gimbal-platform/frontend && npm run typecheck && npm run dev`
手动:admin 登录 → 传递字段 → 服务绑定选 fin-service → 见 $.remark 行 → 填值保存 → 回编排器看 step 卡徽标变化;member 不见入口(直接访问 GET 可读、PUT 403)。

- [ ] **Step 4: Commit**

```bash
git add src/gimbal-platform/frontend/src/views/CarryConfig.vue src/gimbal-platform/frontend/src/router/index.ts src/gimbal-platform/frontend/src/components/TopNav.vue
git commit -m "feat(ui): 传递字段配置页 — 服务绑定 + 全局默认双签页"
```

---

### Task 16: 前端 — 适配中心 carry 面板

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/AdaptationCenter.vue`(carry 漂移 section)
- Modify: `src/gimbal-platform/frontend/src/components/adaptations/OpConstructDialog.vue`(3 个 carry op 类型)
- Modify: `src/gimbal-platform/frontend/src/api/adaptations.ts`(openCarryBatch)
- Modify: `src/gimbal-platform/frontend/src/api/adaptations.ts` 或 `api/carry.ts`(getDrift 已在 carry.ts)
- Test: `src/gimbal-platform/frontend/src/components/adaptations/__tests__/`(若 ImpactDrawer 等有既有测试模式则加一个面板数据组装用例;否则 typecheck 把关)

**Interfaces:**
- Consumes: Task 11 `getDrift`(api/carry.ts);Task 12 `POST /adaptations/carry-batches` + 既有 `createOp`;Task 14 api/carry.ts。
- Produces: 适配中心 carry 职能闭环(spec §7):漂移发现 → 勾选 → 生成批 → 应用。

- [ ] **Step 1: api 扩展**

`api/adaptations.ts` 追加:

```ts
/** 开 carry 值表批(service=null → 全局默认表面) */
export async function openCarryBatch(
  service: string | null,
): Promise<BatchDetail> {
  return http.post('/api/adaptations/carry-batches', { service })
}
```

`OpOut.scenarioId` 类型改 `string | null`。

- [ ] **Step 2: AdaptationCenter carry section**

`AdaptationCenter.vue` 批次表之后追加(数据面结构参考既有待适配卡片):

```vue
    <section class="c-card">
      <header>
        <h3>carry 漂移(值表 vs plate 面)</h3>
        <el-button @click="loadCarryDrift">刷新</el-button>
        <el-button
          type="primary" :disabled="!carryChecked.length"
          @click="openCarryBatchFromDrift"
        >勾选生成批({{ carryChecked.length }})</el-button>
      </header>
      <div v-for="s in carryDrift" :key="s.service" class="drift-svc">
        <h4>{{ s.service }}</h4>
        <el-checkbox-group v-model="carryChecked">
          <el-checkbox
            v-for="o in s.orphaned" :key="`o:${o}`"
            :label="JSON.stringify({ service: s.service, opType: 'removeCarryBinding', payload: { service: s.service, path: o } })"
          >孤儿绑定 {{ o }} → 移除</el-checkbox>
          <el-checkbox
            v-for="u in s.uncovered" :key="`u:${u}`"
            :label="JSON.stringify({ service: s.service, opType: 'addCarryBinding', payload: { service: s.service, path: u, value: '' } })"
          >未绑定面字段 {{ u }} → 补绑定</el-checkbox>
          <el-checkbox
            v-for="r in s.renamedSuggestions" :key="`r:${r.from}`"
            :label="JSON.stringify({ service: s.service, opType: 'renameCarryPath', payload: { service: s.service, from: r.from, to: r.to } })"
          >改名建议 {{ r.from }} → {{ r.to }}</el-checkbox>
        </el-checkbox-group>
      </div>
    </section>
```

script 区:

```ts
import { getDrift, type ServiceDrift } from '@/api/carry'
import { openCarryBatch, createOp } from '@/api/adaptations'

const carryDrift = ref<ServiceDrift[]>([])
const carryChecked = ref<string[]>([])

async function loadCarryDrift() {
  carryDrift.value = await getDrift()
  carryChecked.value = []
}

async function openCarryBatchFromDrift() {
  const services = new Set(carryChecked.value.map((c) => JSON.parse(c).service))
  for (const svc of services) {
    const detail = await openCarryBatch(svc)
    for (const raw of carryChecked.value) {
      const item = JSON.parse(raw)
      if (item.service !== svc) continue
      await createOp(detail.batchId, {
        opType: item.opType, payload: item.payload,
      } as any)
    }
    router.push(`/adaptations/batches/${detail.batchId}`)
  }
}
```

(`createOp` 既有签名执行时对齐(`grep -n "export async function createOp" api/adaptations.ts`)—— scenarioId 可空后请求体不带该键。)

- [ ] **Step 3: OpConstructDialog 扩展**

op 类型清单追加三项(payload 字段:`service?/from/to`、`service?/path/value`、`service?/path`),表单段落抄既有 renameField 的 from/to 输入对模式。

- [ ] **Step 4: typecheck + 全量前端回归**

Run: `cd src/gimbal-platform/frontend && npm run typecheck && npm test`
Expected: 全绿

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/views/AdaptationCenter.vue src/gimbal-platform/frontend/src/components/adaptations/OpConstructDialog.vue src/gimbal-platform/frontend/src/api/adaptations.ts
git commit -m "feat(ui): 适配中心 carry 面板 — 漂移三类勾选生成值表批"
```

---

## 自审记录(Self-Review)

**Spec 覆盖核对**(spec 章节 → Task):

| spec 章节 | Task |
|---|---|
| §2.1 CarryEntry/carry/校验/序列化 | 1 |
| §2.1.1 model 机制移除(含术语唯一化) | 2、3、4 |
| §2.2 三分类(未声明黄警 = 既有 Type C 展示保留) | 13(差集滤 carry 后仅剩未声明) |
| §3.1 两表 + null 语义 | 5 |
| §3.2 API 面(含 /fields、/drift) | 6、11 |
| §4.1 CarryContext + 纯函数 + 批量预解析 | 8、9 |
| §4.2 填充规则/类型转换/模板透传/降级 | 8(规则)、7+9(derive_base/黄警) |
| §4.3 导出同源 + 快照语义 | 10 |
| §5 编排无感 + deepDefaults 收敛 + 只读提示 | 13、14 |
| §6 配置页(含跨服务提示/placeholder) | 15 |
| §7 适配中心(漂移/CARRY_OPS/影响面=倒排既有) | 11、12、16 |
| §9 兼容(carry_context=None 等价/存量 body 不覆盖) | 8 测试钉死 |
| §10 测试策略 | 各 Task 内嵌 |
| §11 验收清单 | 逐项落于上述 Task |

**二期预留注**:订单组绑定层(Task 8 CarryContext docstring 已留链位注释)、env profile(表结构不加列即预留)按 spec §8 不实现。

**已实证符号**(计划编写时 grep 验证存在,执行者可直接引用):`_path.is_valid_path/normalize`(io_spec.py L8 已 import 为 `_path`)、`adaptation_service._plate_list_endpoints`(L40)、`_RollbackConflict`(L578)/`rollback_batch._snap(kind)` 闭包(L607)、tests helpers `register_and_login`/`make_draft`/`wait_until`(helpers.py L15/32/75)、`_run_payload`/`_patch_launch_capture`(test_run_m1_capabilities.py L33/42)、`_member`(test_scenario_visibility_and_copy.py L22)。

**已知执行期校准点**(非占位符,是按现场代码对齐签名的机械动作,均已给出 grep 目标):`db_factory()` 会话开法、TopNav admin 过滤机制、el-input null 态交互(建议 `isNull` 布尔列承载)、helpers 的确切参数默认值。
