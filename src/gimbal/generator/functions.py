"""gimbal/generator/functions.py

7 个内置生成函数（pure function）。
每个函数接收**命名参数**（参数名与 Spec 字段一一对应），返回 primitive 值。
"""
from __future__ import annotations

import random
import string
import uuid as _uuid
from datetime import datetime, timedelta


def uuid() -> str:
    """32 位 hex。"""
    return _uuid.uuid4().hex


def random_str(length: int = 8, charset: str = "alnum") -> str:
    """随机字符串。"""
    pools = {
        "alpha": string.ascii_letters,
        "digit": string.digits,
        "alnum": string.ascii_letters + string.digits,
    }
    if charset not in pools:
        raise ValueError(f"invalid charset: {charset!r}")
    return "".join(random.choices(pools[charset], k=length))


def random_int(min: int = 0, max: int = 100) -> int:
    """闭区间随机整数。"""
    if min > max:
        raise ValueError(f"min ({min}) > max ({max})")
    return random.randint(min, max)


def random_decimal(min: float = 0.0, max: float = 100.0, places: int = 2) -> float:
    """闭区间随机小数，四舍五入到指定位数。"""
    if min > max:
        raise ValueError(f"min ({min}) > max ({max})")
    return round(random.uniform(min, max), places)


def timestamp(format: str = "iso", offset_seconds: int = 0) -> int | str:
    """当前时间 + 偏移。"""
    ts = datetime.now() + timedelta(seconds=offset_seconds)
    if format == "epoch":
        return int(ts.timestamp())
    if format == "iso":
        return ts.isoformat()
    if format == "compact":
        return ts.strftime("%Y%m%d%H%M%S")
    raise ValueError(f"invalid format: {format!r}")


def now(format: str = "iso") -> int | str:
    """当前时间（无偏移）。"""
    return timestamp(format=format, offset_seconds=0)


# seq 用模块级计数器；不跨进程、不跨 run、不线程安全
_seq_counter: dict[str, int] = {}


def seq(prefix: str = "", width: int = 6, start: int = 1) -> str:
    """自增序号 + 业务前缀；同 (prefix, width, start) 组合下递增。"""
    key = f"{prefix}|{width}|{start}"
    if key not in _seq_counter:
        _seq_counter[key] = start
    else:
        _seq_counter[key] += 1
    return f"{prefix}{_seq_counter[key]:0{width}d}"


def reset_seq_counter() -> None:
    """重置 seq 计数器（多进程跑前 / 测试隔离用）。"""
    _seq_counter.clear()
