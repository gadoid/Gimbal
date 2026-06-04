"""Unit tests for gimbal.core.asset_materializer (引用物化器).

覆盖场景：
  [1] 通用内联 Ref — body dict 中的 {"kind": "ref", "ref": "..."} 替换为拉来的内容
  [2] 顶层类型化 Ref — StepRef / ApiRef / RequestRef / StrategyRef 整对象替换
  [3] 嵌套深度 — step 里嵌 ApiRef，ApiRef 拉来的内容里又含 Ref（传递闭包）
  [4] 显式循环 — A → B → A，触发 AssetCycleError
  [5] 深度兜底 — 超过 max_depth 触发 AssetCycleError
  [6] 标量 + 容器穿透 — dict/list 嵌套、标量原样返回
  [7] 拉取失败 — ref 不存在 / 反序列化失败
  [8] 兄弟分支互不污染 — A 含两个 ref，都成功且都"恢复 seen"（不会假阳性 cycle）
  [9] ScenarioRef / SuiteRef 适配 — 顶层 scenario/suite 引用，discriminator 选 Scenario/Suite
"""
import sys
import os
import json
import shutil
import tempfile
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# logging 最低配置
import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("ASSET MATERIALIZER TEST")
print("=" * 60)

TMP = tempfile.mkdtemp(prefix="gimbal_materializer_test_")
print(f"\nUsing temp dir: {TMP}")


def cleanup():
    if os.path.isdir(TMP):
        shutil.rmtree(TMP, ignore_errors=True)


# ════════════════════════════════════════════════════════════════════
# 0. 工具：构造一个 LocalFsContentStore，预填若干 ref
# ════════════════════════════════════════════════════════════════════
from gimbal.repository import AssetStore, LocalFsContentStore, AssetRef
from gimbal.schema.api import Api
from gimbal.schema.request import Request
from gimbal.schema.scenario import Scenario, Suite, ScenarioRef, SuiteRef
from gimbal.schema.step import Step
from gimbal.schema.strategy import Extract
from gimbal.schema.ref import Ref
from gimbal.exceptions import AssetCycleError, AssetMaterializationError

BACKEND = LocalFsContentStore(root=os.path.join(TMP, "store"))
STORE = AssetStore(backend=BACKEND)


def push(ref_str: str, payload) -> None:
    """payload 可以是 dict（→ JSON 编码）或 bytes。"""
    ref = AssetRef.parse(ref_str)
    if isinstance(payload, (dict, list)):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    elif isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        data = payload
    STORE.push(ref, data, kind="data", overwrite=True)


# 预先 push 各种"将被 ref 拉取"的内容
push("common/auth:v1", {"token": "eyJ-secret-token", "ttl": 3600})
push("smoke/order-id-pool:latest", "POOL-98765")
push("smoke/cart-line-template:v1", {"sku": "B2", "qty": 2, "price": 9.99})
push("smoke/step-add-cart:v1", {
    "kind": "step",
    "api": {
        "kind": "api",
        "service": "cart",
        "method": "POST",
        "path": "/api/cart/items",
        "headers": {"X-Env": "test"},
    },
    "request": {
        "kind": "request",
        "body": {
            "client_id": "c-001",
            "line": {"kind": "ref", "ref": "smoke/cart-line-template:v1"},
        },
    },
    "strategy": [
        {
            "kind": "extract",
            "name": "extract_cart_id",
            "expression": "$.body.cart_id",
            "target": "cart_id",
        }
    ],
})
# 给策略 ref 提供一个完整的策略对象
push("smoke/strategy-extract-cart-id:v1", {
    "kind": "extract",
    "name": "extract_cart_id",
    "expression": "$.body.cart_id",
    "target": "cart_id",
    "scope": "scenario",
})
# 循环测试数据：a 和 b 都用通用内联 Ref（kind=ref）作为内容，
# 物化器在反序列化后会再次看到 Ref 节点 → 走递归 → 命中 seen。
push("smoke/cycle-a:v1", {"kind": "ref", "ref": "smoke/cycle-b:v1"})
push("smoke/cycle-b:v1", {"kind": "ref", "ref": "smoke/cycle-a:v1"})

