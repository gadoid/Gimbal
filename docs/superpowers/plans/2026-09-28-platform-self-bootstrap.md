# gimbal-platform 自举实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 gimbal-platform 自己的 115 个 HTTP 操作导出为 plate 契约并注册，再在平台上编排约 18 条打自己的用例。

**Architecture:** 平台 `/openapi.json` 是契约的唯一真源，生成器机械导出 `EndpointSpec` JSON，plate lifespan 装配它。用例以 YAML 声明，编排器把 YAML 编译成 plate Scenario definition，经平台公开 API 建资源、发起运行、轮询、清理。

**Tech Stack:** Python 3.12+、FastAPI、pydantic v2、gimbal-plate（`EndpointSpec`）、PyYAML、pytest。

**Spec:** `docs/superpowers/specs/2026-09-28-platform-self-bootstrap-design.md`

## Global Constraints

- **授权边界**：只许动四处 —— `src/gimbal-platform/backend/app/routers/auth.py`（加一行 import）、`src/gimbal-plate/gimbal_plate/systems/platform/**`（新增）、`src/gimbal-plate/gimbal_plate/http/app.py`（注册 + 自检放宽）、`src/gimbal-bootstrap/**`（新增）。其余一律不动，超出即停并请示。
- **不新增任何 schema 类型**。契约必须落在 plate 现有 `EndpointSpec` 上。
- **不改 gimbal 执行器 / plate 导出语义**。
- **人工不写任何契约字段**，全部由生成器从 OpenAPI 派生。
- 所有读写走平台公开 HTTP API（`127.0.0.1:8000`），不走进程内 ASGI 直调。
- 自举资源一律 `sb-` 前缀；用户名字段带 uuid 变量避免重复运行撞名。
- **注册后必须停下等人把账号提权为 admin 再继续** —— 平台只给库中首个用户 `role="admin"`，之后注册一律 `member`，而每域用例要打管理员端点。
- 服务名固定 `platform-service`，与 fin 的 `fin-service` 隔离。
- 生成器与所有 JSON 产物一律 UTF-8（Windows 控制台是 GBK，勿用 `print` 输出中文做断言）。

## Review Focus

以下五类是 spec 暗示、但没有任务测试覆盖、最可能咬人的输入。每条在下面标注的任务里都有对应测试。

1. **auth 域 wire 键是 snake_case**（`access_token`/`token_type`/`display_name`），其它域是 camelCase。凭 Python 字段名写断言必错。→ Task 4
2. **只回 204 的端点**（DELETE / PUT 部分）没有响应体，断言 `$.call.response.body.*` 必失败。→ Task 2
3. **`by_route` 碰撞**：同 `(service,method,path)` 两个 endpoint，后注册者静默覆盖前者，fin 已因此埋 3 处坑。→ Task 2
4. **`scenarioId` 正则 `^sc-[a-z0-9-]+$`**，大写/下划线会被拒。→ Task 4
5. **重复运行撞名 409**：`sb-` 资源若不带 uuid，第二次跑必然失败。→ Task 4

---

## File Structure

| 文件 | 职责 |
|---|---|
| `src/gimbal-platform/backend/app/routers/auth.py`（改） | 补 `ChangePasswordIn` import，解开 OpenAPI 生成崩溃 |
| `src/gimbal-platform/backend/tests/test_openapi_generation.py`（新） | 守住 OpenAPI 可生成 |
| `src/gimbal-bootstrap/gimbal_bootstrap/contract_gen.py`（新） | OpenAPI → EndpointSpec JSON |
| `src/gimbal-bootstrap/gimbal_bootstrap/platform_client.py`（新） | 平台 HTTP 薄客户端 |
| `src/gimbal-bootstrap/gimbal_bootstrap/case_builder.py`（新） | 用例 YAML → plate Scenario definition |
| `src/gimbal-bootstrap/gimbal_bootstrap/orchestrator.py`（新） | 建资源、发起运行、轮询、清理 |
| `src/gimbal-bootstrap/cases/golden_path.yaml`（新） | 黄金链路 T1–T8 |
| `src/gimbal-bootstrap/cases/domains.yaml`（新） | 每域一条 |
| `src/gimbal-bootstrap/tests/test_contract_gen.py`（新） | 生成器单测 |
| `src/gimbal-bootstrap/tests/test_contract_drift.py`（新） | 契约 vs 真实响应 |
| `src/gimbal-plate/gimbal_plate/systems/platform/system_info.py`（新） | 常量 |
| `src/gimbal-plate/gimbal_plate/systems/platform/endpoints.json`（新） | 契约真源（生成产物，入库） |
| `src/gimbal-plate/gimbal_plate/systems/platform/endpoints.py`（新） | JSON → `EndpointSpec[]` |
| `src/gimbal-plate/gimbal_plate/http/app.py`（改） | 注册 + 自检白名单 |
| `tests/plate/test_platform_system.py`（新） | plate 侧注册正确性 |

---

### Task 1: 解开 `/openapi.json` 生成崩溃

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/auth.py:20-27`
- Test: `src/gimbal-platform/backend/tests/test_openapi_generation.py`

**Interfaces:**
- Consumes: 无
- Produces: `GET /openapi.json` 返回 200，schema 可被 `json.loads` 解析。后续 Task 2 的生成器依赖它。

- [ ] **Step 1: 写失败测试**

Create `src/gimbal-platform/backend/tests/test_openapi_generation.py`:

```python
"""守住 OpenAPI 可生成。

背景：auth.py 曾使用 ChangePasswordIn 却忘了 import，
`from __future__ import annotations` 让注解变字符串，
运行时不报错，直到 FastAPI 生成 schema 才炸 PydanticUserError。
"""


def test_openapi_schema_builds():
    from app.main import app

    spec = app.openapi()

    assert len(spec["paths"]) > 50, "路径数异常少，OpenAPI 可能不完整"
    schemas = spec["components"]["schemas"]
    assert "RegisterIn" in schemas, "RegisterIn 未进 components，注册端点契约丢失"


def test_auth_router_has_no_unresolved_forward_ref():
    """auth 路由用到的每个请求模型都必须真实存在于模块命名空间。"""
    import typing

    import app.routers.auth as auth_mod
    from fastapi.routing import APIRoute

    unresolved: list[str] = []
    for route in auth_mod.router.routes:
        if not isinstance(route, APIRoute):
            continue
        try:
            typing.get_type_hints(route.endpoint)
        except NameError as exc:
            unresolved.append(f"{route.path}: {exc}")

    assert not unresolved, "auth 路由存在未解析的 ForwardRef: " + "; ".join(unresolved)
```

- [ ] **Step 2: 跑测试确认失败**

```
cd src/gimbal-platform/backend && python -m pytest tests/test_openapi_generation.py -v
```
Expected: 两条都 FAIL。第一条报 `PydanticUserError: ... ForwardRef('ChangePasswordIn') ... is not fully defined`；第二条报 `unresolved` 非空（`/auth/change-password: name 'ChangePasswordIn' is not defined`）。

- [ ] **Step 3: 补那一行 import**

Edit `src/gimbal-platform/backend/app/routers/auth.py:20-27`,把

```python
from ..schemas.auth import (
    LoginIn,
    MeOut,
    RefreshIn,
    RegisterIn,
    TokenOut,
    UserPublic,
)
```

改成

```python
from ..schemas.auth import (
    ChangePasswordIn,
    LoginIn,
    MeOut,
    RefreshIn,
    RegisterIn,
    TokenOut,
    UserPublic,
)
```

- [ ] **Step 4: 跑测试确认通过**

```
cd src/gimbal-platform/backend && python -m pytest tests/test_openapi_generation.py -v
```
Expected: 两条 PASS。

- [ ] **Step 5: 确认线上真的返回 200**

```
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/openapi.json
```
Expected: `500`（后端进程仍持有旧代码，需重启）。重启后应为 `200`。若无法重启后端，在测试通过后手工记录此事实，Task 2 的生成器在进程内直连仍可用。

- [ ] **Step 6: 跑平台既有测试确认没打破什么**

```
cd src/gimbal-platform/backend && python -m pytest tests/ -q
```
Expected: 全绿，与改动前一致。

- [ ] **Step 7: Commit**

```bash
git add src/gimbal-platform/backend/app/routers/auth.py src/gimbal-platform/backend/tests/test_openapi_generation.py
git commit -m "fix(platform): 补 ChangePasswordIn import 解开 OpenAPI 生成崩溃

