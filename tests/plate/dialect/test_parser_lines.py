"""RS0 第一项：Block 记录结束行（版本模型 3.2 分级规则的实现前提）。

finding 只有 source / line，闸门要按评审状态分级（D-4），就必须能把
行号映射到块与对象——`[line, end_line]` 区间是这一映射的依据。
"""
from gimbal_plate.dialect.parser import parse_markdown

TEXT = """---
type: system
system: fin
---

# fin

```gimbal:system
review: reviewed
name: fin-service
version: 1.1.0
```

中间散文。

```gimbal:defaults
review: reviewed
config:
  setup: []
```

收尾散文。
"""


def _fence_lines() -> list[int]:
    return [
        i + 1 for i, l in enumerate(TEXT.split("\n"))
        if l.startswith("```")
    ]


def test_block_records_end_line() -> None:
    d = parse_markdown(TEXT, source="<test>")
    blocks = d.blocks()
    assert len(blocks) == 2
    fences = _fence_lines()          # [起始1, 闭合1, 起始2, 闭合2]
    first, second = blocks
    assert (first.line, first.end_line) == (fences[0], fences[1])
    assert (second.line, second.end_line) == (fences[2], fences[3])


def test_block_ranges_disjoint_and_monotonic() -> None:
    blocks = parse_markdown(TEXT, source="<test>").blocks()
    ordered = sorted(blocks, key=lambda b: b.line)
    for prev, nxt in zip(ordered, ordered[1:]):
        assert prev.end_line < nxt.line


def test_finding_line_maps_to_unique_block() -> None:
    """分级规则的前提：任一行号至多命中一个块区间。"""
    blocks = parse_markdown(TEXT, source="<test>").blocks()

    def owner_block(finding_line: int):
        hits = [b for b in blocks if b.line <= finding_line <= b.end_line]
        assert len(hits) == 1, f"行 {finding_line} 命中 {len(hits)} 个块"
        return hits[0]

    fences = _fence_lines()
    assert owner_block(fences[0]).type == "system"       # 起始围栏行
    assert owner_block(fences[0] + 2).type == "system"   # 块体行
    assert owner_block(fences[1]).type == "system"       # 闭合围栏行
    assert owner_block(fences[2] + 2).type == "defaults"


def test_list_payload_block_end_line() -> None:
    text = (
        "```gimbal:system\n"
        "- review: reviewed\n"
        "  name: a\n"
        "  version: 1.0.0\n"
        "- review: reviewed\n"
        "  name: b\n"
        "  version: 1.0.0\n"
        "```\n"
    )
    d = parse_markdown(text, source="<test>")
    (block,) = d.blocks()
    assert block.line == 1 and block.end_line == 8
    assert isinstance(block.payload, list)
