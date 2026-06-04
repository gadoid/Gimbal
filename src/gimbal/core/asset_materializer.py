"""core/asset_materializer.py

引用物化器（Asset Materializer）。

职责：
    在用例对象（Scenario / Step / Api / Request / Strategy / body dict ...）被
    装入执行器之前，把图里所有 Ref 节点（RefBase 任意子类）替换为从 AssetStore
    拉来的真实数据类对象。

设计原则：
    1. 数据类无关 —— 只看 isinstance(x, RefBase)，不关心具体是 StepRef
       / ApiRef / RequestRef / StrategyRef / Ref 中的哪一种
    2. 固定点算法 —— 拉来的内容里可能又含 Ref，递归处理直到没有 Ref 为止
    3. 循环保护 —— 同时跟踪 (RefClass, ref) 栈与递归深度，避免无限递归
    4. 不可变遍历 —— 使用 frozenset 推进 visited 集合，避免兄弟分支互相污染

与 AssetResolver（外层）的关系：
    - AssetResolver：CLI 传 `customs/declare:v1.0` 进来 → 整张图 pull 出来
    - AssetMaterializer：把整张图里的 Ref 节点（可能内嵌）逐个替换

两件事在不同层互补。AssetResolver 拿到的是 ResolvedAsset（含整个
AssetContent）；本物化器再对该图做内层展开。
"""
from __future__ import annotations

from typing import Any, Set, Tuple, TYPE_CHECKING

from pydantic import BaseModel, TypeAdapter

from gimbal.exceptions import AssetCycleError, AssetMaterializationError
from gimbal.log import get_logger
from gimbal.schema.ref import Ref, RefBase

if TYPE_CHECKING:
    from gimbal.repository import AssetStore

logger = get_logger(__name__)


# ── 类型化 Ref → Pydantic 目标类的映射 ──────────────────────────────────────
# 物化器只识别顶层数据类；具体 Strategy / Resource 等子类的 discriminator
# 由 Pydantic 自己根据 kind 字段选。
#
# 新增类型化 Ref 时只需在此追加一行，**物化器代码本身不需要改**。


def _build_kind_to_adapter() -> dict[str, TypeAdapter]:
    """懒加载：构造 Ref class name → TypeAdapter 的映射。

    使用 TypeAdapter 而非直接 class：
      - StrategyRef 拉来的内容需要按 discriminator (kind) 选
        Extract / Assign / Assertion 子类，TypeAdapter(StrategyUnion) 才能处理
      - 普通 Ref（StepRef / ApiRef / RequestRef）也用 TypeAdapter 保持一致

    避免在 import 期就拉所有 schema 子模块（防止循环导入）。
    """
    from gimbal.schema.api import Api, ApiUnion
    from gimbal.schema.request import Request, RequestUnion
    from gimbal.schema.scenario import RunUnion
    from gimbal.schema.step import Step, StepUnion
    from gimbal.schema.strategy import StrategyUnion
    return {
        # 类型化 Ref 拉来的内容是单个对象（不含 *Ref 本身），
        # 所以适配的是去掉 Ref 后的 Union。
        "StepRef":      TypeAdapter(StepUnion),
        "ApiRef":       TypeAdapter(ApiUnion),
        "RequestRef":   TypeAdapter(RequestUnion),
        "StrategyRef":  TypeAdapter(StrategyUnion),
        # ScenarioRef / SuiteRef 共享 RunUnion —— 拉来的内容
        # kind="scenario" / kind="suite"，discriminator 会自动选 Scenario / Suite
        # （RunUnion 还含 ScenarioRef / SuiteRef 是为了 Pydantic 多态 schema 完整，
        # 实际 pulled content 是数据类本身，不会出现 *Ref 字段）
        "ScenarioRef":  TypeAdapter(RunUnion),
        "SuiteRef":     TypeAdapter(RunUnion),
    }