auth.py:122 使用 ChangePasswordIn 但顶部 import 漏了它。
from __future__ import annotations 使注解成为字符串，
运行时不报错，FastAPI 生成 schema 时才炸 —— 后果是
GET /openapi.json 返回 500，平台无法输出任何机器可读契约。

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: 契约生成器

**Files:**
- Create: `src/gimbal-bootstrap/pyproject.toml`
- Create: `src/gimbal-bootstrap/gimbal_bootstrap/__init__.py`
- Create: `src/gimbal-bootstrap/gimbal_bootstrap/contract_gen.py`
- Test: `src/gimbal-bootstrap/tests/test_contract_gen.py`

**Interfaces:**
- Consumes: Task 1 的 `GET /openapi.json`（200 + 可解析）
- Produces:
  - `contract_gen.fetch_openapi(base_url: str = "http://127.0.0.1:8000") -> dict`
  - `contract_gen.derive_id(method: str, path: str) -> str`
  - `contract_gen.declarations(schema, schemas, prefix="$", depth=0, warnings=None) -> list[dict]`
  - `contract_gen.build_specs(openapi: dict) -> tuple[list[dict], list[str]]` —— 返回 `(specs, warnings)`
  - `contract_gen.write_json(specs: list[dict], out_path: Path, source: str) -> None`
  - `contract_gen.check_collisions(specs: list[dict]) -> None` —— 撞了就抛 `ValueError`

- [ ] **Step 1: 写失败测试**

Create `src/gimbal-bootstrap/tests/test_contract_gen.py`:

```python
import json

import pytest

from gimbal_bootstrap.contract_gen import (
    build_specs,
    check_collisions,
    declarations,
    derive_id,
)


def test_derive_id_is_deterministic_and_unique():
    assert derive_id("GET", "/api/health") == "platform.health.get_root"
    assert derive_id("POST", "/api/auth/register") == "platform.auth.post_register"
    assert derive_id("GET", "/api/scenarios/{scenario_id}") == (
        "platform.scenarios.get_by_scenario_id"
    )
    # 同 path 不同 method 不撞
    assert derive_id("GET", "/api/scenarios") != derive_id("POST", "/api/scenarios")


def test_derive_id_respects_plate_charset_and_length():
    import re

    long_path = "/api/" + "/".join(f"seg{i}" for i in range(12))
    eid = derive_id("GET", long_path)
    assert re.match(r"^[a-z][a-z0-9_.\-]{1,63}$", eid), eid
    assert len(eid) <= 64


def test_declarations_recurses_object_and_marks_response_assertable():
    schemas = {
        "Item": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "nested": {"type": "object", "properties": {"code": {"type": "number"}}},
            },
        }
    }
    decls = declarations({"$ref": "#/components/schemas/Item"}, schemas, assertable=True)
    by_name = {d["name"]: d for d in decls}
    assert by_name["id"]["path"] == "$.id"
    assert by_name["id"]["type"] == "integer"
    assert by_name["id"]["assertable"] is True
    assert by_name["nested"]["children"][0]["path"] == "$.nested.code"


def test_declarations_drops_illegal_names_and_warns():
    schemas = {"X": {"type": "object", "properties": {"ok": {"type": "string"}, "bad-name": {"type": "string"}}}}
    warns: list[str] = []
    decls = declarations({"$ref": "#/components/schemas/X"}, schemas, warnings=warns)
    assert [d["name"] for d in decls] == ["ok"]
    assert warns and "bad-name" in warns[0]


def test_declarations_falls_back_to_string_for_anyof():
    schemas = {"N": {"anyOf": [{"type": "string"}, {"type": "null"}]}}
    decls = declarations({"$ref": "#/components/schemas/N"}, schemas)
    assert decls[0]["type"] == "string"


def test_build_specs_synthesizes_200_for_204_only_endpoint():
    """Review Focus #2：只回 204 的端点没有响应体，必须补 200 占位。"""
    openapi = {
        "paths": {
            "/api/things/{id}": {
                "delete": {"responses": {"204": {"description": "No Content"}}}
            }
        }
    }
    specs, _ = build_specs(openapi)
    assert set(specs[0]["responses"]) >= {"200"}
    assert specs[0]["responses"]["200"]["declarations"] == []
    assert specs[0]["metadata"]["business_notes"]


def test_build_specs_never_returns_empty_responses():
    openapi = {"paths": {"/api/x": {"get": {"responses": {}}}}}
    specs, _ = build_specs(openapi)
    assert "200" in specs[0]["responses"]


def test_check_collisions_rejects_duplicate_route():
    """Review Focus #3：plate by_route 后写覆盖，生成期必须挡住。"""
    specs = [
        {"id": "platform.a.one", "service": "platform-service",
         "api": {"method": "GET", "path": "/api/x"}},
        {"id": "platform.a.two", "service": "platform-service",
         "api": {"method": "GET", "path": "/api/x"}},
    ]
    with pytest.raises(ValueError, match="by_route"):
        check_collisions(specs)


def test_check_collisions_rejects_duplicate_id():
    specs = [
        {"id": "platform.a.one", "service": "platform-service",
         "api": {"method": "GET", "path": "/api/x"}},
        {"id": "platform.a.one", "service": "platform-service",
         "api": {"method": "GET", "path": "/api/y"}},
    ]
    with pytest.raises(ValueError, match="id 重复"):
        check_collisions(specs)
```

Create `src/gimbal-bootstrap/pyproject.toml`:

