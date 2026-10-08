"""gimbal_plate 测试 fixtures（A2：统一加载器 + 方言 M2）。"""
from __future__ import annotations

import pytest

# 确保 gimbal_plate 可被 import(src 在 PYTHONPATH 或已安装)
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parents[2]
_pkg_root = _repo / "src"
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from gimbal_plate import (
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    HttpBinding,
    RequestSpec,
    ResponseSpec,
    registry,
)
from gimbal_plate.http import create_app
from gimbal_plate.loader import load_registry
from gimbal_plate.registry import PlateRegistry

# systems/ 真源（P1：Markdown 方言为唯一真源；测试与生产同一加载器）
SYSTEMS_ROOT = _repo / "systems"


@pytest.fixture
def fresh_registry() -> PlateRegistry:
    """统一加载器从 ``systems/`` 构建的全新 registry（与生产 lifespan 同路径）。

    A2 起：不再 import 各系统 Python 实例 / dimensions.py —— 单一装配
    入口是 :func:`gimbal_plate.loader.load_registry`。
    """
    return load_registry([SYSTEMS_ROOT])


@pytest.fixture
def http_client(fresh_registry: PlateRegistry):
    """A ``TestClient`` bound to a plate app using ``fresh_registry``."""
    from fastapi.testclient import TestClient  # local import keeps top of file stable

    with TestClient(create_app(registry=fresh_registry)) as client:
        yield client


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def reset_registry() -> None:
    """每个测试前后清空全局 registry,避免用例间污染。"""
    registry.reset()
    yield
    registry.reset()


@pytest.fixture
def order_endpoint() -> EndpointSpec:
    """一个示例 EndpointSpec:新增订单(POST /api/v1/orders)—— 方言 M2 形态。"""
    return EndpointSpec(
        id="finas.order.add",
        system="finas",
        service="settlement",
        name="新增订单",
        description="创建一笔结算订单",
        binding=HttpBinding(
            method="POST",
            path="/api/v1/orders",
            timeout_seconds=30,
            auth="bearer",
        ),
        request=RequestSpec(
            declarations=[
                DeclarationEntry(name="order_no", path="$.order_no", type='string',
                                 required=True,
                                 example="ORD-001", ui_kind="text"),
                DeclarationEntry(name="amount", path="$.amount", type='number',
                                 required=True,
                                 example=99.9, ui_kind="number"),
            ],
        ),
        responses={
            "200": ResponseSpec(
                description="成功",
                declarations=[
                    DeclarationEntry(name="order_id", path="$.data.order_id",
                                     type='string', required=True,
                                     ui_kind="text", assertable=True),
                    DeclarationEntry(name="order_no", path="$.data.order_no",
                                     type='string', required=True,
                                     ui_kind="text", assertable=True),
                ],
            ),
            "400": ResponseSpec(description="参数错误"),
        },
        metadata=EndpointMetadata(
            module="订单",
            tags=["冒烟", "结算"],
            owner="alice",
            priority=1,
            preconditions=["已登录"],
            success_criteria="返回 order_id",
        ),
    )


@pytest.fixture
def order_patch_endpoint() -> EndpointSpec:
    """第二个示例 EndpointSpec:更新订单(POST /api/v1/orders/patch)。"""
    return EndpointSpec(
        id="finas.order.patch",
        system="finas",
        service="settlement",
        name="更新订单",
        binding=HttpBinding(method="POST", path="/api/v1/orders/patch"),
        request=RequestSpec(
            declarations=[
                DeclarationEntry(name="order_id", path="$.order_id", type='string',
                                 required=True, ui_kind="text"),
                DeclarationEntry(name="status", path="$.status", type='string',
                                 required=True, ui_kind="text"),
            ],
        ),
        # declare() 语法糖已随旧栈退役(X5);声明树直写
        responses={
            "200": ResponseSpec(declarations=[
                DeclarationEntry(name="order_id", path="$.data.order_id",
                                 type='string', assertable=True),
                DeclarationEntry(name="status", path="$.data.status",
                                 type='string', assertable=True),
            ]),
        },
        metadata=EndpointMetadata(tags=["结算"], owner="bob"),
    )