# Scenario / Suite 完整数据（[9] 测试用）—— 最小合法 schema
_SCENARIO_META = {
    "name": "sc-test-001", "description": "d", "module": "m", "priority": 1,
    "author": "a", "owner": "o", "tags": ["t"], "version": "1.0",
    "createTime": "2026-01-01T00:00:00", "expire": False, "requirementRef": [],
}
push("smoke/full-scenario:v1", {
    "kind": "scenario",
    "scenarioId": "sc-test-001",
    "meta": _SCENARIO_META,
    "config": {"services": {"user-svc": "http://localhost:8080"}, "users": {}},
    "resource": {},
    "steps": [],
})
push("smoke/full-suite:v1", {
    "kind": "suite",
    "suite": [
        {
            "kind": "scenario",
            "scenarioId": "sc-embedded-001",
            "meta": _SCENARIO_META,
            "config": {},
            "resource": {},
            "steps": [],
        }
    ],
})

print("\n  preloaded: common/auth, smoke/order-id-pool, smoke/cart-line-template, "
      "smoke/step-add-cart, smoke/strategy-extract-cart-id, smoke/cycle-a/b, "
      "smoke/full-scenario, smoke/full-suite")


# ════════════════════════════════════════════════════════════════════
# [1] 通用内联 Ref
# ════════════════════════════════════════════════════════════════════
print("\n[1] 通用内联 Ref（出现在 body dict）")
from gimbal.core.asset_materializer import AssetMaterializer

obj = {
    "order_id": {"kind": "ref", "ref": "smoke/order-id-pool:latest"},
    "auth": {"kind": "ref", "ref": "common/auth:v1"},
    "items": [
        {"sku": "A1"},
        {"kind": "ref", "ref": "smoke/cart-line-template:v1"},
    ],
}
materializer = AssetMaterializer(STORE, max_depth=8)
result = materializer.materialize(obj)

assert result["order_id"] == "POOL-98765",          f"order_id got {result['order_id']!r}"
assert result["auth"] == {"token": "eyJ-secret-token", "ttl": 3600}, f"auth got {result['auth']!r}"
assert result["items"][0] == {"sku": "A1"},         f"items[0] got {result['items'][0]!r}"
assert result["items"][1] == {"sku": "B2", "qty": 2, "price": 9.99}, f"items[1] got {result['items'][1]!r}"
# ref 节点本身已经消失
assert not any(isinstance(v, Ref) for v in result.values())
assert not any(isinstance(v, Ref) for v in result["items"])
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# [2] 顶层类型化 Ref
# ════════════════════════════════════════════════════════════════════
print("\n[2] 顶层类型化 Ref（StepRef / ApiRef / RequestRef / StrategyRef）")
from gimbal.schema.step import StepRef
from gimbal.schema.api import ApiRef
from gimbal.schema.request import RequestRef
from gimbal.schema.strategy import StrategyRef

# StepRef —— 应被替换为 Step
step_obj = StepRef(ref="smoke/step-add-cart:v1")
result = AssetMaterializer(STORE).materialize(step_obj)
assert isinstance(result, Step),                       f"expected Step, got {type(result).__name__}"
assert result.api.service == "cart",                   f"api.service got {result.api.service!r}"
assert result.api.method == "POST",                    f"api.method got {result.api.method!r}"
assert isinstance(result.request, Request),            f"request got {type(result.request).__name__}"
print(f"  StepRef → Step: api={result.api.method} {result.api.path}")

# ApiRef
api_obj = {"kind": "api_ref", "ref": "smoke/step-add-cart:v1"}
result = AssetMaterializer(STORE).materialize(api_obj)
# 注意：ApiRef 拉 smoke/step-add-cart 时会拉整个 step，但我们让 ref_kind_to_class 选 Api
# 实际：拉来的 parsed 是 step dict，里面有 kind=step；model_validate(Api, ...) 会失败
# 所以这种"ref 类型与内容不匹配"应该由用户负责写对。
# 这里改成测：让 ref 内容本身就是 Api
push("smoke/just-api:v1", {
    "kind": "api",
    "service": "user",
    "method": "GET",
    "path": "/api/users/123",
    "headers": {"X-Token": "fixed"},
})
api_obj2 = ApiRef(ref="smoke/just-api:v1")
result = AssetMaterializer(STORE).materialize(api_obj2)
assert isinstance(result, Api), f"expected Api, got {type(result).__name__}"
print(f"  ApiRef → Api: service={result.service} {result.method} {result.path}")