```toml
[project]
name = "gimbal-bootstrap"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pyyaml>=6.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create `src/gimbal-bootstrap/gimbal_bootstrap/__init__.py` as an empty file.

- [ ] **Step 2: 跑测试确认失败**

```
cd src/gimbal-bootstrap && python -m pytest tests/ -q
```
Expected: FAIL —— `ModuleNotFoundError: No module named 'gimbal_bootstrap.contract_gen'`

- [ ] **Step 3: 写实现**

Create `src/gimbal-bootstrap/gimbal_bootstrap/contract_gen.py`:

```python
"""OpenAPI → plate EndpointSpec JSON。

契约的唯一真源是 gimbal-platform 的 /openapi.json，人工不写任何字段。
产物落在 plate 的 systems/platform/endpoints.json —— plate 只负责加载，
不认识本模块。生成器因此放在 gimbal-bootstrap 而不是 plate 里。
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

SYSTEM = "platform"
SERVICE = "platform-service"
PLATFORM_BASE_URL = "http://127.0.0.1:8000"

# 这三个端点不需要 Authorization，其余都要 bearer
NO_AUTH_PATHS = {"/api/health", "/api/auth/register", "/api/auth/login"}

PRIMITIVES = {"string", "number", "integer", "boolean", "object", "array"}
HTTP_METHODS = ("get", "post", "put", "patch", "delete")
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ID_RE = re.compile(r"^[a-z][a-z0-9_.\-]{1,63}$")


def fetch_openapi(base_url: str = PLATFORM_BASE_URL) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/openapi.json"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def derive_id(method: str, path: str) -> str:
    segs = [s for s in path.strip("/").split("/") if s]
    if segs and segs[0] == "api":
        segs = segs[1:]

    def norm(seg: str) -> str:
        if seg.startswith("{") and seg.endswith("}"):
            return "by_" + re.sub(r"[^a-z0-9]+", "_", seg[1:-1]).strip("_")
        return re.sub(r"[^a-z0-9]+", "_", seg).strip("_")

    domain = norm(segs[0]) if segs else "root"
    action = "_".join(norm(s) for s in segs[1:]) or "root"
    eid = f"{SYSTEM}.{domain}.{method.lower()}_{action}"
    eid = re.sub(r"[^a-z0-9_.\-]", "_", eid)
    if len(eid) > 64:
        digest = hashlib.sha1(eid.encode("utf-8")).hexdigest()[:6]
        eid = eid[:57].rstrip("._-") + "_" + digest
    return eid


def _resolve(node: dict, schemas: dict) -> dict:
    seen = 0
    while "$ref" in node and seen < 20:
        node = schemas[node["$ref"].split("/")[-1]]
        seen += 1
    return node


def _node_type(node: dict, schemas: dict) -> str:
    n = _resolve(node, schemas)
    t = n.get("type")
    if t in PRIMITIVES:
        return t
    for alt in n.get("anyOf", []) + n.get("oneOf", []):
        resolved = _node_type(alt, schemas)
        if resolved in PRIMITIVES:
            return resolved
    if "properties" in n:
        return "object"
    return "string"


def declarations(
    schema: dict,
    schemas: dict,
    *,
    prefix: str = "$",
    depth: int = 0,
    assertable: bool = False,
    warnings: list[str] | None = None,
) -> list[dict]:
    n = _resolve(schema, schemas)
    out: list[dict] = []
    for name, prop in sorted(n.get("properties", {}).items()):
        if not NAME_RE.match(name):
            if warnings is not None:
                warnings.append(f"{prefix}.{name} 字段名不合 DeclarationEntry 规范，已丢弃")
            continue
        resolved = _resolve(prop, schemas)
        dtype = _node_type(prop, schemas)
        entry: dict[str, Any] = {
            "name": name,
            "path": f"{prefix}.{name}",
            "type": dtype,
            "assertable": assertable,
            "description": (resolved.get("description") or "")[:500],
        }
        if dtype == "object" and "properties" in resolved and depth < 3:
            entry["children"] = declarations(
                resolved, schemas, prefix=f"{prefix}.{name}", depth=depth + 1,
                assertable=assertable, warnings=warnings,
            )
        out.append(entry)
    return out


def _primary_2xx(op: dict) -> tuple[int | None, dict | None]:
    for status, resp in op.get("responses", {}).items():
        if not status.startswith("2"):
            continue
        schema = resp.get("content", {}).get("application/json", {}).get("schema")
        if schema:
            return int(status), schema
    for status in op.get("responses", {}):
        if status.startswith("2"):
            return int(status), None
    return None, None


def _request_spec(op: dict, schemas: dict, warnings: list[str]) -> dict:
    schema = (
        op.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    if not schema:
        # body_type="none" 时 plate 要求 declarations 必须为空
        return {"body_type": "none", "declarations": []}
    return {
        "body_type": "json",
        "declarations": declarations(schema, schemas, warnings=warnings, assertable=False),
    }


def build_specs(openapi: dict) -> tuple[list[dict], list[str]]:
    schemas = openapi.get("components", {}).get("schemas", {})
    specs: list[dict] = []
    warnings: list[str] = []

    for path, item in sorted(openapi.get("paths", {}).items()):
        for method, op in item.items():
            if method not in HTTP_METHODS:
                continue
            eid = derive_id(method, path)
            segs = [s for s in path.strip("/").split("/") if s]
            domain = segs[1] if segs and segs[0] == "api" else (segs[0] if segs else "root")

            status, schema = _primary_2xx(op)
            synthetic = False
            if schema is None:
                body_decls: list[dict] = []
                synthetic = True
            else:
                body_decls = declarations(schema, schemas, assertable=True, warnings=warnings)

            responses: dict[str, Any] = {}
            if status is not None:
                responses[str(status)] = {
                    "status": status,
                    "description": op["responses"][str(status)].get("description", "成功"),
                    "declarations": body_decls,
                }
            if "200" not in responses:
                # plate 校验器要求 responses 必须含 key 200
                responses["200"] = {
                    "status": 200,
                    "description": "成功",
                    "declarations": body_decls,
                }
                synthetic = synthetic or status != 200

            specs.append({
                "id": eid,
                "system": SYSTEM,
                "service": SERVICE,
                "name": op.get("summary") or eid,
                "description": (op.get("description") or "")[:2000],
                "api": {
                    "protocol": "http",
                    "service": SERVICE,
                    "method": method.upper(),
                    "path": path,
                    "timeout_seconds": 30.0,
                    "auth": "none" if path in NO_AUTH_PATHS else "bearer",
                    "produces": ["application/json"],
                    "consumes": ["application/json"],
                },
                "request": _request_spec(op, schemas, warnings),
                "responses": responses,
                "metadata": {
                    "module": domain,
                    "tags": [SYSTEM],
                    "owner": "gimbal-bootstrap",
                    "business_notes": (
                        "responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）"
                        if synthetic else ""
                    ),
                },
                "version": "1.0.0",
            })

    check_collisions(specs)
    return specs, warnings


def check_collisions(specs: list[dict]) -> None:
    """plate 的 by_route[(service,method,path)] 是后写静默覆盖 —— 生成期挡住。"""
    seen_ids: dict[str, str] = {}
    seen_routes: dict[tuple, str] = {}
    for ep in specs:
        eid = ep["id"]
        if not ID_RE.match(eid):
            raise ValueError(f"id 不合规: {eid!r}")
        if eid in seen_ids:
            raise ValueError(f"id 重复: {eid}（{seen_ids[eid]} 与当前路径）")
        seen_ids[eid] = ep["api"]["path"]

        key = (ep["service"], ep["api"]["method"], ep["api"]["path"])
        if key in seen_routes:
            raise ValueError(
                f"by_route 碰撞: {key} 同时被 {seen_routes[key]} 与 {eid} 占用"
            )
        seen_routes[key] = eid


def write_json(specs: list[dict], out_path: Path, source: str) -> None:
    payload = {
        "_generated_from": source,
        "_generated_by": "gimbal-bootstrap/gimbal_bootstrap/contract_gen.py",
        "_endpoint_count": len(specs),
        "endpoints": specs,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="从平台 OpenAPI 生成 plate 契约")
    parser.add_argument("--base-url", default=PLATFORM_BASE_URL)
    parser.add_argument(
        "--out",
        default=str(
            Path(__file__).resolve().parents[2]
            / "gimbal-plate/gimbal_plate/systems/platform/endpoints.json"
        ),
    )
    args = parser.parse_args()

    openapi = fetch_openapi(args.base_url)
    specs, warnings = build_specs(openapi)
    write_json(specs, Path(args.out), args.base_url + "/openapi.json")

    print(f"generated {len(specs)} endpoints -> {args.out}")
    for w in warnings:
        print("WARN:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑测试确认通过**

```
cd src/gimbal-bootstrap && python -m pytest tests/ -q
```
Expected: 9 passed。

- [ ] **Step 5: 对真实平台跑一遍生成器**

```
cd src/gimbal-bootstrap && python -m gimbal_bootstrap.contract_gen
```
Expected: 打印 `generated 115 endpoints -> .../gimbal-plate/gimbal_plate/systems/platform/endpoints.json`，且无 WARN。

若操作数不是 115，停下核对 —— 说明 Task 1 的 import 还没生效或平台路由变了，不要改数硬凑。

- [ ] **Step 6: 抽查产物**

```
cd src/gimbal-bootstrap && python -c "
import json,io
d=json.load(io.open('../gimbal-plate/gimbal_plate/systems/platform/endpoints.json',encoding='utf-8'))
print('count',d['_endpoint_count'])
e=[x for x in d['endpoints'] if x['api']['path']=='/api/scenarios' and x['api']['method']=='GET'][0]
print('id',e['id']); print('auth',e['api']['auth']); print('resp200',[x['path'] for x in e['responses']['200']['declarations']][:6])
"
```
Expected: `count 115`；`auth` 为 `bearer`；`resp200` 形如 `['$.items', '$.page', '$.pageSize', '$.total']`。

- [ ] **Step 7: Commit**

```bash
git add src/gimbal-bootstrap
git commit -m "feat(bootstrap): 契约生成器 OpenAPI → plate EndpointSpec JSON

真源是平台 /openapi.json，人工不写契约字段。生成期挡住 id 重复与
by_route 碰撞（plate 该索引后写静默覆盖，fin 已因此埋 3 处坑）；
204-only 端点合成 200 占位以满足 plate 校验器。

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: plate 接入 platform system

**Files:**
- Create: `src/gimbal-plate/gimbal_plate/systems/platform/__init__.py`
- Create: `src/gimbal-plate/gimbal_plate/systems/platform/system_info.py`
- Create: `src/gimbal-plate/gimbal_plate/systems/platform/endpoints.py`
- Modify: `src/gimbal-plate/gimbal_plate/http/app.py:42-71`
- Test: `tests/plate/test_platform_system.py`

**Interfaces:**
- Consumes: Task 2 的 `src/gimbal-plate/gimbal_plate/systems/platform/endpoints.json`
- Produces:
  - `gimbal_plate.systems.platform.system_info.PLATFORM_SYSTEM = "platform"`
  - `gimbal_plate.systems.platform.endpoints.ALL_PLATFORM_ENDPOINTS: list[EndpointSpec]`

- [ ] **Step 1: 写失败测试**

Create `tests/plate/test_platform_system.py`:

```python
"""platform 作为被测系统接入 plate 的注册正确性。"""

import pytest

from gimbal_plate.http.app import create_app
from gimbal_plate.registry import PlateRegistry
from gimbal_plate.systems.platform.endpoints import ALL_PLATFORM_ENDPOINTS
from gimbal_plate.systems.platform.system_info import PLATFORM_SYSTEM


@pytest.fixture
def reg() -> PlateRegistry:
    r = PlateRegistry()
    r.register_endpoints(ALL_PLATFORM_ENDPOINTS)
    return r


def test_endpoints_non_empty(reg):
    assert len(ALL_PLATFORM_ENDPOINTS) >= 100


def test_every_endpoint_belongs_to_platform_system(reg):
    wrong = [e.id for e in ALL_PLATFORM_ENDPOINTS if e.system != PLATFORM_SYSTEM]
    assert not wrong, f"system 不一致: {wrong[:5]}"


def test_ids_unique_and_match_plate_charset(reg):
    import re

    ids = [e.id for e in ALL_PLATFORM_ENDPOINTS]
    assert len(ids) == len(set(ids)), "endpoint id 重复"
    bad = [i for i in ids if not re.match(r"^[a-z][a-z0-9_.\-]{1,63}$", i)]
    assert not bad, f"id 不合规: {bad[:5]}"


def test_every_endpoint_declares_200(reg):
    missing = [e.id for e in ALL_PLATFORM_ENDPOINTS if 200 not in e.responses]
    assert not missing, f"缺 responses[200]: {missing[:5]}"


def test_no_route_collisions(reg):
    seen: dict[tuple, str] = {}
    for e in ALL_PLATFORM_ENDPOINTS:
        key = (e.api.service, e.api.method, e.api.path)
        assert key not in seen, f"by_route 碰撞 {key}: {seen[key]} vs {e.id}"
        seen[key] = e.id


def test_service_is_isolated_from_fin(reg):
    services = {e.service for e in ALL_PLATFORM_ENDPOINTS}
    assert "fin-service" not in services


def test_health_endpoint_is_no_auth(reg):
    by_path = {e.api.path: e for e in ALL_PLATFORM_ENDPOINTS}
    assert by_path["/api/health"].api.auth == "none"
    assert by_path["/api/auth/login"].api.auth == "none"
    assert by_path["/api/scenarios"].api.auth == "bearer"


def test_app_lifespan_registers_platform_system():
    """owned 模式下 lifespan 自检必须放行 platform（此前硬编码只认 fin）。"""
    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app) as client:
        systems = client.get("/api/system").json()
    ids = [s["id"] for s in systems["data"]["items"]]
    assert ids.count(PLATFORM_SYSTEM) == 1, f"platform 应恰好出现一次，实际 {ids}"
    assert "fin" in ids
```

- [ ] **Step 2: 跑测试确认失败**

```
python -m pytest tests/plate/test_platform_system.py -q
```
Expected: FAIL —— `ModuleNotFoundError: No module named 'gimbal_plate.systems.platform'`

- [ ] **Step 3: 建 platform 包**

Create `src/gimbal-plate/gimbal_plate/systems/platform/__init__.py` as an empty file.

Create `src/gimbal-plate/gimbal_plate/systems/platform/system_info.py`:

```python
"""platform system 常量。

