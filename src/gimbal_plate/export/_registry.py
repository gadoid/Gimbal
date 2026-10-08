"""gimbal_plate.export._registry —— 声明式 dispatch 入口(V3.1.1)。

设计背景
--------
plate 对外暴露的服务是**无状态**的(见 ``_requests.py`` 设计背景)。
``dispatch()`` 是声明式入口,把调用方传入的入参(consumer + scenario +
其他可选参数)路由到对应的 exporter 实现。

两条路径并存:

    1. **声明式**:``dispatch(consumer, scenario, ...)``
       - 调试 / UI 配置 / 动态 consumer 名场景
       - plate 用 ``_REQUEST_REGISTRY`` 查表 + 用对应 ``ConsumerRequest``
         做参数校验
       - 调用方不直接 import exporter 类

    2. **静态契约**:
       ``req = PlatformConsumerRequest(...); exporter = PlatformScenarioExporter(req.scenario, ...); result = exporter.render(...)``
       - 编译时类型检查 / IDE 自动补全
       - 调用方自己掌控每一步

两条路径共享同一份 ``ConsumerRequest`` 定义 + 同一份 exporter 实现。
改 request model / exporter,两条路径都生效。

工作流(声明式):

    dispatch("gimbal", scenario=sc)
        │
        ├─ 查 _REQUEST_REGISTRY["gimbal"]
        │     → ("gimbal",   GimbalConsumerRequest,   GimbalScenarioExporter)
        │
        ├─ request = GimbalConsumerRequest(scenario=sc)
        │     (Pydantic 自动校验;失败时抛 ValidationError)
        │
        ├─ exporter = GimbalScenarioExporter(request.scenario)
        │
        └─ return exporter.render(request.scenario)

    dispatch("platform", scenario=sc, endpoints=eps, sections=("endpoints",))
        │
        ├─ 查 _REQUEST_REGISTRY["platform"]
        │     → ("platform", PlatformConsumerRequest, PlatformScenarioExporter)
        │
        ├─ request = PlatformConsumerRequest(scenario=sc, endpoints=eps,
        │                                  sections=("endpoints",))
        │     (sections 字段由 ``Literal[...]`` 校验,非法值直接拒)
        │
        ├─ exporter = PlatformScenarioExporter(request.scenario,
        │                                     endpoints=request.endpoints)
        │
        └─ return exporter.render(request.scenario, endpoints=request.endpoints)

扩展方式
--------
新增 consumer 时:
    1. 在 ``export/_requests.py`` 加一个 ``XxxConsumerRequest`` model
    2. 在 ``export/xxx.py`` 实现一个 ``XxxScenarioExporter(ScenarioExporter)``
    3. 在下方 ``_REQUEST_REGISTRY`` 加一行映射
无需修改 ``dispatch()`` 本身。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Type

from pydantic import BaseModel

if TYPE_CHECKING:
    from gimbal_plate.export._protocol import ScenarioExporter
    from gimbal_plate.schema.endpoint import EndpointSpec
    from gimbal_plate.schema.scenario import Scenario as ScenarioModel


# 内部注册表:consumer_id → (request_cls, exporter_cls)
# 公开访问请用 ``available_consumers()`` / ``dispatch()``。
_REQUEST_REGISTRY: dict[
    str, tuple[Type[BaseModel], Type["ScenarioExporter"]]
] = {}


def _build_default_registry() -> dict[
    str, tuple[Type[BaseModel], Type["ScenarioExporter"]]
]:
    """构建默认注册表。

    在模块导入时被 ``_init_registry()`` 调用,避免循环 import。
    """
    from gimbal_plate.export._requests import (
        GimbalConsumerRequest,
        PlatformConsumerRequest,
    )
    from gimbal_plate.export.gimbal import GimbalScenarioExporter
    from gimbal_plate.export.platform import PlatformScenarioExporter

    return {
        "gimbal":   (GimbalConsumerRequest,   GimbalScenarioExporter),
        "platform": (PlatformConsumerRequest, PlatformScenarioExporter),
    }


def _init_registry() -> None:
    """首次调用 ``dispatch`` 时初始化注册表(惰性)。"""
    if not _REQUEST_REGISTRY:
        _REQUEST_REGISTRY.update(_build_default_registry())


def available_consumers() -> list[str]:
    """返回所有已注册 consumer 名(用于 UI 下拉、错误信息等)。"""
    _init_registry()
    return sorted(_REQUEST_REGISTRY.keys())


def dispatch(
    consumer: str,
    scenario: "ScenarioModel",
    **kwargs: Any,
) -> dict[str, Any]:
    """声明式 dispatch 入口。

    Parameters
    ----------
    consumer:
        consumer 名,例如 ``"gimbal"`` / ``"platform"``。未知值会抛
        ``ValueError``(列出已注册 consumer)。
    scenario:
        ``gimbal_plate.schema.Scenario`` 实例。
    **kwargs:
        转发到对应 ``ConsumerRequest`` 的其他字段(``endpoints`` /
        ``sections`` 等)。consumer 不接受的字段会被 Pydantic
        ``extra="forbid"`` 拦截。

    Returns
    -------
    dict[str, Any]
        对应 exporter 的渲染结果(可被 ``json.dumps`` 序列化)。

    Raises
    ------
    ValueError
        consumer 名未注册。
    pydantic.ValidationError
        入参与 consumer 的 request model 不匹配。
    """
    _init_registry()
    if consumer not in _REQUEST_REGISTRY:
        raise ValueError(
            f"unknown consumer: {consumer!r}; "
            f"available: {available_consumers()}"
        )

    request_cls, exporter_cls = _REQUEST_REGISTRY[consumer]

    # 1. 用 consumer 的 request model 校验入参
    request = request_cls(consumer=consumer, scenario=scenario, **kwargs)

    # 2. 实例化 exporter
    exporter_kwargs: dict[str, Any] = {}
    if getattr(request, "endpoints", None) is not None:
        exporter_kwargs["endpoints"] = request.endpoints
    exporter = exporter_cls(request.scenario, **exporter_kwargs)

    # 3. 渲染(sections 字段在 V3.1.1 仅作声明,目前全视图输出;
    #    Step 3 可在 PlatformScenarioExporter 里实现 sections 切片)
    return exporter.render(
        request.scenario,
        endpoints=getattr(request, "endpoints", None),
    )


__all__ = [
    "dispatch",
    "available_consumers",
]