# RequestRef
push("smoke/just-request:v1", {
    "kind": "request",
    "body": {"hello": "world"},
})
req_obj = RequestRef(ref="smoke/just-request:v1")
result = AssetMaterializer(STORE).materialize(req_obj)
assert isinstance(result, Request), f"expected Request, got {type(result).__name__}"
assert result.body == {"hello": "world"}, f"body got {result.body!r}"
print(f"  RequestRef → Request: body={result.body}")

# StrategyRef
strat_obj = StrategyRef(ref="smoke/strategy-extract-cart-id:v1")
result = AssetMaterializer(STORE).materialize(strat_obj)
# StrategyRef → StrategyBase（具体子类由 Pydantic 按 kind 选）
assert hasattr(result, "expression"), f"expected strategy, got {type(result).__name__}"
assert isinstance(result, Extract), f"expected Extract, got {type(result).__name__}"
assert result.target == "cart_id"
print(f"  StrategyRef → Extract: target={result.target}")
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# [3] 嵌套深度（传递闭包）
# ════════════════════════════════════════════════════════════════════
print("\n[3] 嵌套深度：StepRef 拉来的 step 内部仍含 Ref")
# 构造一个 step 顶层 dict 整体作为 Ref
# step-add-cart 的 body 里已经含了一个 inline Ref → smoke/cart-line-template:v1
# 物化 StepRef(smoke/step-add-cart) → 应递归物化 body 里的内联 Ref
step_obj = StepRef(ref="smoke/step-add-cart:v1")
result = AssetMaterializer(STORE).materialize(step_obj)
assert isinstance(result, Step)
# body 里的内联 Ref 应该被替换
line = result.request.body["line"]
assert not isinstance(line, Ref), f"inline Ref not materialized: {line!r}"
assert line == {"sku": "B2", "qty": 2, "price": 9.99}, f"got {line!r}"
print(f"  StepRef body 内联 Ref 也被替换: line={line}")
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# [4] 显式循环检测
# ════════════════════════════════════════════════════════════════════
print("\n[4] 显式循环检测")
# smoke/cycle-a → {"kind": "ref", "ref": "smoke/cycle-b:v1"} (通用内联 Ref)
# smoke/cycle-b → {"kind": "ref", "ref": "smoke/cycle-a:v1"} (通用内联 Ref)
# a → b → a → b → ... 应该被 seen 检测到
obj = {"kind": "ref", "ref": "smoke/cycle-a:v1"}
try:
    AssetMaterializer(STORE, max_depth=16).materialize(obj)
except AssetCycleError as e:
    print(f"  AssetCycleError (expected): {e}")
else:
    raise AssertionError("expected AssetCycleError")
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# [5] 深度兜底
# ════════════════════════════════════════════════════════════════════
print("\n[5] 深度兜底（max_depth=3 应在第 4 层报错）")
# 链式资产: x1 → x2 → x3 → x4 → ...
for i in range(1, 6):
    nxt = f"smoke/chain-{i+1}:v1" if i < 5 else "smoke/chain-end:v1"
    push(f"smoke/chain-{i}:v1", {"kind": "ref", "ref": nxt})
push("smoke/chain-end:v1", {"final": True})

obj = {"kind": "ref", "ref": "smoke/chain-1:v1"}
try:
    AssetMaterializer(STORE, max_depth=3).materialize(obj)
except AssetCycleError as e:
    print(f"  AssetCycleError (expected, max_depth=3): {e}")
else:
    raise AssertionError("expected AssetCycleError on depth overflow")
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# [6] 标量 + 容器穿透
# ════════════════════════════════════════════════════════════════════
print("\n[6] 标量 + 容器穿透")
obj = {
    "str": "hello",
    "int": 42,
    "float": 3.14,
    "bool": True,
    "none": None,
    "list": [1, 2, "three", None, {"kind": "ref", "ref": "smoke/order-id-pool:latest"}],
    "nested": {
        "deep": {
            "value": {"kind": "ref", "ref": "smoke/order-id-pool:latest"},
        },
    },
}
result = AssetMaterializer(STORE).materialize(obj)
assert result["str"] == "hello"
assert result["int"] == 42
assert result["float"] == 3.14
assert result["bool"] is True
assert result["none"] is None
assert result["list"][:4] == [1, 2, "three", None]
assert result["list"][4] == "POOL-98765"
assert result["nested"]["deep"]["value"] == "POOL-98765"
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# [7] 拉取失败
# ════════════════════════════════════════════════════════════════════
print("\n[7] 拉取失败 / 非法 ref")
# 不存在的 ref
try:
    AssetMaterializer(STORE).materialize({"kind": "ref", "ref": "does/not-exist:v1"})
