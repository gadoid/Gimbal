"""外部接口登记目录 · 服务层(外部接口登记批 X1,设计 v1.0 §4)。

职责:
* CRUD 编排(kind=external 前置校验、别名内唯一);
* ``jsonschema_to_declarations`` —— 标准 JSON Schema → plate /full 同形
  declarations 树(表单数据源的单一转换点,不双写);
* OpenAPI 导入(演练/apply 两段,迁移纪律:默认演练、单事务、幂等 ——
  同名条目跳过并报告)。

校验器口径(与转换器同一套类型映射,手写子集、不引运行时依赖):
object/string/number/integer/boolean/array + required + properties 嵌套;
超集 schema 字段(如 format/pattern)忽略 —— 告警语义(D2 拍板),
不追求严格 JSON Schema 校验。
"""
from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.external_endpoint import ExternalEndpoint
from ..models.service_alias import ServiceAlias

AUTH_VALUES = ("none", "bearer", "basic", "cookie", "custom")
_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "DELETE")

# JSON Schema type → 契约展示 type(转换器与校验器共用)
_TYPE_MAP = {
    "string": "string",
    "number": "number",
    "integer": "number",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}


# ─── JSON Schema → declarations 树(单一转换点)────────────────────

def _ensure_order(schema: dict | None) -> dict | None:
    """2-4(2026-10-13):顺序显式承载 —— 每个 object 层写 ``x-order``
    (本层 properties 的键序,过滤只剩实际存在的键)。

    JSONB 会按键长/字节序重排对象键;表单 declarations 的字段顺序源
    自 properties 键序。写入前统一盖章,读取侧(_props_to_nodes)按
    x-order 排序 —— 顺序不再依赖存储层行为;列本身也回 json(0023)
    保插入序兜底。
    """
    if not isinstance(schema, dict):
        return schema
    props = schema.get("properties")
    if isinstance(props, dict) and props:
        order = [k for k in props if isinstance(k, str)]
        if order:
            schema["x-order"] = order
        for spec in props.values():
            if isinstance(spec, dict):
                _ensure_order(spec)
    # array items 层同为「键序敏感面」,一并盖章(2-3:顶层之外的嵌套
    # object 经上面 spec 递归已覆盖,items 是独立入口)
    items = schema.get("items")
    if isinstance(items, dict):
        _ensure_order(items)
    return schema


def _x_order_of(spec: dict) -> list | None:
    # 2-3:取层内 x-order(写侧 _ensure_order 每层盖章);非法形状按缺省
    order = spec.get("x-order")
    return order if isinstance(order, list) else None


def jsonschema_to_declarations(schema: dict | None) -> list[dict]:
    """标准 JSON Schema(object 根)→ plate 目录树同形 declarations。

    * ``properties.x`` → ``{name, path, type, state: form, required,
      children?}``;嵌套 object 递归挂 children(与 plate 目录树同形,
      编排器表单零改造消费);
    * 无 schema / 非 object 根 / 无 properties → ``[]``(表单自由编辑,
      与现状同,不炸);
    * ``required`` 只作用于本层属性名。
    """
    if not isinstance(schema, dict):
        return []
    if schema.get("type") != "object":
        return []
    props = schema.get("properties")
    if not isinstance(props, dict) or not props:
        return []
    required = set(schema.get("required") or [])
    return _props_to_nodes(props, required, prefix="$", x_order=_x_order_of(schema))


def _props_to_nodes(props: dict, required: set, prefix: str,
                    x_order: list | None = None) -> list[dict]:
    # 2-4:x-order 显式序优先(写侧 _ensure_order 盖章);缺省按插入序
    # (json 列保序;兼容未盖章的历史/手工载荷)
    names = [n for n in (x_order or []) if n in props]
    names += [n for n in props if n not in names]
    nodes: list[dict] = []
    for name in names:
        spec = props[name]
        if not isinstance(spec, dict):
            continue
        path = f"{prefix}.{name}"
        js_type = spec.get("type")
        node: dict = {
            "name": str(name),
            "path": path,
            "type": _TYPE_MAP.get(str(js_type), "string"),
            "state": "form",
            "required": str(name) in required,
        }
        if js_type == "object":
            # 2-3:子层 x-order 一并传入(此前只顶层生效,嵌套层顺序
            # 仍依赖存储层保序,json 列兜底在,但前提不成立)
            children = _props_to_nodes(
                spec.get("properties") or {},
                set(spec.get("required") or []),
                prefix=path,
                x_order=_x_order_of(spec),
            )
            if children:
                node["children"] = children
        elif js_type == "array" and isinstance(spec.get("items"), dict):
            items = spec["items"]
            if items.get("type") == "object" and items.get("properties"):
                # 数组元素结构挂 children(path 带 [0] 示意)
                node["children"] = _props_to_nodes(
                    items.get("properties") or {},
                    set(items.get("required") or []),
                    prefix=f"{path}[0]",
                    x_order=_x_order_of(items),
                )
        nodes.append(node)
    return nodes


