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
    """schema / systems / export 各层只允许沿设计文档规定的方向依赖。"""

    def test_schema_has_no_dependency_on_systems_or_export(self) -> None:
        bad = _violations(
            "schema",
            ("gimbal_plate.systems", "gimbal_plate.export"),
        )
        assert bad == [], f"schema/* 反向依赖: {bad}"

    def test_systems_does_not_depend_on_export(self) -> None:
        bad = _violations(
            "systems",
            ("gimbal_plate.export",),
        )
        assert bad == [], f"systems/* 反向依赖: {bad}"

    def test_legacy_case_module_removed(self) -> None:
        """case/ 目录已删除,任何模块都不应再依赖 gimbal_plate.case。"""
        offenders: list[str] = []
        for path in PY_FILES:
            text = path.read_text(encoding="utf-8")
            for module in _imports_in(text):
                if module == "gimbal_plate.case" or module.startswith("gimbal_plate.case."):
                    offenders.append(f"{path.relative_to(PKG_ROOT)} -> {module}")
        assert offenders == [], f"残留 case/ 引用: {offenders}"

        case_dir = PKG_ROOT / "case"
        assert not case_dir.exists(), f"case/ 目录应已删除,仍存在: {case_dir}"

    def test_legacy_service_module_removed(self) -> None:
        """service/ 目录已被迁移重定义(V3.1):

        - ``ServiceDefinition`` 已迁入 ``schema/service_definition.py``
        - ``service/`` 当前承担"服务层纯函数"职责

        验证点(符号级扫描,避免误伤合法的 service/ 包内部引用):
            1. 旧位置 ``gimbal_plate/service/service.py`` 不应再存在
            2. 新位置 ``schema/service_definition.py`` 必须存在
            3. 任何**模块**都不得以 ``from gimbal_plate.service(...)
               import ServiceDefinition`` 这种形态引用旧数据类
        """
        old_file = PKG_ROOT / "service" / "service.py"
        assert not old_file.exists(), (
            f"旧 service/service.py 应已删除,仍存在: {old_file}"
        )

        sd_new = PKG_ROOT / "schema" / "service_definition.py"
        assert sd_new.exists(), (
            f"schema/service_definition.py 应已建立,仍缺失: {sd_new}"
        )

        # 符号级扫描:精确匹配"from gimbal_plate.service ... import ServiceDefinition"
        offenders: list[str] = []
        for path in PY_FILES:
            rel = path.relative_to(PKG_ROOT)
            # 跳过 service/ 包自身的引用 —— 它现在的合法用法是
            # `from gimbal_plate.service.<sub> import <func>`(纯函数),
            # 不会再出现 ServiceDefinition。
            if rel.parts and rel.parts[0] == "service":
                continue
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                if "ServiceDefinition" not in stripped:
                    continue
                if "from gimbal_plate.service" not in stripped:
                    continue
                offenders.append(f"{rel}:{line_no}: {stripped}")
        assert offenders == [], f"残留 ServiceDefinition 旧路径引用: {offenders}"


class TestEndpointCompositionHolds:
    """V3 核心原则:系统差异由组合表达,允许 EndpointSpec 容纳 body model。"""

    def test_all_fin_endpoints_carry_system_and_service(self) -> None:
        expected_services = {"fin-service"}
        for endpoint in ALL_ENDPOINTS:
            assert endpoint.system == "fin"
            assert endpoint.service in expected_services
