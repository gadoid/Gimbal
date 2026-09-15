"""S3:语义富化 —— zh 合并(rule>column>derived)/type 映射/默认值/enum(rule)。

Enum 类抽取仅作报告候选(v1 不自动挂 enum,scope 控制);字段集 =
活跃规则键 ∪ 被注释规则键 ∪ 读取键。

节点形状 probe 实录(task-6,fixture OrderEnum):
declaration_list 子序 = [const_declaration, comment, ...] 相邻命名兄弟,
中间无匿名节点(不同于 property 数组里的 ','),children[i+1] 直接命中
同行行尾 comment;const_element 是 const_declaration 直接子节点
(const/; 为匿名),其子 = name + '='(匿名)+ integer|string。
"""
from __future__ import annotations

from pathlib import Path

from .php_ast import ParsedFile, load, text_of, classes, is_string_literal
from .ir import ActionIR, FieldIR, RuleEntry
from .schema_source import ColumnCatalog

_INT_TYPES = ("int", "bigint", "tinyint", "smallint", "mediumint")
_NUM_TYPES = ("decimal", "float", "double")


def load_enums(app_root: Path) -> dict[str, list[tuple[str, str]]]:
    """Common/Enum/*.class.php:常量名 → [(值, 中文)](报告候选用)。"""
    out: dict[str, list[tuple[str, str]]] = {}
    for f in sorted((app_root / "Common" / "Enum").glob("*.class.php")):
        pf = load(f)
        for _n, _c, decl in classes(pf):
            children = list(decl.children)
            for i, node in enumerate(children):
                if node.type != "const_declaration":
                    continue
                for el in node.children:
                    if el.type != "const_element":
                        continue
                    name = next((c for c in el.children if c.type == "name"), None)
                    if name is None:
                        continue
                    val_n = next((c for c in el.children
                                  if c.type == "integer" or is_string_literal(c)),
                                 None)
                    nxt = children[i + 1] if i + 1 < len(children) else None
                    zh = ""
                    if nxt is not None and nxt.type == "comment" \
                            and nxt.start_point[0] == node.start_point[0]:
                        zh = text_of(pf, nxt).lstrip("/ ").strip()
                    if val_n is not None:
                        out.setdefault(text_of(pf, name), []).append(
                            (text_of(pf, val_n).strip("'\""), zh))
    return out


def _type_of(col_type: str) -> str:
    base = col_type.split("(")[0].lower()
    if base in _INT_TYPES:
        return "integer"
    if base in _NUM_TYPES:
        return "number"
    return "string"


def _rule_index(rules: list[RuleEntry]) -> dict[str, RuleEntry]:
    out: dict[str, RuleEntry] = {}
    for r in rules:                     # 活跃行优先(后写覆盖时保活跃)
        if r.active:
            out[r.key] = r
    for r in rules:
        out.setdefault(r.key, r)
    return out


def enrich(actions: list[ActionIR], catalog: ColumnCatalog
           ) -> dict[str, list[FieldIR]]:
    all_fields: dict[str, list[FieldIR]] = {}
    for act in actions:
        ridx = _rule_index(act.rules)
        keys: list[str] = []
        for k in list(ridx) + list(act.reads):
            if k not in keys:
                keys.append(k)
        fields: list[FieldIR] = []
        for key in keys:
            rule = ridx.get(key)
            read = act.reads.get(key)
            cols = catalog.by_name.get(key, [])
            f = FieldIR(
                key=key,
                read=read is not None,
                # 校验派生只认活跃行;被注释行仅贡献 zh(保留注释行的目的)
                required=bool(rule and rule.active and rule.required()),
                must_include=bool(rule and rule.active
                                  and (rule.required() or rule.must_include())),
                zh=rule.zh if rule and rule.zh else "",
                zh_source="rule" if rule and rule.zh else "",
                enum_values=rule.enum_values() if rule and rule.active else None,
                default=read.default if read and read.default is not None else None,
                col_comment=cols[0].comment if cols else "",
                col_type=cols[0].col_type if cols else "",
                tables=[c.table for c in cols],
            )
            if not f.zh and cols and cols[0].comment:
                f.zh, f.zh_source = cols[0].comment, "column"
            if not f.zh and key.endswith("_name"):
                base_key = key[:-5]           # customer_name → customer
                for cand in (base_key, base_key + "_id"):
                    base = ridx.get(cand)
                    if base and base.zh:
                        f.zh, f.zh_source = base.zh + "名称", "derived"
                        break
            f.type_ = _type_of(f.col_type) if f.col_type else "string"
            if f.default is None and cols and cols[0].default:
                f.default = cols[0].default
            fields.append(f)
        all_fields[act.id] = fields
    return all_fields
