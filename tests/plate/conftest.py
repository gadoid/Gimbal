"""gimbal_plate 测试 fixtures。"""
from __future__ import annotations

import pytest

# 确保 gimbal_plate 可被 import(src/gimbal-plate 在 PYTHONPATH 或已安装)
import sys
from pathlib import Path

_pkg_root = Path(__file__).resolve().parents[2] / "src" / "gimbal-plate"
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from pydantic import BaseModel

from gimbal_plate import (
    ApiSpec,
    EndpointMetadata,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
    registry,
)
from gimbal_plate.http import create_app
from gimbal_plate.registry import PlateRegistry
from gimbal_plate.systems.common.dimensions import register_common_dims
from gimbal_plate.systems.fin.dimensions import register_fin_dims


@pytest.fixture
def fresh_registry() -> PlateRegistry:
    """A fresh in-memory registry pre-loaded with the bundled fin system + M6 dims.

    Both production (``gimbal_plate.http.app._lifespan``) and this fixture
    route through the same single source of truth:
    :func:`gimbal_plate.systems.fin.dimensions.register_fin_dims`. Tests pass
    this registry to ``create_app(registry=...)``, which means the production
    lifespan will skip its owned-mode setup.

    ADR 0002 §D-D4: shared helper replaces the prior near-verbatim duplicate
    of ``app._register_fin_dims`` — drift between app and tests is no longer
    possible.

    ``register_fin_dims`` 不注册 endpoint(防二次注册);按其契约,
    调用方须先把 ``ALL_ENDPOINTS`` 注册进 registry(与生产端
    ``app._lifespan`` owned 模式步骤 1 对齐)。
    """
    from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS

    reg = PlateRegistry()
    for ep in ALL_ENDPOINTS:
        reg.register_endpoint(ep)
    register_fin_dims(reg)
    # common 通用层与生产 lifespan 同步注册(声明式系统 + 通用 seed)。
    register_common_dims(reg)
    return reg


@pytest.fixture
def http_client(fresh_registry: PlateRegistry):
    """A ``TestClient`` bound to a plate app using ``fresh_registry``."""
    from fastapi.testclient import TestClient  # local import keeps top of file stable

    with TestClient(create_app(registry=fresh_registry)) as client:
        yield client


# ── 示例 Pydantic 模型 ──────────────────────────────────────────────

class OrderIn(BaseModel):
    order_no: str
    amount: float


class OrderOut(BaseModel):
    order_id: str
    order_no: str


class OrderPatch(BaseModel):
    order_id: str
    status: str


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def reset_registry() -> None:
    """每个测试前后清空全局 registry,避免用例间污染。"""
    registry.reset()
    yield
    registry.reset()


@pytest.fixture
def order_endpoint() -> EndpointSpec:
    """一个示例 EndpointSpec:新增订单(POST /api/v1/orders)。"""
    return EndpointSpec(
        id="finas.order.add",
        system="finas",
        service="settlement",
        name="新增订单",
        description="创建一笔结算订单",
        api=ApiSpec(
            service="settlement",
            method="POST",
            path="/api/v1/orders",
            timeout_seconds=30,
            auth="bearer",
        ),
        request=RequestSpec(
            body_type="json",
            model=OrderIn,
            fields=[
                IOFieldBinding(name="order_no", path="order_no", required=True,
                               example="ORD-001", ui_kind="text"),
                IOFieldBinding(name="amount", path="amount", required=True,
                               example=99.9, ui_kind="number"),
            ],
        ),
        responses={
            200: ResponseSpec(
                status=200,
                description="成功",
                model=OrderOut,
                fields=[
                    IOFieldBinding(name="order_id", path="order_id",
                                   required=True, ui_kind="text"),
                    IOFieldBinding(name="order_no", path="order_no",
                                   required=True, ui_kind="text"),
                ],
                assertable_fields=["order_id", "order_no"],
            ),
            400: ResponseSpec(status=400, description="参数错误"),
        },
        metadata=EndpointMetadata(
            module="订单",
            tags=["冒烟", "结算"],
            owner="alice",
            priority=1,
            preconditions=["已登录"],
            success_criteria="返回 order_id",
        ),
        version="1.0.0",
    )


@pytest.fixture
def order_patch_endpoint() -> EndpointSpec:
    """第二个示例 EndpointSpec:更新订单(POST /api/v1/orders/patch)。"""
    return EndpointSpec(
        id="finas.order.patch",
        system="finas",
        service="settlement",
        name="更新订单",
        api=ApiSpec(
            service="settlement",
            method="POST",
            path="/api/v1/orders/patch",
        ),
        request=RequestSpec(body_type="json", model=OrderPatch),
        responses={200: ResponseSpec(status=200, model=OrderOut)},
        metadata=EndpointMetadata(tags=["结算"], owner="bob"),
    )