# ─── 保存校验(D2 拍板:告警不阻塞)────────────────────────────────

def check_body_against_schema(
    body: Any, schema: dict | None,
) -> list[str]:
    """body vs JSON Schema 子集比对 → 告警清单(调用侧展示,不阻塞)。

    只报三类:多余字段 / 缺必填 / 类型不符;嵌套 object 递归。
    body 非 dict / 无 schema → 空清单(无约束面)。
    """
    if not isinstance(schema, dict) or not isinstance(body, dict):
        return []
    if schema.get("type") != "object":
        return []
    return _check_obj(body, schema, path="body")


def _check_obj(body: dict, schema: dict, path: str) -> list[str]:
    warns: list[str] = []
    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        return warns
    required = set(schema.get("required") or [])
    for name in required:
        if name not in body:
            warns.append(f"{path}.{name} 缺必填字段(目录登记 required)")
    for name, value in body.items():
        spec = props.get(name)
        child = f"{path}.{name}"
        if spec is None:
            warns.append(f"{child} 不在目录登记的 schema 中(多余字段)")
            continue
        warns.extend(_check_value(value, spec, child))
    return warns


def _check_value(value: Any, spec: dict, path: str) -> list[str]:
    js_type = spec.get("type")
    if not js_type:
        return []
    ok = _value_matches(value, str(js_type))
    if not ok:
        return [f"{path} 类型不符:目录登记 {js_type}"]
    if js_type == "object" and isinstance(value, dict):
        return _check_obj(value, spec, path)
    if js_type == "array" and isinstance(value, list) and isinstance(
            spec.get("items"), dict):
        warns: list[str] = []
        for i, item in enumerate(value):
            warns.extend(_check_value(item, spec["items"], f"{path}[{i}]"))
        return warns
    return []


def _value_matches(value: Any, js_type: str) -> bool:
    import datetime as _dt
    if js_type == "string":
        return isinstance(value, str)
    if js_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if js_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if js_type == "boolean":
        return isinstance(value, bool)
    if js_type == "array":
        return isinstance(value, list)
    if js_type == "object":
        return isinstance(value, dict)
    return True     # 未知类型不比(告警语义,宁可漏报不误报)


# ─── CRUD 编排 ─────────────────────────────────────────────────────

async def _require_external_alias(
    db: AsyncSession, alias_name: str,
) -> ServiceAlias:
    row = await db.get(ServiceAlias, alias_name)
    if row is None:
        raise ValueError(f"alias_not_found: {alias_name}")
    if (row.kind or "plate") != "external":
        raise ValueError(
            f"alias_not_external: {alias_name}(kind={row.kind or 'plate'};"
            "外部接口只能登记在 kind=external 的别名下)")
    return row


def contract_view(row: ExternalEndpoint) -> dict:
    """详情/契约视图(设计 §4.2):与 plate /full 的 item 同形。"""
    return {
        "id": f"ext:{row.alias_name}.{row.name}",
        "title": row.title or row.name,
        "method": row.method,
        "path": row.path,
        "auth": row.auth,
        "request": {"declarations": jsonschema_to_declarations(
            row.request_schema)},
    }


def _to_wire(row: ExternalEndpoint) -> dict:
    return {
        "id": row.id,
        "aliasName": row.alias_name,
        "name": row.name,
        "title": row.title,
        "method": row.method,
        "path": row.path,
        "requestSchema": row.request_schema,
        "auth": row.auth,
        "notes": row.notes,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


async def list_endpoints(
    db: AsyncSession, *, alias: str | None = None, q: str | None = None,
) -> list[dict]:
    stmt = select(ExternalEndpoint).order_by(
        ExternalEndpoint.alias_name, ExternalEndpoint.name)
    if alias:
        stmt = stmt.where(ExternalEndpoint.alias_name == alias)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((ExternalEndpoint.name.ilike(like))
                          | (ExternalEndpoint.title.ilike(like))
                          | (ExternalEndpoint.path.ilike(like)))
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_wire(r) for r in rows]


