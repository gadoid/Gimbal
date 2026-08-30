"""common 通用层的装配入口(与 fin 的 dimensions.py 对称)。

集中 common 自己拥有的注册动作:
- 声明 common 系统(无 endpoint 的声明式系统 — registry 内核能力)
- 播种 ``common.default`` config / meta 通用默认

设计意图:
    - common 是"通用层"而非业务系统:meta 的默认结构在通用层管理,
      不放进每个业务系统下;config 通用项(timePolicy/retry)同样如此。
    - 此函数是 common 的私有装配入口,被生产路径
      ``gimbal_plate.http.app._lifespan`` 调用,也被测试路径
      ``tests/plate/conftest.py:fresh_registry`` 调用(与
      ``register_fin_dims`` 同一收敛模式,防生产/测试 drift)。
    - dim 本身(config/meta)是全局单例,由 ``register_fin_dims``
      先注册;本函数只往已有 dim 的 index 里播种,调用顺序须在
      ``register_fin_dims`` 之后。

调用方:
    from gimbal_plate.systems.common.dimensions import register_common_dims
    register_common_dims(reg)
"""
from __future__ import annotations

from gimbal_plate.registry import PlateRegistry
from gimbal_plate.systems.common.config import common_config_template
from gimbal_plate.systems.common.meta import common_meta_template

# common 通用层的系统标识(与 fin 的 FIN_SYSTEM 同一定位)。
COMMON_SYSTEM = "common"


def register_common_dims(reg: PlateRegistry) -> None:
    """声明 common 系统 + 播种 ``common.default`` config/meta 通用默认。

    幂等性由 registry.declare_system 与各 index 的 ``register``
    (同 key 覆盖写)保证。
    """
    reg.declare_system(
        COMMON_SYSTEM,
        name=COMMON_SYSTEM,
        description="通用默认系统配置(跨系统场景的通用层)",
    )
    config_spec = reg.index_for("config")
    meta_spec = reg.index_for("meta")
    config_spec.index.register(
        common_config_template(), item_id=f"{COMMON_SYSTEM}.default"
    )
    # 通用 meta 默认:版本/expire/requirementRef 等公共项来自模板;
    # name/description/module/author 等 per-scenario 字段给中性空值,
    # 由编排者填写(预填不为难用户删占位符)。
    meta_spec.index.register(
        common_meta_template(
            name="",
            description="",
            module="",
            priority=1,
            author="",
            owner="",
            tags=[],
            system=[COMMON_SYSTEM],
        ),
        item_id=f"{COMMON_SYSTEM}.default",
    )
