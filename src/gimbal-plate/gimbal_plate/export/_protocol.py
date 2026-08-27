"""gimbal_plate.export._protocol —— ScenarioExporter 抽象基类(V3.1.2)。

本文件定义所有 ``export/*.py`` 模块需要遵循的统一接口,以及每个 exporter 必须
声明的静态能力清单。

设计原则(V3 §1,核心):
    - **dict 必须经过 schema**:exporter 唯一输入形态是 ``Schema`` 对象
      (``ScenarioModel`` / ``EndpointSpec``),输出是 ``dict``。
    - 仅约束输入/输出形态,不约束字段细节(各 consumer 自有视图模型)。
    - 基类引用 ``schema/`` 的类型,但不引用任何具体 consumer 实现。
    - 依赖方向: ``export/_protocol.py → schema/``,
      ``export/*.py → export/_protocol.py``

Exporter 能力清单(V3.1.2)
------------------------
按"必填 / 可选 / meta"三类组织。每个新 exporter 必须满足所有必填项(C1-C5),
并显式声明它的可选能力(C6-C9),便于 dispatcher 做路由与切片决策。

**必填**(每个 exporter 都必须声明 / 实现):

    C1  ``consumer_id``               唯一字符串标识(registry key / dashboard / log)
    C2  ``render(scenario, *, endpoints)``  核心入口,接收 Schema,产出 dict
    C3  输入形态约束                    scenario 必须为 ``ScenarioModel``(非 Schema 抛 TypeError)
    C4  输出形态约束                    返回 dict 必须可 ``json.dumps`` 序列化(默认信任 schema)
    C5  ``capabilities`` 属性           静态能力描述

**可选**(按 consumer 性质声明):

    C6  ``sections``                   视图切片;Platform 声明 endpoints/navigation/config_summary
    C7  ``needs_endpoints``            render 是否需要 endpoint 列表;Platform=True / Gimbal=False
    C8  ``to_dict()`` 向后兼容入口       无参时等价于 ``render(self.scenario, endpoints=self.endpoints)``
    C9  ``supports(request)``          dispatcher 路由判断(按 consumer 名 / sections 子集)

**meta**(代码组织层):

    C10 ``capabilities`` 不可变         ``frozen=True``,运行时不变
    C11 ``capabilities`` 可 hash        dispatcher / cache 可用 ``caps`` 做 dict key
    C12 scenario 在 ``__init__`` 注入    ``render()`` 接受独立 scenario 参数,以便 dispatcher 切换
    C13 ``description`` / ``output_schema_kind``  人类语言描述 + 产物顶层 kind 标识

新增 consumer 时的 checklist
---------------------------
    □ C1:设 ``consumer_id`` 类属性(唯一)
    □ C2:实现 ``render(scenario, *, endpoints=None) -> dict``
    □ C3:校验 scenario 是 ``ScenarioModel`` 实例(基类提供 helper)
    □ C4:返回 dict 用 ``json.dumps`` 自检(基类提供 helper)
    □ C5:实现 ``capabilities`` 属性,声明 sections + needs_endpoints
    □ C9:若需 sections 级路由,override ``supports(request)``
    □ C10/C11:capabilities 是 ``frozen=True``,可 hash
    □ C12:``__init__`` 保留 ``self.scenario`` 引用(向后兼容 ``to_dict()``)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gimbal_plate.schema.endpoint import EndpointSpec
    from gimbal_plate.schema.scenario import Scenario as ScenarioModel


@dataclass(frozen=True)
class ExporterCapabilities:
    """声明式 exporter 的静态能力描述(C5/C10/C11)。

    字段(C13 扩展):
        consumer:
            唯一字符串标识(``"gimbal"`` / ``"platform"`` / ...)。
        sections:
            支持的视图切片;空元组表示无切片(整视图输出)。
            Platform 声明 ``("endpoints", "navigation", "config_summary")``。
        needs_endpoints:
            render 时是否需要 endpoint 列表。
            Platform=True(需要 endpoint 元数据才能渲染 view_hints / navigation);
            Gimbal=False(从 Scenario 自包含的 Api 即可还原)。
        description:
            人类语言描述,用于 dashboard / 文档 / 错误信息。
        output_schema_kind:
            产物顶层 ``kind`` 字段值,例如 ``"gimbal_scenario"`` /
            ``"platform_scenario"``,供 dispatcher / 日志识别产物类型。
    """

    consumer: str
    sections: tuple[str, ...] = ()
    needs_endpoints: bool = False
    description: str = ""
    output_schema_kind: str = ""

    def __post_init__(self) -> None:
        # C10 frozen 已经由 dataclass 保证;C11 由 dataclass 自动生成
        # __hash__;这里仅校验 description 不是 None(防止误传 None)。
        if self.description is None:  # type: ignore[unreachable]
            raise ValueError("ExporterCapabilities.description 不能为 None")

    def __hash__(self) -> int:  # C11 显式声明
        return hash((self.consumer, self.sections, self.needs_endpoints))


class ScenarioExporter(ABC):
    """所有 consumer scenario exporter 的抽象基类。

    子类必须:
        - 设置 ``consumer_id`` 类属性(或 override ``_consumer_id``)
        - 实现 ``render(scenario, *, endpoints=None) -> dict``
        - 调用基类 ``_validate_scenario()`` 校验入参(C3)
        - 返回前调用基类 ``_validate_dict()`` 自检可序列化(C4)

    子类可选 override(为声明式 dispatcher 预留):
        - ``capabilities``: 返回 ``ExporterCapabilities``
        - ``supports(request)``: 字符串 / dataclass 版声明式入口

    约束(子类实现必须满足):
        - 输入 ``scenario`` 为 ``gimbal_plate.schema.Scenario`` 实例
        - 输入 ``endpoints`` 可选,为 ``EndpointSpec`` 列表
        - 输出为 ``dict[str, Any]``,可被 ``json.dumps`` 序列化
    """

    # ── 必填(C1/C2) ────────────────────────────────────────────────
    @property
    @abstractmethod
    def consumer_id(self) -> str:
        """本 exporter 的 consumer 唯一标识(C1)。"""
        ...

    @abstractmethod
    def render(
        self,
        scenario: "ScenarioModel",
        *,
        endpoints: list["EndpointSpec"] | None = None,
    ) -> dict[str, Any]:
        """核心入口(C2)。把 ``scenario`` 翻译为本 consumer 的视图 dict。

        推荐实现模板::

            def render(self, scenario, *, endpoints=None):
                self._validate_scenario(scenario)            # C3
                if self.capabilities.needs_endpoints:
                    self._validate_endpoints(endpoints)       # C7
                out = self._do_render(scenario, endpoints)    # 业务逻辑
                self._validate_serializable(out)              # C4
                return out

        Parameters
        ----------
        scenario:
            ``gimbal_plate.schema.Scenario`` 实例。
        endpoints:
            ``EndpointSpec`` 列表;部分 consumer(``platform``)需要,
            不需要的 consumer(``gimbal``)忽略。

        Returns
        -------
        dict[str, Any]
            可被 ``json.dumps`` 序列化的视图字典。
        """
        ...

    # ── 校验 helper(C3/C4/C7) ─────────────────────────────────────
    def _validate_scenario(self, scenario: Any) -> "ScenarioModel":
        """C3:校验 ``scenario`` 是 ``ScenarioModel`` 实例。

        非 Schema 实例抛 ``TypeError``,错误信息包含传入类型与期望类型,
        便于调用方排查。

        返回原对象(便于子类 ``return self._validate_scenario(scenario)`` 链式调用)。
        """
        # 局部 import 避免循环(``schema/`` 反向依赖 ``export/`` 是不允许的)
        from gimbal_plate.schema.scenario import Scenario as ScenarioModel

        if not isinstance(scenario, ScenarioModel):
            raise TypeError(
                f"{type(self).__name__}.render() 入参 scenario 必须是 "
                f"gimbal_plate.schema.Scenario 实例,实际收到 {type(scenario).__name__}"
            )
        return scenario

    def _validate_endpoints(
        self,
        endpoints: list["EndpointSpec"] | None,
    ) -> list["EndpointSpec"]:
        """C7:校验 ``endpoints`` 是 ``EndpointSpec`` 列表(若声明 needs_endpoints=True)。

        仅当 ``self.capabilities.needs_endpoints`` 为 True 时调用;
        否则 ``endpoints`` 会被忽略,无需校验。
        """
        from gimbal_plate.schema.endpoint import EndpointSpec

        eps = list(endpoints or [])
        for i, ep in enumerate(eps):
            if not isinstance(ep, EndpointSpec):
                raise TypeError(
                    f"{type(self).__name__}.render() endpoints[{i}] 必须是 "
                    f"EndpointSpec 实例,实际收到 {type(ep).__name__}"
                )
        return eps

    def _validate_serializable(self, out: Any) -> dict[str, Any]:
        """C4:校验返回 dict 可被 ``json.dumps`` 序列化。

        默认信任 schema 输出;若子类手工构造 dict 嵌套了非基本类型
        (例如 ``Decimal`` / ``datetime`` / 自定义类),应自行转换或在此处抛错。
        """
        import json

        if not isinstance(out, dict):
            raise TypeError(
                f"{type(self).__name__}.render() 返回值必须是 dict,实际收到 "
                f"{type(out).__name__}"
            )
        try:
            json.dumps(out)
        except (TypeError, ValueError) as e:
            raise TypeError(
                f"{type(self).__name__}.render() 返回 dict 不可被 json.dumps 序列化: {e}"
            ) from e
        return out

    # ── 可选(C5/C8/C9) ──────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        """向后兼容入口(零参,C8)。

        默认实现要求子类在 ``__init__`` 中保留 ``scenario`` 引用;若不保留,
        子类应 override 此方法。
        """
        scenario = getattr(self, "scenario", None)
        if scenario is None:
            raise NotImplementedError(
                "exporter 必须在 __init__ 中保留 scenario 引用,或 override to_dict()"
            )
        endpoints = getattr(self, "endpoints", None)
        return self.render(scenario, endpoints=endpoints)

    @property
    def capabilities(self) -> ExporterCapabilities:
        """默认能力描述:仅标识 consumer 名,无可用 sections(C5 默认)。

        子类应 override 返回完整 ``ExporterCapabilities``。
        """
        return ExporterCapabilities(consumer=self.consumer_id)

    def supports(self, request: Any) -> bool:
        """声明式入口的路由判断(C9)。

        默认实现按 consumer 名匹配;子类若需 sections 级路由,
        应 override 此方法。

        ``request`` 形态:
            V3.1.2:str(consumer 名)
            未来  :ConsumerRequest dataclass(consumer + sections + ...)
        """
        return request == self.consumer_id


__all__ = [
    "ExporterCapabilities",
    "ScenarioExporter",
]