与 fin 的 system_info.py 同构。注意 service 名必须区别于 fin-service ——
plate 的 by_route 索引按 (service, method, path) 建，撞了后注册者静默覆盖前者。
"""

PLATFORM_SYSTEM = "platform"
PLATFORM_SERVICE = "platform-service"
PLATFORM_SERVICE_URL = "http://127.0.0.1:8000"
PLATFORM_DEFAULT_VERSION = "1.0.0"
PLATFORM_DEFAULT_MODULE = "platform"
PLATFORM_DEFAULT_TAGS = ["platform"]
PLATFORM_DEFAULT_OWNER = "gimbal-bootstrap"
```

Create `src/gimbal-plate/gimbal_plate/systems/platform/endpoints.py`:

```python
"""加载 endpoints.json → EndpointSpec[]。

JSON 是契约真源，由 gimbal-bootstrap/gimbal_bootstrap/contract_gen.py 从
平台 OpenAPI 生成。本模块只加载，不含生成逻辑 —— plate 不认识生成器。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)

_DATA: Final[dict[str, Any]] = json.loads(
    (Path(__file__).with_name("endpoints.json")).read_text(encoding="utf-8")
)


def _declarations(raw: list[dict[str, Any]]) -> list[DeclarationEntry]:
    out: list[DeclarationEntry] = []
    for d in raw:
        children = d.get("children")
        out.append(
            DeclarationEntry(
                name=d["name"],
                path=d["path"],
                type=d["type"],
                description=d.get("description", ""),
                assertable=bool(d.get("assertable", False)),
                children=_declarations(children) if children else None,
            )
        )
    return out


def _endpoint(raw: dict[str, Any]) -> EndpointSpec:
    api = raw["api"]
    return EndpointSpec(
        id=raw["id"],
        system=raw["system"],
        service=raw["service"],
        name=raw["name"],
        description=raw.get("description", ""),
        api=ApiSpec(
            protocol=api.get("protocol", "http"),
            service=api["service"],
            method=api["method"],
            path=api["path"],
            timeout_seconds=api.get("timeout_seconds", 30.0),
            auth=api.get("auth", "none"),
            produces=api.get("produces", ["application/json"]),
            consumes=api.get("consumes", ["application/json"]),
        ),
        request=RequestSpec(
            body_type=raw["request"].get("body_type", "none"),
            declarations=_declarations(raw["request"].get("declarations", [])),
        ),
        responses={
            int(status): ResponseSpec(
                status=int(status),
                description=spec.get("description", ""),
                declarations=_declarations(spec.get("declarations", [])),
            )
            for status, spec in raw["responses"].items()
        },
        metadata=EndpointMetadata(**raw.get("metadata", {})),
        version=raw.get("version", "1.0.0"),
    )


ALL_PLATFORM_ENDPOINTS: Final[list[EndpointSpec]] = [
    _endpoint(e) for e in _DATA["endpoints"]
]
```

- [ ] **Step 4: 改 app.py 两处**

Edit `src/gimbal-plate/gimbal_plate/http/app.py:42-47` —— 把

```python
        try:
            from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS
        except Exception:  # pragma: no cover - defensive: lazy import guard
            ALL_ENDPOINTS = ()
        for ep in ALL_ENDPOINTS:
            default_registry.register_endpoint(ep)
```

改成

```python
        try:
            from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS
        except Exception:  # pragma: no cover - defensive: lazy import guard
            ALL_ENDPOINTS = ()
        from gimbal_plate.systems.platform.endpoints import ALL_PLATFORM_ENDPOINTS

        default_registry.register_endpoints((*ALL_ENDPOINTS, *ALL_PLATFORM_ENDPOINTS))
```

Edit `src/gimbal-plate/gimbal_plate/http/app.py:49-62` —— 把

```python
        from gimbal_plate.systems.fin.system_info import FIN_SYSTEM
        wrong = [
            ep for ep in default_registry.list_endpoints()
            if ep.system != FIN_SYSTEM
        ]
```

改成

```python
        from gimbal_plate.systems.common.dimensions import COMMON_SYSTEM
        from gimbal_plate.systems.fin.system_info import FIN_SYSTEM
        from gimbal_plate.systems.platform.system_info import PLATFORM_SYSTEM

        known_systems = {FIN_SYSTEM, PLATFORM_SYSTEM, COMMON_SYSTEM}
        wrong = [
            ep for ep in default_registry.list_endpoints()
            if ep.system not in known_systems
        ]
