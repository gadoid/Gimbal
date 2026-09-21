"""M2 元数据断言测试(PG迁移方案 §2.1 时区结构修法的防回退门禁)。

遍历 ``Base.metadata`` 全部列,钉两条不变量:
1. **所有 DateTime 列 timezone=True**(timestamptz;SQLite 方言虽不存
   offset,列声明仍统一,PG 侧才生效);
2. **func.now() 的 server_default 只出现在 timezone=True 列上** ——
   timestamptz 下 PG 的 now() 存绝对时间(不随会话时区漂);naive 列上
   的 DB 生成时间戳才是漂移源(catalog_versions.synced_at 曾是唯一破口,
   §8 风险 2)。

防的是以后新加的列,比一次性人工扫描值钱。
"""
from __future__ import annotations

from sqlalchemy import DateTime, schema

from app.core.db import Base
from app import models  # noqa: F401  注册所有模型


def _all_columns():
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            yield table.name, col


def test_all_datetime_columns_are_timezone_aware():
    offenders = [
        f"{t}.{c.name}" for t, c in _all_columns()
        if isinstance(c.type, DateTime) and not c.type.timezone
    ]
    assert not offenders, (
        f"存在不带 timezone=True 的 DateTime 列(会随会话时区漂): {offenders}"
    )


def test_func_now_defaults_only_on_tz_aware_columns():
    offenders = []
    for t, c in _all_columns():
        default = c.server_default
        if default is None:
            continue
        arg = getattr(default, "arg", None)
        is_now = isinstance(arg, schema.FetchedValue) or (
            callable(getattr(arg, "name", None))
        )
        if isinstance(arg, str):
            is_now = "now()" in arg.lower()
        elif hasattr(arg, "name") and not callable(arg.name):
            is_now = str(arg.name).lower() in {"now", "current_timestamp"}
        else:
            is_now = False
        if is_now and (not isinstance(c.type, DateTime) or not c.type.timezone):
            offenders.append(f"{t}.{c.name}")
    assert not offenders, (
        f"naive 列上挂了 DB 生成时间默认值(timestamptz 外的 now() 才漂): {offenders}"
    )


def test_json_columns_render_jsonb_on_pg():
    """JSON 一律 JSONB(§0 原则 5):所有 JSON 列在 PG 方言编译为 JSONB。"""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.types import JSON

    offenders = []
    for t, c in _all_columns():
        if isinstance(c.type, JSON):
            rendered = c.type.compile(dialect=postgresql.dialect())
            if rendered.upper() != "JSONB":
                offenders.append(f"{t}.{c.name}({rendered})")
    assert not offenders, f"存在 PG 侧非 JSONB 的 JSON 列: {offenders}"