async def get_endpoint_db(
    db: AsyncSession, alias: str, name: str,
) -> ExternalEndpoint | None:
    """ORM 行读取(代理路由就地派生契约视图用)。"""
    return (await db.execute(select(ExternalEndpoint).where(
        ExternalEndpoint.alias_name == alias,
        ExternalEndpoint.name == name,
    ))).scalar_one_or_none()


async def get_endpoint(
    db: AsyncSession, alias: str, name: str,
) -> dict | None:
    row = (await db.execute(select(ExternalEndpoint).where(
        ExternalEndpoint.alias_name == alias,
        ExternalEndpoint.name == name,
    ))).scalar_one_or_none()
    if row is None:
        return None
    out = _to_wire(row)
    out["contract"] = contract_view(row)
    return out


def _validate_payload(
    *, name: str, method: str, path: str, request_schema: dict | None,
    auth: str,
) -> None:
    if not name or ":" in name or "." in name:
        raise ValueError(
            "invalid_name: 接口名非空且不含 . 与 :(锚点段保留字)")
    if method.upper() not in _METHODS:
        raise ValueError(f"invalid_method: {method}")
    if not path.startswith("/"):
        raise ValueError("invalid_path: path 须以 / 起头(URL 模式)")
    if request_schema is not None and not isinstance(request_schema, dict):
        raise ValueError("invalid_schema: requestSchema 须为 JSON 对象")
    if auth not in AUTH_VALUES:
        raise ValueError(f"invalid_auth: {auth} ∈ {AUTH_VALUES}")