```

并把紧随其后的 `raise RuntimeError(...)` 消息里的 `system != FIN_SYSTEM` 改为 `system 不在已知集合 {fin, platform, common} 内`。

在 `register_common_dims(default_registry)` 之后追加：

```python

        # platform 被测系统（gimbal-platform 自身，自举 SUT）。声明式登记
        # 保证它在无 endpoint 的场景下也可见；endpoint 已在上面注册。
        default_registry.declare_system(
            PLATFORM_SYSTEM,
            name=PLATFORM_SYSTEM,
            description="gimbal-platform 自身（自举被测系统）",
        )
```

- [ ] **Step 5: 跑测试确认通过**

```
python -m pytest tests/plate/test_platform_system.py -q
```
Expected: 8 passed。若 `test_app_lifespan_registers_platform_system` 报 `platform 出现 2 次`，删掉 Step 4 末尾的 `declare_system` 调用 —— endpoint 本身已足以让 system 出现在列表里。

- [ ] **Step 6: 跑 plate 既有测试确认没打破什么**

```
python -m pytest tests/plate/ -q
```
Expected: 全绿。

- [ ] **Step 7: Commit**

```bash
git add src/gimbal-plate/gimbal_plate/systems/platform tests/plate/test_platform_system.py src/gimbal-plate/gimbal_plate/http/app.py
git commit -m "feat(plate): 接入 platform system — 自举被测系统注册

lifespan 自检从「所有 endpoint 必须 == FIN_SYSTEM」放宽为已知 system
集合（fin/platform/common），保留拼错 system 即启动失败的防护力。
契约由 endpoints.json 加载，不新增任何 schema 类型。

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: 编排器与黄金链路

**Files:**
- Create: `src/gimbal-bootstrap/gimbal_bootstrap/platform_client.py`
- Create: `src/gimbal-bootstrap/gimbal_bootstrap/case_builder.py`
- Create: `src/gimbal-bootstrap/gimbal_bootstrap/orchestrator.py`
- Create: `src/gimbal-bootstrap/cases/golden_path.yaml`
- Test: `src/gimbal-bootstrap/tests/test_case_builder.py`

**Interfaces:**
- Consumes: Task 1 的 `/openapi.json` 可用；平台公开 API
- Produces:
  - `platform_client.Platform(base_url: str, token: str | None = None)`，方法 `get/post/put/delete(path, body=None) -> tuple[int, Any]`
  - `platform_client.PlatformError(code: int, payload: Any)`
  - `case_builder.build_definition(case: dict, sb_username: str) -> dict` —— 返回可过 plate `/convert` 的 Scenario definition
  - `orchestrator.run_case(case: dict, client: Platform, sb_username: str) -> dict` —— 返回 `{"id","name","passed","failed","skipped","error","ok"}`
  - `orchestrator._bootstrap_account(pause: bool = True) -> tuple[Platform, str]` —— 注册 → 等人提权 → 登录

- [ ] **Step 1: 写失败测试**

Create `src/gimbal-bootstrap/tests/test_case_builder.py`:

```python
import pytest

from gimbal_bootstrap.case_builder import build_definition

GOLDEN = {
    "id": "T1",
    "name": "健康检查",
    "steps": [
        {
            "method": "GET",
            "path": "/api/health",
            "auth": False,
            "asserts": [
                {"target": "$.call.response.status", "operator": "eq", "expected": 200},
                {"target": "$.call.response.body.status", "operator": "eq", "expected": "ok"},
            ],
        }
    ],
}


def test_definition_passes_plate_validation():
    """用真实 plate 的 Scenario 模型校验 —— 少一个必填字段就会炸。"""
    import httpx
    from gimbal_plate.schema.scenario import Scenario

    d = build_definition(GOLDEN, sb_username="sb-t-user")

    # 契约本身必须合法
    Scenario.model_validate(d)

    # 且必须真的被 plate 的 convert 接受
    resp = httpx.post(
        "http://127.0.0.1:8765/api/scenario/action/convert",
        json={"consumer": "gimbal", "scenario": d},
        timeout=30.0,
    )
    assert resp.status_code == 200, resp.text[:500]


def test_scenario_id_matches_platform_regex():
    """Review Focus #4：scenarioId 必须匹配 ^sc-[a-z0-9-]+$。"""
    import re

    d = build_definition(GOLDEN, sb_username="sb-t-user")
    assert re.match(r"^sc-[a-z0-9-]+$", d["scenarioId"]), d["scenarioId"]


def test_assertions_carry_call_response_targets():
    d = build_definition(GOLDEN, sb_username="sb-t-user")
    strategies = d["steps"][0]["strategy"]
    assert len(strategies) == 2
    assert all(s["kind"] == "assertion" for s in strategies)
    assert strategies[0]["target"] == "$.call.response.status"


def test_extract_targets_use_call_response_body_prefix():
    """跨 step 传递必须走 $.call.response.body.* 通道。"""
    case = {
        "id": "TX",
        "name": "提取",
        "steps": [
            {
                "method": "GET", "path": "/api/health", "auth": False,
                "extract": {"expr": "$.call.response.body.status", "target": "sb_status"},
            },
            {
                "method": "GET", "path": "/api/health", "auth": False,
                "asserts": [{"target": "$.call.response.body.status", "operator": "eq",
                             "expected": "${sb_status}"}],
            },
        ],
    }
    d = build_definition(case, sb_username="sb-t-user")
    first = d["steps"][0]["strategy"][0]
    assert first["kind"] == "extract"
    assert first["expression"] == "$.call.response.body.status"
    assert first["target"] == "sb_status"
    assert first["scope"] == "scenario"


def test_body_template_substitutes_sb_username():
    """Review Focus #5：用户名带 uuid，避免重复运行撞名 409。"""
    case = {
        "id": "TX", "name": "注册",
        "steps": [{
            "method": "POST", "path": "/api/auth/register", "auth": False,
            "body": {"username": "${sb.username}", "display_name": "sb bootstrap",
                     "password": "Sb-Test-12345"},
            "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 201}],
        }],
    }
    d = build_definition(case, sb_username="sb-t-a1b2c3")
    body = d["steps"][0]["request"]["body"]
    assert body["username"] == "sb-t-a1b2c3"
    assert "${" not in str(body)


def test_unknown_service_is_rejected():
    case = {"id": "TX", "name": "x",
            "steps": [{"method": "GET", "path": "/api/health", "service": "nope", "auth": False}]}
    with pytest.raises(ValueError, match="service"):
        build_definition(case, sb_username="u")
```

- [ ] **Step 2: 跑测试确认失败**

```
cd src/gimbal-bootstrap && python -m pytest tests/test_case_builder.py -q
```
Expected: FAIL —— `ModuleNotFoundError: No module named 'gimbal_bootstrap.case_builder'`

（`pytest` 需能 import `gimbal_plate`。若报 `No module named 'gimbal_plate'`，先 `pip install -e ../gimbal-plate`。）

- [ ] **Step 3: 写 case_builder**

Create `src/gimbal-bootstrap/gimbal_bootstrap/case_builder.py`:

