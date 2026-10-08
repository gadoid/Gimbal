"""dialect.renderer —— M2 → Markdown 规范形（批次 A1，第 5 节）。

规范形规则（已定）：
- 键序 = M2 模型字段定义序（``model_dump`` 保序，``sort_keys=False``）；
- 排除等于默认值的字段（与 hash 的规范序列化同一纪律，修订九①）；
- 不含注释；块信封 ``review`` 仅在 ``reviewed`` 时写出（draft 为缺省）；
- 只替换结构块内部，不动块外散文（Prose 节点原样回写）。

「无损往返」= 语义等价而非字节等价（已定）：人工手写文件一经 plate 回写
即转为规范形；``render(parse(render(parse(x))))`` 字节稳定（幂等）。
"""
from __future__ import annotations

from typing import Any

import yaml

from .models import Frontmatter
from .parser import Block, Deliverable, Prose

_YAML_KWARGS: dict[str, Any] = {
    "sort_keys": False,
    "allow_unicode": True,
    "default_flow_style": False,
    "width": 4096,
}


def _is_ambiguous(value: str) -> bool:
    """字符串标量在 1.1 或 1.2 core 任一口径下会被读成非本串（评审 P0-9）。

    解析口径已是 1.2 core（修订十一，parser._core_implicit）；渲染的规范形
    仍须对**两个口径**都无歧义——手写文件可能被任何 YAML 工具读取，
    规范形是跨消费方的兼容面。两口径都按解析器真跑一遍（而非正则近似）：
    - 1.1 误读（PyYAML 缺省）：'01'→1、'on'→True、'12:30'→750、'null'→None；
    - 1.2 core 误读：'08'/'1e3'/'0o10'→数字。
    """
    from .parser import core_scalar
    stripped = value.strip()
    if not stripped:
        return False
    try:
        resolved_12 = core_scalar(stripped)
        resolved_11 = yaml.safe_load(stripped)
    except Exception:  # noqa: BLE001 — 解析失败 = 无歧义
        return False
    for resolved in (resolved_11, resolved_12):
        if not isinstance(resolved, str) or resolved != value:
            return True
    return False


class _QuotingDumper(yaml.SafeDumper):
    """字符串歧义标量双引号写出(其余走 SafeDumper 默认)。"""


def _str_representer(dumper, value):
    if _is_ambiguous(value):
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str", value, style='"')
    return dumper.represent_scalar("tag:yaml.org,2002:str", value)


_QuotingDumper.add_representer(str, _str_representer)

# 渲染时排除的派生字段（解析期由块后散文派生，不写入块内——6.3）：
# ``Statement.text`` 仍参与 canonical/hash（它是对象内容），只不进块体。
_RENDER_EXCLUDE: dict[str, set[str]] = {"statement": {"text"}}


def _model_to_payload(model: Any, exclude: set[str] = frozenset()) -> dict[str, Any]:
    """模型 → 规范 payload（键序 = 定义序、排除默认值、排除派生字段）。"""
    return model.model_dump(mode="json", exclude_defaults=True, exclude=exclude)


def _dump_yaml(data: Any) -> str:
    out = yaml.dump(data, Dumper=_QuotingDumper, **_YAML_KWARGS)
    return out.rstrip("\n")


def render_frontmatter(fm: Frontmatter) -> str:
    payload = _model_to_payload(fm)
    if not payload:
        return ""
    return "---\n" + _dump_yaml(payload) + "\n---"


def render_block(block: Block) -> str:
    exclude = _RENDER_EXCLUDE.get(block.type, frozenset())
    payloads = (
        [_model_to_payload(m, exclude)
         if hasattr(m, "model_dump") else m
         for m in block.payload]
        if isinstance(block.payload, list)
        else _model_to_payload(block.payload, exclude)
        if hasattr(block.payload, "model_dump")
        else block.payload
    )
    if block.review == "reviewed":
        # 信封仅在非缺省时写出（列表块写到每个对象上）
        if isinstance(payloads, list):
            payloads = [{"review": "reviewed", **p} for p in payloads]
        else:
            payloads = {"review": "reviewed", **payloads}
    body = _dump_yaml(payloads)
    return f"```gimbal:{block.type}\n{body}\n```"


def render(deliverable: Deliverable) -> str:
    """渲染规范形 Markdown。frontmatter 在前；节点序列原序回写。"""
    parts: list[str] = []
    if deliverable.frontmatter is not None:
        fm = render_frontmatter(deliverable.frontmatter)
        if fm:
            parts.append(fm)

    for node in deliverable.nodes:
        if isinstance(node, Prose):
            parts.append(node.text)
        else:
            parts.append(render_block(node))

    out = "\n\n".join(p for p in parts if p.strip())
    return out + "\n" if out else ""
