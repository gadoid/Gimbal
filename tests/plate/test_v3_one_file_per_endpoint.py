"""一文件一交付物（方言版纪律测试，A1 交付项）。

旧版：fin/endpoint/ 每 .py 导出恰好一个 EndpointSpec + 文件名与 id 尾段一致。
A2 版：``systems/<系统>/endpoints/*.md`` 每文件恰好一个 gimbal:endpoint 块；
文件名 = ``<endpoint id>.md``。真源从 Python 实例移到 Markdown（P1）。
"""
from __future__ import annotations

from gimbal_plate.dialect import EndpointSpec, parse_markdown
from tests.plate.conftest import SYSTEMS_ROOT

_ENDPOINTS_DIRS = sorted(SYSTEMS_ROOT.glob("*/endpoints"))


def test_endpoints_dirs_exist() -> None:
    assert {d.parent.name for d in _ENDPOINTS_DIRS} == {"fin", "platform"}


def test_each_endpoint_file_exports_one_endpointspec() -> None:
    count = 0
    for d in _ENDPOINTS_DIRS:
        for md in sorted(d.glob("*.md")):
            deliverable = parse_markdown(
                md.read_text(encoding="utf-8"), source=str(md)
            )
            blocks = deliverable.blocks("endpoint")
            assert len(blocks) == 1, f"{md}: 须恰好一个 gimbal:endpoint 块"
            models = blocks[0].models()
            assert len(models) == 1 and isinstance(models[0], EndpointSpec)
            count += 1
    assert count == 149


def test_endpoint_filename_matches_id() -> None:
    for d in _ENDPOINTS_DIRS:
        for md in sorted(d.glob("*.md")):
            deliverable = parse_markdown(
                md.read_text(encoding="utf-8"), source=str(md)
            )
            ep = deliverable.blocks("endpoint")[0].payload
            assert md.stem == ep.id, f"{md}: 文件名须等于 endpoint id ({ep.id})"
            assert deliverable.frontmatter.system == d.parent.name