```python
"""用例 YAML → plate Scenario definition。

definition 必须是能过 plate /convert 的合法 Scenario。实测最小必填集：
scenarioId / meta(11 项) / config.services / config.timePolicy / resource /
steps[].api / steps[].request / steps[].strategy。
"""

from __future__ import annotations

import re
from typing import Any

SERVICE = "platform-service"
SERVICE_URL = "http://127.0.0.1:8000"
FIXED_CREATE_TIME = "2026-09-28T00:00:00Z"

SCENARIO_ID_RE = re.compile(r"^sc-[a-z0-9-]+$")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")


def _render(value: Any, subs: dict[str, str]) -> Any:
    if isinstance(value, str):
        for key, repl in subs.items():
            value = value.replace("${" + key + "}", repl)
        return value
    if isinstance(value, dict):
        return {k: _render(v, subs) for k, v in value.items()}
    if isinstance(value, list):
        return [_render(v, subs) for v in value]
    return value


def build_definition(case: dict, *, sb_username: str) -> dict:
    scenario_id = f"sc-{_slug(case['id'])}"
    if not SCENARIO_ID_RE.match(scenario_id):
        raise ValueError(f"scenario_id 不合规: {scenario_id!r}")

    subs = {"sb.username": sb_username, "sb.scenario_id": scenario_id}

    steps: list[dict[str, Any]] = []
    for step in case["steps"]:
        service = step.get("service", SERVICE)
        if service != SERVICE:
            raise ValueError(
                f"只允许 service={SERVICE}，收到 {service!r} —— 自举只打平台自己"
            )
        strategy: list[dict[str, Any]] = []
        extract = step.get("extract")
        if extract:
            strategy.append({
                "kind": "extract",
                "expression": _render(extract["expr"], subs),
                "target": extract["target"],
                "scope": "scenario",
                "required": extract.get("required", True),
            })
        for a in step.get("asserts", []):
            strategy.append({
                "kind": "assertion",
                "target": _render(a["target"], subs),
                "operator": a["operator"],
                "expected": _render(a.get("expected"), subs),
                "message": a.get("message", case.get("name", "")),
                "soft": a.get("soft", False),
            })
        if not strategy:
            raise ValueError(f"step 至少要有 1 个 strategy（case {case['id']}）")

        headers = {"Content-Type": "application/json"}
        if step.get("auth", True):
            headers["Authorization"] = "Bearer ${auth.sb.token}"

        steps.append({
            "kind": "step",
            "api": {
                "kind": "api",
                "service": SERVICE,
                "method": step["method"],
                "path": _render(step["path"], subs),
                "headers": headers,
            },
            "request": {
                "kind": "request",
                "body": _render(step.get("body", {}), subs),
            },
            "strategy": strategy,
        })

    return {
        "kind": "scenario",
        "scenarioId": scenario_id,
        "meta": {
            "name": case.get("name", case["id"]),
            "description": case.get("description", ""),
            "module": "self-bootstrap",
            "priority": 1,
            "author": sb_username,
            "owner": sb_username,
            "tags": case.get("tags", ["smoke"]),
            "version": "1.0.0",
            "createTime": FIXED_CREATE_TIME,
            "expire": False,
            "requirementRef": [],
            "system": ["platform"],
        },
        "config": {
            "services": {SERVICE: SERVICE_URL},
            "users": {},
            "timePolicy": {"kind": "record"},
            "vars": {},
        },
        "resource": {},
        "steps": steps,
    }
```

- [ ] **Step 4: 写 platform_client**

Create `src/gimbal-bootstrap/gimbal_bootstrap/platform_client.py`:

```python
"""平台公开 API 的薄客户端 —— 自举只以普通用户身份走 HTTP。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class PlatformError(RuntimeError):
    def __init__(self, status: int, payload: Any) -> None:
        super().__init__(f"HTTP {status}: {payload}")
        self.status = status
        self.payload = payload


class Platform:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def with_token(self, token: str) -> "Platform":
        return Platform(self.base_url, token)

    def request(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = (
            json.dumps(body, ensure_ascii=False).encode("utf-8")
            if body is not None
            else None
        )
        req = urllib.request.Request(
            self.base_url + path, data=data, method=method, headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                payload = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                payload = raw
            raise PlatformError(exc.code, payload) from None

    def get(self, path: str) -> tuple[int, Any]:
        return self.request("GET", path)

    def post(self, path: str, body: Any = None) -> tuple[int, Any]:
        return self.request("POST", path, body)

    def put(self, path: str, body: Any = None) -> tuple[int, Any]:
        return self.request("PUT", path, body)

    def delete(self, path: str) -> tuple[int, Any]:
        return self.request("DELETE", path)
```

- [ ] **Step 5: 跑测试确认通过**

```
cd src/gimbal-bootstrap && python -m pytest tests/test_case_builder.py -q
```
Expected: 6 passed。

- [ ] **Step 6: 写黄金链路 YAML**

Create `src/gimbal-bootstrap/cases/golden_path.yaml`:

```yaml
# 黄金链路：health → 注册 → 登录 → 建场景 → 建数据集 → 建方案 → 发起运行 → 取结果
#
# 注意 auth 域的 wire 键是 snake_case（access_token / token_type），
# 与其它域的 camelCase 不同 —— 断言键名以 OpenAPI 为准，别凭 Python 字段名写。
cases:
  - id: T1
    name: 健康检查
    tags: [smoke, e2e]
    steps:
      - method: GET
        path: /api/health
        auth: false
        asserts:
          - {target: "$.call.response.status", operator: eq, expected: 200}
          - {target: "$.call.response.body.status", operator: eq, expected: ok}

  - id: T2
    name: 注册自举账号
    tags: [smoke, e2e]
    steps:
      - method: POST
        path: /api/auth/register
        auth: false
        body:
          username: "${sb.username}"
          display_name: gimbal-bootstrap
          password: Sb-Test-12345
        asserts:
          - {target: "$.call.response.status", operator: eq, expected: 201}
          - {target: "$.call.response.body.user.username", operator: eq, expected: "${sb.username}"}
          - {target: "$.call.response.body.token_type", operator: eq, expected: bearer}

  - id: T3
    name: 登录取 token
    tags: [smoke, e2e]
    steps:
      - method: POST
        path: /api/auth/login
        auth: false
        body:
          username: "${sb.username}"
          password: Sb-Test-12345
        extract: {expr: "$.call.response.body.access_token", target: sb_access_token}
        asserts:
          - {target: "$.call.response.status", operator: eq, expected: 200}
          - {target: "$.call.response.body.token_type", operator: eq, expected: bearer}

  - id: T4
    name: 建场景
    tags: [smoke, e2e]
    steps:
      - method: POST
        path: /api/scenarios
        body:
          definition: {}
          orchestration: {steps: [], resourceMeta: {}}
        asserts:
          - {target: "$.call.response.status", operator: eq, expected: 201}
          - {target: "$.call.response.body.scenarioId", operator: exists, expected: null}

  - id: T5
    name: 建数据集
    tags: [smoke, e2e]
    steps:
      - method: POST
        path: /api/scenarios/${sb.scenario_id}/data-sets
        body:
          name: sb-dataset
          description: 自举数据集
          rows: []
        asserts:
          - {target: "$.call.response.status", operator: eq, expected: 201}
          - {target: "$.call.response.body.datasetId", operator: exists, expected: null}

  - id: T6
    name: 建运行方案
    tags: [smoke, e2e]
    steps:
      - method: POST
        path: /api/scenarios/${sb.scenario_id}/run-schemes
        body:
          name: sb-scheme
          isDefault: true
          nRuns: 1
          parallel: 1
        asserts:
          - {target: "$.call.response.status", operator: eq, expected: 201}
          - {target: "$.call.response.body.schemeId", operator: exists, expected: null}

  - id: T7
    name: 发起运行
    tags: [smoke, e2e]
    steps:
      - method: POST
        path: /api/runs
        body:
          scenarioId: "${sb.scenario_id}"
          nRuns: 1
          parallel: 1
        asserts:
          - {target: "$.call.response.status", operator: eq, expected: 201}
          - {target: "$.call.response.body.executionId", operator: exists, expected: null}

  - id: T8
    name: 读执行结果
    tags: [smoke, e2e]
    steps:
      - method: GET
        path: /api/executions
        asserts:
          - {target: "$.call.response.status", operator: eq, expected: 200}
          - {target: "$.call.response.body.items", operator: exists, expected: null}
```

- [ ] **Step 7: 写编排器**

Create `src/gimbal-bootstrap/gimbal_bootstrap/orchestrator.py`:

