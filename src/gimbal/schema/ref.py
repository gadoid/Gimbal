"""gimbal/schema/ref.py

所有"引用"模型的基类 + 通用内联引用。

本文件只定义两层：

  - `RefBase`（基类，只有 `ref: str` 字段）
  - `Ref`（通用内联引用：kind="ref"，可出现在 dict / list 任意位置）

类型化 Ref（`StepRef` / `ApiRef` / `RequestRef` / `StrategyRef` /
`ScenarioRef` / `SuiteRef`）由各自的领域模块定义，因为它们的反序列化
目标（StepUnion / ApiUnion / ...）就定义在那里：

    - `gimbal.schema.step.StepRef`
    - `gimbal.schema.api.ApiRef`
    - `gimbal.schema.request.RequestRef`
    - `gimbal.schema.strategy.StrategyRef`
    - `gimbal.schema.scenario.ScenarioRef` / `SuiteRef`

区分要点：
  - 类型化 Ref：RefBase 的子类 + 自己的 kind discriminator（如 "step_ref"）。
    物化时用对应 Pydantic 类反序列化，整对象替换父节点对应字段。
  - 通用 Ref（kind="ref"）：物化时把 AssetContent.parsed 直接塞回原位置，
    不做反序列化（parsed 本身可能是 dict / list / str / int）。

识别规则：
    `isinstance(x, RefBase)` 为 true 即视为待实例化节点；
    解释器 (gimbal.core.asset_materializer.AssetMaterializer) 不区分具体类型，
    统一按"pull + 替换"处理。
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class RefBase(BaseModel):
    """所有引用模型的基类。

    子类必须：
      1. 用 `kind` 字段声明自己的 discriminator（便于 Pydantic 多态反序列化）
      2. 通过 `ref` 字段（继承自本类）声明要拉取的 asset ref 字符串
    """
    ref: str = Field(..., description="asset ref 字符串，格式 namespace/name:tag 或 namespace/name@digest")


class Ref(RefBase):
    """通用内联引用：可出现在 dict / list 任意位置的待实例化占位符。

    示例::

        {
            "order_id": {"kind": "ref", "ref": "smoke/order-id-pool:latest"},
            "items": [
                {"sku": "A1"},
                {"kind": "ref", "ref": "smoke/cart-line-template:v1"}
            ]
        }

    物化后变成::

        {
            "order_id": "real-id-12345",
            "items": [
                {"sku": "A1"},
                {"sku": "B2", "qty": 2, ...}      # 拉来的内容直接塞回
            ]
        }

    与类型化 Ref 的区别：
      - 不指定 Pydantic 目标类
      - AssetContent.parsed 直接覆盖（parsed 是 None 时回退到 raw bytes）
    """
    kind: Literal["ref"] = "ref"


if __name__ == "__main__":
    # 测试 RefBase 实例化
    ref = RefBase(ref="test_ref")
    print(f"RefBase 测试: ref={ref.ref}")

    # 测试通用内联 Ref
    inline = Ref(ref="smoke/order-id-pool:latest")
    print(f"Ref 测试: kind={inline.kind} ref={inline.ref}")
