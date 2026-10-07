"""G1:方言自描述视图 —— type dim 的索引(type + schema 视图)。

各块的 JSON Schema(pydantic model_json_schema)、片段 kind 槽位表、
锚点语法、id 规则;Agent 编写方由此获得完整方言契约,不必读代码。
"""
from __future__ import annotations

from typing import Any

from .models import EndpointSpec, Frontmatter, Statement, Term
from .validation import load_types

# 片段 kind 槽位表(6.3,与 validation._REQUIRED_SLOTS/_SLOT_KINDS 同源)
KIND_SLOTS: dict[str, dict[str, Any]] = {
    "mention": {"required": ["subject"], "optional": []},
    "define": {"required": ["subject"], "optional": []},
    "rule": {"required": ["about"], "optional": ["before", "violation"]},
    "outcome": {"required": ["cap"],
                "optional": ["outcome", "when", "target"],
                "at_least_one": ["outcome", "target"]},
    "transition": {"required": ["cap", "from", "to"], "optional": []},
    "step": {"required": ["cap", "order"], "optional": ["branch_on"]},
    "note": {"required": [], "optional": ["terms"]},
}
ANCHOR_GRAMMARS = {
    "section": "标题路径(A2 / A2.1)",
    "table_column": "表.列[=值]",
    "spec_path": "<endpoint_id> <JSONPath>[@outcome][=value]",
    "ui": "页面 / 区块 / 控件",
}
ID_RULES = {
    "endpoint": "^[a-z][a-z0-9_.-]{1,63}$ 且以 system 为前缀",
    "term": "entity|attr|value|cap|outcome : 段式(6.4,固定深度)",
    "statement": "编写方分配;格式约定经本视图暴露(8w)",
}


class TypeCatalogIndex:
    """type dim 索引:类型模板条目;/full 带 dialect schema。"""

    registry: Any

    def __init__(self, registry: Any = None) -> None:
        self.registry = registry

    def list_global(self, *, filters: dict[str, Any] | None = None):
        return [{"id": k, **{kk: vv for kk, vv in v.items() if kk != "id"}}
                for k, v in load_types().items()]

    def list_for_system(self, system: str, *, filters=None):
        return self.list_global()

    def get(self, item_id: str):
        t = load_types().get(item_id)
        return {"id": item_id, **t} if t else None

    def to_view(self, item):
        return item

    def full_schema(self) -> dict[str, Any]:
        """方言自描述(G1 全量):块 JSON Schema + 槽位表 + 锚点 + id 规则。"""
        return {
            "blocks": {
                "endpoint": EndpointSpec.model_json_schema(),
                "statement": Statement.model_json_schema(),
                "term": Term.model_json_schema(),
                "frontmatter": Frontmatter.model_json_schema(),
            },
            "statement_kind_slots": KIND_SLOTS,
            "anchor_grammars": ANCHOR_GRAMMARS,
            "id_rules": ID_RULES,
            "envelope": {"review": ["draft", "reviewed"],
                         "default": "draft", "written_only_when": "reviewed"},
            "canonical_form": {
                "key_order": "M2 模型定义序",
                "exclude_defaults": True,
                "discriminator_always_serialized": True,
            },
        }