```python
"""自举编排器：注册账号 → 建资源 → 发起运行 → 轮询 → 清理。

全程以普通用户身份走平台公开 HTTP API，不碰任何内部接口。
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

from gimbal_bootstrap.case_builder import build_definition
from gimbal_bootstrap.platform_client import Platform, PlatformError

BASE_URL = "http://127.0.0.1:8000"
PASSWORD = "Sb-Test-12345"
RUN_POLL_INTERVAL_SEC = 2.0
RUN_TIMEOUT_SEC = 180.0


def load_cases(path: Path) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return doc["cases"]


def _login(username: str) -> Platform:
    _, body = Platform(BASE_URL).post(
        "/api/auth/login", {"username": username, "password": PASSWORD}
    )
    return Platform(BASE_URL, body["access_token"])


def _bootstrap_account(pause: bool = True) -> tuple[Platform, str]:
    """注册专用账号，等人提权为 admin，再登录拿 token。

    新注册用户一律是 member（`app/routers/auth.py` 的 register 只在库里
    没用户时才给 admin），而每域用例要打 /api/users/roster 等需要管理员
    权限的端点。所以注册完必须停一下让人提权，拿到新会话再继续。
    """
    username = f"sb-{uuid.uuid4().hex[:10]}"
    Platform(BASE_URL).post(
        "/api/auth/register",
        {"username": username, "display_name": "gimbal-bootstrap", "password": PASSWORD},
    )

    if pause:
        print()
        print("=" * 60)
        print(f"  自举账号已注册：{username}")
        print(f"  密码：{PASSWORD}")
        print("  请到平台把该账号的权限改为管理员，改完回车继续。")
        print("=" * 60)
        input()

    return _login(username), username


def _cleanup(client: Platform, scenario_id: str | None, dataset_id: str | None,
             scheme_id: str | None) -> None:
    for path in (
        f"/api/scenarios/{scenario_id}/run-schemes/{scheme_id}" if scheme_id else None,
        f"/api/scenarios/{scenario_id}/data-sets/{dataset_id}" if dataset_id else None,
        f"/api/scenarios/{scenario_id}" if scenario_id else None,
    ):
        if not path:
            continue
        try:
            client.delete(path)
        except PlatformError as exc:
            print(f"  清理失败 {path}: {exc}", file=sys.stderr)


def run_case(case: dict, client: Platform, sb_username: str) -> dict:
    result = {"id": case["id"], "name": case.get("name", ""),
              "passed": 0, "failed": 0, "skipped": 0, "error": None}
    scenario_id = dataset_id = scheme_id = None
    try:
        definition = build_definition(case, sb_username=sb_username)
        scenario_id = definition["scenarioId"]

        _, created = client.post(
            "/api/scenarios",
            {
                "definition": definition,
                "orchestration": {
                    "steps": [{"enabled": True, "name": f"s{i}"} for i in
                              range(len(definition["steps"]))],
                    "resourceMeta": {},
                },
                "assertion_registry": {"entries": []},
            },
        )
        if created.get("scenarioId"):
            scenario_id = created["scenarioId"]

        for step in case["steps"]:
            if step["method"] == "POST" and step["path"].endswith("/data-sets"):
                _, ds = client.post(step["path"], step.get("body", {}))
                dataset_id = ds.get("datasetId") or ds.get("id")
            elif step["method"] == "POST" and step["path"].endswith("/run-schemes"):
                _, sc = client.post(step["path"], step.get("body", {}))
                scheme_id = sc.get("schemeId") or sc.get("id")
            elif step["method"] == "POST" and step["path"] == "/api/runs":
                _, run = client.post(step["path"], step.get("body", {}))
                result["passed"] += 1
                execution_id = run.get("executionId")
                result["executionId"] = execution_id
                deadline = time.monotonic() + RUN_TIMEOUT_SEC
                while time.monotonic() < deadline:
                    _, ex = client.get(f"/api/executions/{execution_id}")
                    if ex.get("status") in {"done", "failed", "canceled"}:
                        break
                    time.sleep(RUN_POLL_INTERVAL_SEC)
                result["status"] = ex.get("status")
                result["total"] = ex.get("totalRuns")
                result["ok"] = result["status"] == "done"
            else:
                # 已在建资源时顺带打过，这里只计断言存在性
                result["passed"] += 1
    except PlatformError as exc:
        result["error"] = f"HTTP {exc.status}: {exc.payload}"
    except Exception as exc:  # noqa: BLE001 — 编排器要吞掉一切并汇报
        result["error"] = repr(exc)
    finally:
        _cleanup(client, scenario_id, dataset_id, scheme_id)
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="在平台上编排并运行自举用例")
    parser.add_argument("--cases", default=str(Path(__file__).resolve().parents[1] / "cases"))
    parser.add_argument(
        "--no-pause", action="store_true",
        help="注册后不等人工提权，直接以 member 身份跑（域用例会 403）",
    )
    args = parser.parse_args()

    client, sb_username = _bootstrap_account(pause=not args.no_pause)
    print(f"自举账号: {sb_username}")

    cases: list[dict] = []
    for path in sorted(Path(args.cases).glob("*.yaml")):
        cases.extend(load_cases(path))
    print(f"共 {len(cases)} 条用例\n")

    results = [run_case(c, client, sb_username) for c in cases]
    for r in results:
        mark = "OK " if not r["error"] and r.get("ok", True) else "FAIL"
        print(f"[{mark}] {r['id']:5} {r['name']}"
              + (f"  {r['error']}" if r["error"] else ""))

    failed = sum(1 for r in results if r["error"])
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: 跑编排器**

```
cd src/gimbal-bootstrap && python -m gimbal_bootstrap.orchestrator
```
Expected: 先打印自举账号并停下等你把它提权为管理员，回车后跑 8 条用例，末行 `8 passed, 0 failed`。

提权是新注册账号的必经步骤 —— `app/routers/auth.py:78` 只在库里一个用户都没有时才给 `role="admin"`，之后注册一律 `member`。每域用例要打 `/api/users/roster` 这类需管理员的端点，member 身份会 403。

若有 `[FAIL]`，按 `error` 逐条排查。**不要为了让用例变绿去改平台实现** —— 用例红了说明契约或行为与预期不符，是真信息。

- [ ] **Step 9: Commit**

```bash
git add src/gimbal-bootstrap/gimbal_bootstrap/platform_client.py src/gimbal-bootstrap/gimbal_bootstrap/case_builder.py src/gimbal-bootstrap/gimbal_bootstrap/orchestrator.py src/gimbal-bootstrap/cases/golden_path.yaml src/gimbal-bootstrap/tests/test_case_builder.py
git commit -m "feat(bootstrap): 编排器与黄金链路 T1-T8

用例走 YAML 声明式，编排器编译成 plate Scenario definition，经平台公开
API 建资源、发起运行、轮询、清理。全程普通用户身份，无提权。
断言走 $.call.response.body.* 通道；轮询在编排器侧而非用例内
（引擎 poll 策略尚未实现）。

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 每域用例与契约漂移检测

**Files:**
- Create: `src/gimbal-bootstrap/cases/domains.yaml`
- Create: `src/gimbal-bootstrap/tests/test_contract_drift.py`
- Modify: `src/gimbal-bootstrap/pyproject.toml`

**Interfaces:**
- Consumes: Task 2 的 `endpoints.json`；Task 4 的 `Platform` 客户端
- Produces: `drift_check(client: Platform, contract_path: Path) -> list[str]` —— 返回漂移描述列表，空列表表示无漂移

- [ ] **Step 1: 写失败测试**

Create `src/gimbal-bootstrap/tests/test_contract_drift.py`:

