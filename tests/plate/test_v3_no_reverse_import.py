"""V3 阶段 7:层级隔离回归测试。"""
from __future__ import annotations

from gimbal_plate.dialect import EndpointSpec
from tests.plate.conftest import SYSTEMS_ROOT
from gimbal_plate.loader import load_registry

_REG = load_registry([SYSTEMS_ROOT])
ALL_ENDPOINTS = [e for e in _REG.list_endpoints() if isinstance(e, EndpointSpec)]
ALL_FIN = [e for e in ALL_ENDPOINTS if e.system == 'fin']

import re
from pathlib import Path



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

    def test_no_import_of_executor_package(self) -> None:
        """P4 单向依赖守卫(第三轮评审降级清单第 1 项补齐):plate 不得
        import 执行器包 ``gimbal``。

        pyproject 的 plate 入口注释、selfdescribe/protocols.py、
        http/strategy_dim.py 与设计附录 D 都引用本守卫——单向纪律的落点:
        plate 是最底层事实源(设计第 2 节),执行器/平台消费 plate;反向
        import 会让独立 `plate` 入口拖进执行器安装树。
        gimbal_plate.utils.jsonpath 是 V2 拍板的同期拷贝(coverage 配置
        已注明),不是 import,不受本条约束。AST 扫描:字符串/注释里的
        "gimbal" 不算,只有真实 import 语句算。
        """
        import ast

        def _hits(module: str) -> bool:
            return module == "gimbal" or module.startswith("gimbal.")

        offenders: list[str] = []
        all_py = sorted(PKG_ROOT.rglob("*.py"))  # 含 __init__.py(不沿用 PY_FILES 的排除)
        for path in all_py:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            rel = path.relative_to(PKG_ROOT)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if _hits(alias.name):
                            offenders.append(f"{rel}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if _hits(node.module):
                        offenders.append(f"{rel}: from {node.module} import")
        assert offenders == [], (
            f"P4 单向依赖被破坏(plate 不得 import 执行器包 gimbal): {offenders}"
        )


class TestEndpointCompositionHolds:
    """V3 核心原则:系统差异由组合表达,允许 EndpointSpec 容纳 body model。"""

    def test_all_fin_endpoints_carry_system_and_service(self) -> None:
        expected = {"fin": {"fin-service"}, "platform": {"platform-service"}}
        for endpoint in ALL_ENDPOINTS:
            assert endpoint.system in expected, endpoint.id
            assert endpoint.service in expected[endpoint.system]
