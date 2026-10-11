"""M2 代际迁移（M2 方案 §5.2）：migrate(gen_n → gen_n+1) 纯函数。

迁移函数随不兼容变更同一提交入库;平台迁移脚本与 CLI 调 plate 的
``POST /api/m2/action/migrate`` 统一入口,不自写转换逻辑。
当前代际 = 1（首次反转）,无历史迁移;gen ≥ 2 的迁移函数按
``_migrate_map`` 注册——键 = 起始代际,值 = 该代际的纯函数变换。
"""
from __future__ import annotations

from typing import Any, Callable

# gen_n → gen_n+1 的迁移函数注册表;当前 gen=1,表为空
_migrate_map: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def migrate_definition(
    definition: dict[str, Any], from_generation: int,
) -> dict[str, Any]:
    """把一份 M2 实例从 from_generation 迁移到当前代际。

    纯函数：不修改入参,返回新 dict;逐代应用 _migrate_map 中的变换。
    未注册的代际跳跃 → ValueError(迁移函数须随不兼容变更入库)。
    """
    from gimbal_plate.schema import M2_GENERATION
    out = dict(definition)
    gen = from_generation
    while gen < M2_GENERATION:
        fn = _migrate_map.get(gen)
        if fn is None:
            raise ValueError(
                f"migrate_function_missing: gen {gen} → {gen + 1} "
                f"(迁移函数须随不兼容变更同一提交入库,M2 §5.2)")
        out = fn(out)
        gen += 1
    return out


def register_migrate(
    from_gen: int,
) -> Callable[[Callable], Callable]:
    """装饰器:注册 gen_n → gen_n+1 的迁移函数。"""
    def decorator(fn: Callable) -> Callable:
        _migrate_map[from_gen] = fn
        return fn
    return decorator