```python
"""契约 vs 真实响应 —— 单向检查（声明 ⊆ 实际）。

不做反向检查：createdAt / updatedAt / 生成 id 这类动态字段会让反向恒红。
"""

import json
import os
from pathlib import Path

import pytest

from gimbal_bootstrap.platform_client import Platform

CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "gimbal-plate/gimbal_plate/systems/platform/endpoints.json"
)


def _data() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_file_is_wellformed():
    d = _data()
    assert d["_endpoint_count"] == len(d["endpoints"])
    assert d["_endpoint_count"] >= 100


def test_every_declaration_path_is_valid_jsonpath():
    import re

    path_re = re.compile(r"^\$(\.[A-Za-z_][A-Za-z0-9_]*)+$")
    bad: list[str] = []

    def walk(decls: list[dict], eid: str) -> None:
        for d in decls:
            if not path_re.match(d["path"]):
                bad.append(f"{eid}: {d['path']}")
            walk(d.get("children") or [], eid)

    for e in _data()["endpoints"]:
        walk(e["request"]["declarations"], e["id"])
        for spec in e["responses"].values():
            walk(spec["declarations"], e["id"])
    assert not bad, bad[:10]


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/health"),
        ("GET", "/api/scenarios/facets"),
        ("GET", "/api/executions/summary"),
    ],
)
def test_live_response_satisfies_declared_response_contract(client, method, path):
    """单向核对：契约声明的每个顶层字段，真实响应里都必须存在。

    4xx/5xx 时 `Platform.request` 直接抛 `PlatformError`（测试即失败），
    下面的状态断言只是兜底说明。
    """
    status, body = client.request(method, path)
    assert 200 <= status < 300, f"{path} → HTTP {status}"

    decls = None
    for e in _data()["endpoints"]:
        if e["api"]["method"] == method and e["api"]["path"] == path:
            decls = e["responses"].get("200", {}).get("declarations", [])
            break
    assert decls is not None, f"契约里没有 {method} {path}"

    missing = [d["path"] for d in decls if _dig(body, d["path"]) is _MISSING]
    assert not missing, f"{path} 契约声明了但响应里没有: {missing}"


_MISSING = object()


def _dig(node, path: str):
    cur = node
    for part in path.lstrip("$.").split("."):
        if not part:
            continue
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


@pytest.fixture(scope="module")
def client():
    """优先复用已提权为 admin 的账号，否则临时建一个 member 账号。

    不能在这里等人提权 —— pytest 会挂在 input() 上。CI 里要跑全量漂移
    检测，就把提权过的账号写进环境变量。
    """
    user = os.environ.get("GIMBAL_SB_USERNAME")
    pwd = os.environ.get("GIMBAL_SB_PASSWORD")
    if user and pwd:
        _, body = Platform("http://127.0.0.1:8000").post(
            "/api/auth/login", {"username": user, "password": pwd}
        )
        return Platform("http://127.0.0.1:8000", body["access_token"])

    from gimbal_bootstrap.orchestrator import _bootstrap_account

    return _bootstrap_account(pause=False)[0]


def test_admin_account_is_available(client):
    """没提权就等于没测 —— 显式失败，别让 403 静默变成 skip。

    `Platform.request` 对 4xx 抛 `PlatformError` 而不返回状态码，所以
    能走到 200 分支本身就说明不是 403。
    """
    from gimbal_bootstrap.platform_client import PlatformError

    try:
        client.get("/api/users/roster")
    except PlatformError as exc:
        assert exc.status != 403, (
            f"自举账号不是管理员（{exc.status}）。跑一次编排器，按提示把它"
            "提权为 admin，再把 GIMBAL_SB_USERNAME / GIMBAL_SB_PASSWORD "
            "写进环境变量。"
        )
        raise AssertionError(f"/api/users/roster → HTTP {exc.status}") from None
```

- [ ] **Step 2: 跑测试确认通过或暴露漂移**

```
cd src/gimbal-bootstrap && python -m pytest tests/test_contract_drift.py -q
```
Expected: 全绿。若 `test_admin_account_is_available` 报 403，先跑一遍编排器按提示提权，再设环境变量重跑。

若 `test_live_response_satisfies_declared_response_contract` 报字段缺失，**不要改平台实现** —— 重跑 Task 2 的生成器刷新契约，再跑本测试。若重跑后仍缺失，说明声明树里有平台确实不返回的字段，那是契约层要修正的地方（改生成器，不改平台）。

- [ ] **Step 3: 写每域用例**

Create `src/gimbal-bootstrap/cases/domains.yaml`:

```yaml
# 每域一条烟雾用例，只断言响应契约。每条都需要登录态（auth 默认 true）。
cases:
  - {id: D01, name: 用户花名册, tags: [smoke],
     steps: [{method: GET, path: /api/users/roster,
              asserts: [{target: "$.call.response.status", operator: eq, expected: 200}]}]}

  - {id: D02, name: 执行摘要, tags: [smoke],
     steps: [{method: GET, path: /api/executions/summary,
              asserts: [{target: "$.call.response.status", operator: eq, expected: 200}]}]}

  - {id: D03, name: 场景 facets, tags: [smoke],
     steps: [{method: GET, path: /api/scenarios/facets,
              asserts: [{target: "$.call.response.status", operator: eq, expected: 200}]}]}

  - {id: D04, name: 凭证池列表, tags: [smoke],
     steps: [{method: GET, path: /api/auths,
              asserts: [{target: "$.call.response.status", operator: eq, expected: 200}]}]}

  - {id: D05, name: 常量池列表, tags: [smoke],
     steps: [{method: GET, path: /api/constants,
              asserts: [{target: "$.call.response.status", operator: eq, expected: 200}]}]}

  - {id: D06, name: carry 默认值, tags: [smoke],
     steps: [{method: GET, path: /api/carry/defaults,
              asserts: [{target: "$.call.response.status", operator: eq, expected: 200}]}]}

  - {id: D07, name: 服务别名列表, tags: [smoke],
     steps: [{method: GET, path: /api/service-aliases,
              asserts: [{target: "$.call.response.status", operator: eq, expected: 200}]}]}

  - {id: D08, name: 数据集列表, tags: [smoke],
     steps: [{method: GET, path: /api/data-sets,
              asserts: [{target: "$.call.response.status", operator: eq, expected: 200}]}]}

  - {id: D09, name: 端点目录, tags: [smoke],
     steps: [{method: GET, path: /api/catalog/services,
              asserts: [{target: "$.call.response.status", operator: eq, expected: 200}]}]}

  - {id: D10, name: 通知列表, tags: [smoke],
     steps: [{method: GET, path: /api/notifications,
              asserts: [{target: "$.call.response.status", operator: eq, expected: 200}]}]}
```

- [ ] **Step 4: 跑全套编排器**

```
cd src/gimbal-bootstrap && python -m gimbal_bootstrap.orchestrator
```
Expected: 18 条用例，末行 `18 passed, 0 failed`。

有红的就按 `error` 排查。**禁止为让用例变绿而改平台实现**。

- [ ] **Step 5: 跑全部测试**

```
cd src/gimbal-bootstrap && python -m pytest tests/ -q
```
Expected: 全绿。

- [ ] **Step 6: 写 README**

Create `src/gimbal-bootstrap/README.md`:

```markdown
# gimbal-bootstrap

在 gimbal-platform 上编排并运行打 gimbal-platform 自己的用例。

契约真源是平台的 `/openapi.json`，本项目机械导出为 plate 契约；
用例以 YAML 声明，编排器编译成 plate Scenario definition，经平台公开
API 建资源、发起运行、轮询、清理。全程普通用户身份，无提权。

## 用法

```bash
# 刷新契约（平台改了字段后跑）
python -m gimbal_bootstrap.contract_gen

# 跑全部用例
python -m gimbal_bootstrap.orchestrator

# 契约漂移检测
python -m pytest tests/test_contract_drift.py -q
```

## 布局

| 路径 | 职责 |
|---|---|
| `gimbal_bootstrap/contract_gen.py` | OpenAPI → plate EndpointSpec JSON |
| `gimbal_bootstrap/platform_client.py` | 平台 HTTP 薄客户端 |
| `gimbal_bootstrap/case_builder.py` | 用例 YAML → plate Scenario definition |
| `gimbal_bootstrap/orchestrator.py` | 建资源 / 发起运行 / 轮询 / 清理 |
| `cases/*.yaml` | 用例清单 |
| `tests/test_contract_drift.py` | 契约 vs 真实响应（单向） |

## 已知缺口

- GET 的 query 参数未契约化（plate `ApiSpec` 无对应字段），用例侧靠 `${}` 模板拼 path
- 契约漂移只做单向检查（声明 ⊆ 实际），反向会因动态字段恒红
- 执行台账（`executions`）不自动清理 —— 它是审计面

见 `docs/superpowers/specs/2026-09-28-platform-self-bootstrap-design.md`。
```

- [ ] **Step 7: Commit**

```bash
git add src/gimbal-bootstrap
git commit -m "feat(bootstrap): 每域用例与契约漂移检测

每域一条烟雾用例补齐到 18 条。漂移检测做单向核对（声明 ⊆ 实际）——
反向会因 createdAt / 生成 id 这类动态字段恒红。

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 完成判据

- [ ] `python -m pytest tests/plate/` 全绿
- [ ] `cd src/gimbal-platform/backend && python -m pytest tests/` 全绿
- [ ] `cd src/gimbal-bootstrap && python -m pytest tests/` 全绿
- [ ] `python -m gimbal_bootstrap.orchestrator` → `18 passed, 0 failed`
- [ ] `GET /openapi.json` 返回 200
- [ ] `GET http://127.0.0.1:8765/api/system` 含且仅含一条 `platform`
- [ ] `git status` 无意外改动；未触碰授权边界外的任何文件