async def create_endpoint(
    db: AsyncSession, *, alias_name: str, name: str, title: str = "",
    method: str = "GET", path: str = "/", request_schema: dict | None = None,
    auth: str = "none", notes: str | None = None,
) -> dict:
    await _require_external_alias(db, alias_name)
    _validate_payload(name=name, method=method, path=path,
                      request_schema=request_schema, auth=auth)
    dup = (await db.execute(select(ExternalEndpoint.id).where(
        ExternalEndpoint.alias_name == alias_name,
        ExternalEndpoint.name == name,
    ))).scalar_one_or_none()
    if dup is not None:
        raise ValueError(f"name_conflict: {alias_name} 下已登记 {name}")
    row = ExternalEndpoint(
        alias_name=alias_name, name=name, title=title or name,
        method=method.upper(), path=path,
        request_schema=_ensure_order(request_schema),   # 2-4:盖章 x-order
        auth=auth, notes=notes,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_wire(row)


async def update_endpoint(
    db: AsyncSession, *, alias_name: str, name: str,
    title: str | None = None, method: str | None = None,
    path: str | None = None, request_schema: dict | None = None,
    auth: str | None = None, notes: str | None = None,
) -> dict:
    await _require_external_alias(db, alias_name)
    row = (await db.execute(select(ExternalEndpoint).where(
        ExternalEndpoint.alias_name == alias_name,
        ExternalEndpoint.name == name,
    ))).scalar_one_or_none()
    if row is None:
        raise ValueError(f"not_found: {alias_name}.{name}")
    if title is not None:
        row.title = title
    if method is not None:
        if method.upper() not in _METHODS:
            raise ValueError(f"invalid_method: {method}")
        row.method = method.upper()
    if path is not None:
        if not path.startswith("/"):
            raise ValueError("invalid_path: path 须以 / 起头")
        row.path = path
    if request_schema is not None:
        if not isinstance(request_schema, dict):
            raise ValueError("invalid_schema: requestSchema 须为 JSON 对象")
        row.request_schema = _ensure_order(request_schema)  # 2-4:盖章
    if auth is not None:
        if auth not in AUTH_VALUES:
            raise ValueError(f"invalid_auth: {auth}")
        row.auth = auth
    if notes is not None:
        row.notes = notes
    await db.commit()
    await db.refresh(row)
    return _to_wire(row)


async def delete_endpoint(
    db: AsyncSession, *, alias_name: str, name: str,
) -> None:
    row = (await db.execute(select(ExternalEndpoint).where(
        ExternalEndpoint.alias_name == alias_name,
        ExternalEndpoint.name == name,
    ))).scalar_one_or_none()
    if row is None:
        raise ValueError(f"not_found: {alias_name}.{name}")
    await db.delete(row)
    await db.commit()


# ─── OpenAPI 导入(演练/apply 两段)────────────────────────────────

def parse_openapi(doc: dict) -> tuple[list[dict], str | None]:
    """OpenAPI 文档 → (条目清单, servers[0].url)。

    条目 = {name, title, method, path, request_schema};name 由 path 派生
    (去 / 与 {},以 - 连接;与既有条目同名由导入器跳过并报告)。
    requestBody 取首个 JSON content 的 schema($ref 不解引用 —— 登记
    面收内联子集,引用式组件留手工展开,导入报告列出跳过原因)。
    """
    paths = doc.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise ValueError("invalid_openapi: 文档无 paths")
    servers = doc.get("servers") or []
    base_url = None
    if isinstance(servers, list) and servers and isinstance(servers[0], dict):
        base_url = servers[0].get("url") or None
    entries: list[dict] = []
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        name = _name_from_path(str(path))
        for method, op in item.items():
            m = str(method).lower()
            if m not in ("get", "post", "put", "patch", "delete",
                         "head", "options"):
                continue
            if not isinstance(op, dict):
                continue
            schema = _body_schema_of(op)
            title = ""
            if isinstance(op.get("summary"), str):
                title = op["summary"]
            elif isinstance(op.get("description"), str):
                title = op["description"][:64]
            entries.append({
                "name": name if m == "get" else f"{name}-{m}",
                "title": title or f"{m.upper()} {path}",
                "method": m.upper(),
                "path": str(path),
                "request_schema": schema,
            })
    if not entries:
        raise ValueError("invalid_openapi: paths 内无可导入的 method")
    return entries, base_url


def _name_from_path(path: str) -> str:
    """path → 接口名(仅清锚点保留字 ``.`` / ``:``;下划线原样保留)。"""
    segs = [s.strip("{}").replace(".", "-").replace(":", "-")
            for s in path.strip("/").split("/") if s]
    return ("-".join(segs) or "root")[:120]


def _body_schema_of(op: dict) -> dict | None:
    rb = op.get("requestBody")
    if not isinstance(rb, dict):
        return None
    content = rb.get("content")
    if not isinstance(content, dict):
        return None
    for ctype, media in content.items():
        if not isinstance(media, dict):
            continue
        if "json" not in ctype:
            continue
        schema = media.get("schema")
        if isinstance(schema, dict) and "$ref" not in schema:
            return copy.deepcopy(schema)
    return None


async def import_openapi(
    db: AsyncSession, *, alias_name: str, doc: dict, apply: bool = False,
) -> dict:
    """导入(默认演练):同名跳过 + 报告;apply = 单事务落库。

    返回 {total, created, skipped, base_url, applied, items}。
    """
    await _require_external_alias(db, alias_name)
    entries, base_url = parse_openapi(doc)
    existing = {
        r.name for r in (await db.execute(
            select(ExternalEndpoint).where(
                ExternalEndpoint.alias_name == alias_name))
        ).scalars().all()}
    report_items: list[dict] = []
    created = skipped = 0
    for e in entries:
        if e["name"] in existing:
            skipped += 1
            report_items.append(
                {"name": e["name"], "action": "skip",
                 "reason": "name_conflict(已登记,跳过)"})
            continue
        created += 1
        report_items.append(
            {"name": e["name"], "action": "create",
             "method": e["method"], "path": e["path"]})
        if apply:
            db.add(ExternalEndpoint(
                alias_name=alias_name, name=e["name"], title=e["title"],
                method=e["method"], path=e["path"],
                request_schema=_ensure_order(e["request_schema"]),  # 2-4
            ))
    if apply:
        # 别名 base_url 缺失且文档带 servers.url → 补默认层(登记增强)
        if base_url:
            alias_row = await db.get(ServiceAlias, alias_name)
            if alias_row is not None and not (alias_row.base_url or "").strip():
                alias_row.base_url = base_url.rstrip("/")
        await db.commit()
    return {"total": len(entries), "created": created, "skipped": skipped,
            "base_url": base_url, "applied": apply, "items": report_items}