except AssetMaterializationError as e:
    print(f"  AssetMaterializationError (missing ref, expected): {e}")
else:
    raise AssertionError("expected AssetMaterializationError")

# 非法 ref 格式
try:
    AssetMaterializer(STORE).materialize({"kind": "ref", "ref": "INVALID UPPER"})
except AssetMaterializationError as e:
    print(f"  AssetMaterializationError (invalid ref, expected): {e}")
else:
    raise AssertionError("expected AssetMaterializationError")

# 类型化 Ref 但内容不匹配（smoke/step-add-cart 是 step dict，但当成 Api 拉）
push("smoke/not-an-api:v1", {"kind": "step", "ref": "smoke/just-api:v1"})
try:
    AssetMaterializer(STORE).materialize(ApiRef(ref="smoke/not-an-api:v1"))
except AssetMaterializationError as e:
    print(f"  AssetMaterializationError (deserialization, expected): {e}")
else:
    raise AssertionError("expected AssetMaterializationError")
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# [8] 兄弟分支互不污染 seen
# ════════════════════════════════════════════════════════════════════
print("\n[8] 兄弟分支互不污染 seen")
# 一个对象含两个引用同一资产的不同位置：
obj = {
    "a": {"kind": "ref", "ref": "smoke/order-id-pool:latest"},
    "b": {"kind": "ref", "ref": "smoke/order-id-pool:latest"},
    "c": {"kind": "ref", "ref": "smoke/cart-line-template:v1"},
}
result = AssetMaterializer(STORE).materialize(obj)
assert result["a"] == "POOL-98765"
assert result["b"] == "POOL-98765"   # 第二次拉到同一 ref 不应被误判 cycle
assert result["c"] == {"sku": "B2", "qty": 2, "price": 9.99}
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# [9] ScenarioRef / SuiteRef 适配 — 顶层 scenario/suite 引用，
#      RunUnion discriminator 选 Scenario / Suite
# ════════════════════════════════════════════════════════════════════
print("\n[9] ScenarioRef / SuiteRef 适配")

# 9a. ScenarioRef → Scenario
sr = ScenarioRef(ref="smoke/full-scenario:v1")
result = AssetMaterializer(STORE, max_depth=8).materialize(sr)
assert isinstance(result, Scenario), f"expected Scenario, got {type(result).__name__}"
assert result.scenarioId == "sc-test-001"
assert result.kind == "scenario"
print(f"  ScenarioRef → Scenario: scenarioId={result.scenarioId}")

# 9b. SuiteRef → Suite
stref = SuiteRef(ref="smoke/full-suite:v1")
result2 = AssetMaterializer(STORE, max_depth=8).materialize(stref)
assert isinstance(result2, Suite), f"expected Suite, got {type(result2).__name__}"
assert result2.kind == "suite"
assert len(result2.suite) == 1
assert isinstance(result2.suite[0], Scenario)
assert result2.suite[0].scenarioId == "sc-embedded-001"
print(f"  SuiteRef → Suite:  inner scenarios={[s.scenarioId for s in result2.suite]}")

# 9c. 校验：ref 类型与内容不匹配 → 应抛 AssetMaterializationError
push("smoke/not-a-scenario:v1", {"kind": "step", "api": {}, "request": {}, "strategy": []})
sr2 = ScenarioRef(ref="smoke/not-a-scenario:v1")
try:
    AssetMaterializer(STORE, max_depth=8).materialize(sr2)
except AssetMaterializationError as e:
    msg = str(e)
    assert "scenario" in msg.lower() or "union" in msg.lower() or "kind" in msg.lower(), msg
    print(f"  mismatch kind   → AssetMaterializationError (expected)")
else:
    raise AssertionError("expected AssetMaterializationError on kind mismatch")
print("  PASS")


# ════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("ALL ASSET MATERIALIZER TESTS PASSED")
print("=" * 60)
cleanup()
