"""JSON 路径表达式的双方言编译(PG迁移方案 §2.2 方言段)。

composer_scenarios 的七个 STORED 生成列在两个方言上各用原生 JSON 语法:
* PG:``(payload->'definition'->'meta'->>'name')`` 文本 / ``->`` JSON
* SQLite:``json_extract(payload, '$.definition.meta.name')``

SQLAlchemy 的 ``Computed`` 只接受一个表达式,方言变体经由自定义
``FunctionElement`` + ``@compiles`` 钩子实现 —— 模型声明一份,渲染按
引擎方言走。M0-4 已实测双方言 STORED 生成列可用(进两案、出一案全过)。
路径段必须用 ``literal()`` 传入:生成列表达式进 DDL,绑定参数在那里
渲染不出来。
"""
from __future__ import annotations

from sqlalchemy import Integer, literal
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import FunctionElement
from sqlalchemy.types import JSON, Text


class json_path_text(FunctionElement):
    """按路径取文本(标量抽出:name/description/module/author/priority)。"""

    type = Text()
    name = "json_path_text"
    inherit_cache = True


class json_path_json(FunctionElement):
    """按路径取 JSON 值(数组/对象抽出:system/tags)。"""

    type = JSON()
    name = "json_path_json"
    inherit_cache = True


def _col_name(clause) -> str:
    """裸列名 —— 生成列表达式里禁止表限定(SQLite 报
    "the . operator prohibited in generated columns"),两方言统一裸名。"""
    return getattr(clause, "name", None) or str(clause)


def _keys(element) -> list[str]:
    """路径段:literal() 的绑定值直接取 ``.value`` 自行拼单引号 ——
    交给编译器渲染会出双引号标识符/绑定占位,DDL 里都不可用。"""
    return [str(c.value) for c in list(element.clauses)[1:]]


@compiles(json_path_text, "postgresql")
def _text_pg(element, compiler, **kw):
    col = _col_name(list(element.clauses)[0])
    keys = _keys(element)
    head = "->".join([f"'{k}'" for k in keys[:-1]])
    last = f"'{keys[-1]}'"
    # 文本抽取:路径中段用 ->,末段用 ->>(json → text)
    return f"({col}->{head}->>{last})" if head else f"({col}->>{last})"


@compiles(json_path_text, "sqlite")
def _text_sqlite(element, compiler, **kw):
    col = _col_name(list(element.clauses)[0])
    path = ".".join(_keys(element))
    return f"json_extract({col}, '$.{path}')"


@compiles(json_path_json, "postgresql")
def _json_pg(element, compiler, **kw):
    col = _col_name(list(element.clauses)[0])
    path = "->".join(f"'{k}'" for k in _keys(element))
    return f"({col}->{path})"


@compiles(json_path_json, "sqlite")
def _json_sqlite(element, compiler, **kw):
    col = _col_name(list(element.clauses)[0])
    path = ".".join(_keys(element))
    return f"json_extract({col}, '$.{path}')"


class json_array_len(FunctionElement):
    """JSON 数组长度(composer_data_sets.row_count 生成列,G3)。

    PG 侧带 jsonb_typeof 守卫:rows 恒为数组,守卫只防脏数据把写入
    打炸(SQLite 的 json_array_length 对非数组本就返回 0)。
    """

    type = Integer()
    name = "json_array_len"
    inherit_cache = True


@compiles(json_array_len, "postgresql")
def _arrlen_pg(element, compiler, **kw):
    col = _col_name(list(element.clauses)[0])
    return (f"(CASE WHEN jsonb_typeof({col}) = 'array' "
            f"THEN jsonb_array_length({col}) ELSE 0 END)")


@compiles(json_array_len, "sqlite")
def _arrlen_sqlite(element, compiler, **kw):
    col = _col_name(list(element.clauses)[0])
    return f"json_array_length({col})"


__all__ = ["json_path_text", "json_path_json", "json_array_len", "literal"]