class AssetMaterializer:
    """引用物化器。

    用法::

        materializer = AssetMaterializer(asset_store=store, max_depth=8)
        materialized = materializer.materialize(scenario_obj)

    入参 obj 可以是：
      - Scenario / Step / Api / Request / Strategy ...（任意 BaseModel）
      - dict / list（free-form 容器）
      - 标量（str / int / float / bool / None）

    返回值结构与入参相同，只是 Ref 节点被替换为拉来的内容。
    """

    def __init__(
        self,
        asset_store: "AssetStore",
        *,
        max_depth: int = 8,
    ) -> None:
        self._store = asset_store
        self._max_depth = max_depth
        # 已处理的 (RefClassName, ref) 集合，用于显式环检测。
        # 推进时使用 frozenset 风格（用 | 构造新 set），不修改原集合
        # —— 兄弟分支互不污染。
        self._seen: Set[Tuple[str, str]] = set()
        self._ref_kind_to_adapter: dict[str, TypeAdapter] = _build_kind_to_adapter()
        logger.debug(
            "[AssetMaterializer] 初始化: store={} max_depth={} ref_kinds={}",
            type(asset_store).__name__, max_depth,
            list(self._ref_kind_to_adapter.keys()),
        )

    # ── 公开入口 ──────────────────────────────────────────────────────────────

    def materialize(self, obj: Any) -> Any:
        """递归物化整个对象，返回物化后的版本。"""
        logger.info("[AssetMaterializer] 开始物化: type={}", type(obj).__name__)
        result = self._walk(obj, depth=0, path="$")
        logger.info(
            "[AssetMaterializer] 物化完成: visited_refs={}",
            len(self._seen),
        )
        return result

    # ── 核心遍历 ──────────────────────────────────────────────────────────────

    def _walk(self, obj: Any, *, depth: int, path: str) -> Any:
        """根据 obj 类型分派到对应的处理方法。"""
        # 1. Ref 节点 → pull + 递归
        #    两种识别方式：
        #    a) Pydantic 模型实例（顶层类型化 Ref 一定走这条）
        #    b) raw dict 形态（Request.body: dict[str, Any] 里嵌的内联 Ref；
        #       Pydantic v2 不递归校验 free-form dict，需要结构识别）
        if isinstance(obj, RefBase) or self._looks_like_ref_dict(obj):
            ref_obj = self._coerce_to_ref(obj, path=path)
            return self._materialize_ref(ref_obj, depth=depth, path=path)

        # 2. Pydantic 模型 → 逐字段 walk
        if isinstance(obj, BaseModel):
            return self._walk_model(obj, depth=depth, path=path)

        # 3. dict → 逐 value walk
        if isinstance(obj, dict):
            return {
                k: self._walk(v, depth=depth, path=f"{path}.{k}")
                for k, v in obj.items()
            }

        # 4. list / tuple → 逐元素 walk
        if isinstance(obj, list):
            return [
                self._walk(v, depth=depth, path=f"{path}[{i}]")
                for i, v in enumerate(obj)
            ]
        if isinstance(obj, tuple):
            return tuple(
                self._walk(v, depth=depth, path=f"{path}[{i}]")
                for i, v in enumerate(obj)
            )

        # 5. 标量 / 未知类型 → 原样返回
        return obj

    # ── 结构识别：raw dict → Ref 节点 ──────────────────────────────────────

    @staticmethod
    def _looks_like_ref_dict(obj: Any) -> bool:
        """检查 obj 是否是 raw dict 形态的 Ref 节点。

        触发条件（同时满足）：
          - 是 dict
          - 有 'kind' 字段，且值是 "ref"（通用内联 Ref）
          - 有 'ref' 字段，且值是 str
        """
        if not isinstance(obj, dict):
            return False
        if obj.get("kind") != "ref":
            return False
        return isinstance(obj.get("ref"), str)

    @staticmethod
    def _coerce_to_ref(obj: Any, *, path: str) -> RefBase:
        """把 raw dict 转成 Ref Pydantic 实例。已是 Pydantic 则原样返回。"""
        if isinstance(obj, RefBase):
            return obj
        # 此时 _looks_like_ref_dict 已保证字段齐全
        return Ref(**obj)

    def _walk_model(self, model: BaseModel, *, depth: int, path: str) -> BaseModel:
        """对 Pydantic 模型逐字段 walk，原地替换字段值。

        直接修改入参对象并返回 —— 物化是一次性的预处理，不需要保留原图。
        （如需不可变，调用方应在物化前 model.model_copy(deep=True)）
        """
        for field_name in type(model).model_fields:
            current = getattr(model, field_name)
            if current is None:
                continue
            new_value = self._walk(
                current, depth=depth, path=f"{path}.{field_name}"
            )
            if new_value is not current:
                try:
                    setattr(model, field_name, new_value)
                except Exception as e:  # noqa: BLE001
                    # Pydantic v2 frozen 模型可能拒写
                    logger.warning(
                        "[AssetMaterializer] 字段替换失败: {}.{} err={}",
                        type(model).__name__, field_name, e,
                    )
        return model

    # ── Ref 物化 ──────────────────────────────────────────────────────────────

    def _materialize_ref(
        self, ref: RefBase, *, depth: int, path: str,
    ) -> Any:
        """pull ref 对应的资产，反序列化为目标对象，再递归处理拉来的内容。"""
        ref_cls_name = type(ref).__name__
        ref_key = (ref_cls_name, ref.ref)

        # 显式环检测：同一 (Class, ref) 在递归栈中出现两次 → 环
        if ref_key in self._seen:
            raise AssetCycleError(
                f"Ref cycle detected: {ref_cls_name}({ref.ref!r}) at {path}",
                ref=ref.ref, ref_class=ref_cls_name, path=path,
            )

        # 深度兜底：超过 max_depth → 视作环（不显式检测到但极深也是病）
        if depth >= self._max_depth:
            raise AssetCycleError(
                f"Ref nesting exceeded max_depth={self._max_depth} at {path}",
                depth=depth, ref=ref.ref, ref_class=ref_cls_name, path=path,
            )

        # 推进 visited —— 用新 set 替换，不污染兄弟分支
        previous_seen = self._seen
        self._seen = self._seen | {ref_key}
        try:
            # 1. pull
            from gimbal.repository import AssetRef
            try:
                asset_ref = AssetRef.parse(ref.ref)
            except Exception as e:
                raise AssetMaterializationError(
                    f"Invalid asset ref: {ref.ref!r}",
                    ref=ref.ref, path=path,
                ) from e

            logger.debug(
                "[AssetMaterializer] pull: ref={} path={} depth={}",
                ref.ref, path, depth,
            )
            try:
                content = self._store.pull(asset_ref)
            except Exception as e:
                raise AssetMaterializationError(
                    f"Failed to pull asset for ref: {ref.ref!r}",
                    ref=ref.ref, path=path,
                ) from e

            # 2. 反序列化 / 直接取 parsed
            materialized = self._deserialize(ref, content, path=path)

            # 3. 拉来的内容里可能又含 Ref → 递归 walk
            return self._walk(
                materialized, depth=depth + 1, path=path,
            )
        finally:
            # 恢复 seen，让本分支的推进不阻塞其他兄弟分支
            self._seen = previous_seen

    def _deserialize(
        self,
        ref: RefBase,
        content: Any,
        *,
        path: str,
    ) -> Any:
        """根据 ref 类型选择反序列化策略。

        - 通用 Ref（kind="ref"）：content.parsed 直接返回；parsed 为 None 时
          回退到 raw bytes 解码
        - 类型化 Ref：用映射表中对应 Pydantic 类 model_validate
        """
        # 通用内联 Ref —— 不反序列化
        if isinstance(ref, Ref):
            parsed = getattr(content, "parsed", None)
            if parsed is not None:
                return parsed
            raw = getattr(content, "raw", None)
            if raw is not None:
                return raw.decode("utf-8", errors="replace")
            raise AssetMaterializationError(
                f"Inline Ref has neither parsed nor raw content: {ref.ref!r}",
                ref=ref.ref, path=path,
            )

        # 类型化 Ref —— 查适配器
        adapter = self._ref_kind_to_adapter.get(type(ref).__name__)
        if adapter is None:
            raise AssetMaterializationError(
                f"Unknown typed Ref subclass: {type(ref).__name__}",
                ref_class=type(ref).__name__, ref=ref.ref, path=path,
            )

        parsed = getattr(content, "parsed", None)
        if parsed is None:
            raise AssetMaterializationError(
                f"Typed Ref requires JSON content (parsed is None): {ref.ref!r}",
                ref=ref.ref, ref_class=type(ref).__name__, path=path,
            )

        try:
            obj = adapter.validate_python(parsed)
        except Exception as e:
            raise AssetMaterializationError(
                f"Failed to deserialize {type(ref).__name__}({ref.ref!r}): {e}",
                ref=ref.ref, ref_class=type(ref).__name__, path=path,
            ) from e

        # adapter 是 *Union 形态，拉来的 Ref 节点自身（如 step_ref）不应再
        # 出现在结果里 —— Union 已剔除 Ref 子类，所以理论上 obj 不可能是
        # RefBase。保险起见做一次校验。
        if isinstance(obj, RefBase):
            raise AssetMaterializationError(
                f"Pulled content is itself a Ref: {type(obj).__name__}({obj.ref!r})",
                ref=ref.ref, ref_class=type(ref).__name__, path=path,
            )
        return obj


# ── 便捷函数 ────────────────────────────────────────────────────────────────


def materialize(
    obj: Any,
    asset_store: "AssetStore",
    *,
    max_depth: int = 8,
) -> Any:
    """一次性物化：构造 materializer 并跑一次。"""
    return AssetMaterializer(asset_store, max_depth=max_depth).materialize(obj)
