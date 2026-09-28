"""OpenAPI → plate EndpointSpec JSON。

契约的唯一真源是 gimbal-platform 的 /openapi.json，人工不写任何字段。
产物落在 plate 的 systems/platform/endpoints.json —— plate 只负责加载，
不认识本模块。生成器因此放在 gimbal-bootstrap 而不是 plate 里。
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
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
BACKEND_DIR = Path(__file__).resolve().parents[2] / "gimbal-platform/backend"


def fetch_openapi(
    base_url: str = PLATFORM_BASE_URL, *, allow_inprocess_fallback: bool = False
) -> dict[str, Any]:
    """优先走 HTTP；后端跑着旧代码导致 500 时可回落进程内生成。

    回落的意义是免掉"改了后端必须先重启才能刷新契约"这个耦合 —— 进程内
    拿的一定是当前 checkout 的代码，HTTP 拿的可能是常驻进程的旧版本。
    """
    url = f"{base_url.rstrip('/')}/openapi.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.load(resp)
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        if not allow_inprocess_fallback:
            raise
        import sys

        sys.path.insert(0, str(BACKEND_DIR))
        from app.main import app  # noqa: PLC0415 — 回落路径才导入

        return app.openapi()


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


def _union(node: dict, schemas: dict, warnings: list[str] | None) -> dict:
    """把顶层 anyOf/oneOf 折成一个合成 object schema（各分支 properties 的并集）。

    平台的列表端点按 query 参数返回两种不同形状（`GET /api/scenarios` →
    `anyOf[ScenarioListOut, ScenarioOptionsOut]`），而 plate 的
    `responses: dict[int, ResponseSpec]` 一个状态码只能挂一份声明。取并集
    得到的超集契约对两条路都成立，正好够单向漂移检测用。
    """
    branches = [b for b in node.get("anyOf", []) + node.get("oneOf", [])]
    merged: dict[str, Any] = {"type": "object", "properties": {}}
    for branch in branches:
        resolved = _resolve(branch, schemas)
        if "properties" not in resolved:
            continue
        for name, prop in resolved["properties"].items():
            existing = merged["properties"].get(name)
            if existing is None:
                merged["properties"][name] = prop
            elif existing != prop and warnings is not None:
                warnings.append(
                    f"{name} 在 union 各分支类型不一致，保留首个声明"
                )
    return merged


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
    if "anyOf" in n or "oneOf" in n:
        n = _union(n, schemas, warnings)
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

    openapi = fetch_openapi(args.base_url, allow_inprocess_fallback=True)
    specs, warnings = build_specs(openapi)
    write_json(specs, Path(args.out), args.base_url + "/openapi.json")

    print(f"generated {len(specs)} endpoints -> {args.out}")
    for w in warnings:
        print("WARN:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
