"""F5：版本线声明校验（版本模型 v1.4 2.1/2.4；开发计划 T1.6 第一块）。

P8 加法字段——未声明任何 line 字段的系统不受影响；一旦声明即受校验。
"""
from pathlib import Path

import pytest

from gimbal_plate.dialect.validation import (
    load_types,
    validate_system_tree,
)

_TYPES = load_types(Path(__file__).resolve().parents[3] / "types" / "types.yaml")

_SYSTEM_MD = """---
type: system
system: fin{extra}
---

# fin

```gimbal:system
review: reviewed
name: fin-service
version: 1.1.0
```
"""


def _system(tmp_path: Path, extra: str) -> Path:
    root = tmp_path / "fin"
    root.mkdir()
    (root / "system.md").write_text(
        _SYSTEM_MD.format(extra=extra), encoding="utf-8", newline="\n")
    return root


def _f5(tmp_path: Path, extra: str) -> list[str]:
    report = validate_system_tree(_system(tmp_path, extra), types=_TYPES)
    return [f.message for f in report.blocking if f.rule == "F5"]


def test_no_line_fields_untouched(tmp_path: Path) -> None:
    """现状系统（fin/platform 未声明版本线）不受 F5 影响。"""
    assert _f5(tmp_path, "") == []


def test_free_manual_default_passes(tmp_path: Path) -> None:
    """只声明 line（缺省 free + manual）——RS0 起始口径，通过。"""
    assert _f5(tmp_path, '\nline: "3.2"') == []


@pytest.mark.parametrize("extra,frag", [
    ('\nline: "3.2"\nline_scheme: semver', "不符合 semver"),
    ('\nline: "3.x"\nline_scheme: date', "不符合 date"),
    ('\nline: "r12"\nline_scheme: iteration', "不符合 iteration"),
    ('\nline: "3.2"\nline_scheme: pattern', "须声明 line_pattern"),
    ('\nline: "3.2"\nline_scheme: pattern\nline_pattern: "^r\\\\d+$"',
     "不匹配 line_pattern"),
    ('\nline: "3.2"\nline_scheme: weekly', "line_scheme"),
    ('\nline: "3.2"\nline_source: git', "line_source"),
    ('\nline: "3.2"\nline_source: service_version', "line_service"),
    ('\nline: "3.2"\nline_source: service_version\nline_service: no-svc',
     "gimbal:system"),
    ('\npredecessor_line: "3.1"', "缺少 line"),
])
def test_f5_blocking(tmp_path: Path, extra: str, frag: str) -> None:
    findings = _f5(tmp_path, extra)
    assert len(findings) == 1, findings
    assert frag in findings[0]


@pytest.mark.parametrize("extra", [
    '\nline: "3.2.0"\nline_scheme: semver\npredecessor_line: "3.1.4"',
    '\nline: "2026-10-10"\nline_scheme: date',
    '\nline: "12"\nline_scheme: iteration',
    '\nline: "r12"\nline_scheme: pattern\nline_pattern: "^r\\\\d+$"',
    ('\nline: "1.1.0"\nline_source: service_version\n'
     'line_service: fin-service'),
])
def test_f5_passes(tmp_path: Path, extra: str) -> None:
    assert _f5(tmp_path, extra) == []
