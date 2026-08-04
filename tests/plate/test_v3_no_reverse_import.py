"""V3 阶段 7:层级隔离回归测试。"""
from __future__ import annotations

import re
from pathlib import Path

from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS


PKG_ROOT = Path(__file__).resolve().parents[2] / "src" / "gimbal-plate" / "gimbal_plate"
PY_FILES = sorted(
    p for p in PKG_ROOT.rglob("*.py")
    if p.name != "__init__.py"
)


def _layer_of(path: Path) -> str:
    rel = path.relative_to(PKG_ROOT)
    return rel.parts[0] if rel.parts else ""


def _imports_in(text: str) -> list[str]:
    modules: list[str] = []
    for pattern in (
        r"^\s*from\s+([\w.]+)\s+import",
        r"^\s*import\s+([\w.]+)",
    ):
        for match in re.finditer(pattern, text, re.MULTILINE):
            modules.append(match.group(1))
    return modules


def _violations(layer: str, forbidden: tuple[str, ...]) -> list[str]:
    bad: list[str] = []
    for path in PY_FILES:
        if _layer_of(path) != layer:
            continue
        text = path.read_text(encoding="utf-8")
        for module in _imports_in(text):
            if module.startswith(forbidden):
                rel = path.relative_to(PKG_ROOT)
                bad.append(f"{rel} -> {module}")
    return bad


class TestNoReverseImport:
    """schema / systems / export / case 各层只允许沿设计文档规定的方向依赖。"""

    def test_schema_has_no_dependency_on_systems_or_export(self) -> None:
        bad = _violations(
            "schema",
            ("gimbal_plate.systems", "gimbal_plate.export", "gimbal_plate.case"),
        )
        assert bad == [], f"schema/* 反向依赖: {bad}"

    def test_systems_does_not_depend_on_export_or_case(self) -> None:
        bad = _violations(
            "systems",
            ("gimbal_plate.export", "gimbal_plate.case"),
        )
        assert bad == [], f"systems/* 反向依赖: {bad}"

    def test_export_does_not_depend_on_legacy_case_module(self) -> None:
        bad = _violations("export", ("gimbal_plate.case",))
        assert bad == [], f"export/* 反向依赖 case/*: {bad}"

    def test_legacy_case_module_only_re_exports_from_export(self) -> None:
        case_dir = PKG_ROOT / "case"
        if not case_dir.exists():
            return
        offenders: list[str] = []
        for path in sorted(case_dir.rglob("*.py")):
            if path.name == "__init__.py":
                continue
            text = path.read_text(encoding="utf-8")
            for module in _imports_in(text):
                if not module.startswith("gimbal_plate."):
                    continue
                if module.startswith("gimbal_plate.export.gimbal"):
                    continue
                offenders.append(f"{path.relative_to(PKG_ROOT)} -> {module}")
        assert offenders == [], f"case/* 不应直连其他层: {offenders}"


class TestEndpointCompositionHolds:
    """V3 核心原则:系统差异由组合表达,允许 EndpointSpec 容纳 body model。"""

    def test_all_fin_endpoints_carry_system_and_service(self) -> None:
        expected_services = {
            "settlement", "account",
            "order_entrust", "order", "order_fee", "audit",
        }
        for endpoint in ALL_ENDPOINTS:
            assert endpoint.system == "fin"
            assert endpoint.service in expected_services
