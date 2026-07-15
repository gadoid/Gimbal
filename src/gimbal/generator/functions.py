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


def random_decorated_str(
    length: int = 8,
    charset: str = "alnum",
    head: str = "",
    tail: str = "",
    separator: str = "",
) -> str:
    """带前后缀与连接符的随机字符串。

    用"高基数随机"——一个独立的 random.choices 调用，避免复用 random_str 时的
    任何状态耦合。

    输出形式：head + separator + 核心随机串 + separator + tail

    Examples::

        random_decorated_str(length=4, charset="alnum", head="BL", tail="CN", separator="-")
        # → "BL-a3kP-CN"

        random_decorated_str(length=8, charset="digit")  # head/tail/sep 全空
        # → "a3kPm2xQ"（等价于 random_str(length=8, charset="digit")）
    """
    # 复用 random_str 的 charset→pool 映射，保证 charset 校验口径一致
    core = random_str(length=length, charset=charset)
    return f"{head}{separator}{core}{separator}{tail}"


# time_offset 单位集合
# 注意：milliseconds 在 Python 3.10+ 的 datetime 中并未作为 timedelta 关键字直接支持，
# 我们用 seconds=msec/1000 来表达；months / years 在 datetime 中无原生支持，按"日历月"
# 手算（见 _shift_months）。
_VALID_OFFSET_UNITS = (
    "milliseconds", "seconds", "minutes", "hours",
    "days", "weeks", "months", "years",
)

# time_offset 单位 → timedelta 关键字参数的映射（仅适用于"固定长度"单位）
_TIMEDELTA_UNIT_KEYWORD = {
    "seconds": "seconds",
    "minutes": "minutes",
    "hours": "hours",
    "days": "days",
    "weeks": "weeks",
}


def _shift_months(dt: datetime, months: int) -> datetime:
    """在 ``dt`` 上按"日历月"做偏移，月末溢出时夹到目标月最后一天。

    之所以手写而非引入 ``dateutil.relativedelta``：
      - 项目时间工具此前只用 Python 标准库 + pydantic（无第三方时间库）
      - 逻辑简单，跨年/跨闰年的 corner case 可控
      - 保持零新增依赖

    行为约定：
      - ``Jan 31 + 1 month`` → ``Feb 28``（非闰年）/ ``Feb 29``（闰年）
      - ``Mar 31 + (-1) month`` → ``Feb 28/29``（同向上面）
      - 跨年正常推进（例如 ``Nov 10 + 3 months`` → 次年 ``Feb 10``）

    Examples::

        _shift_months(datetime(2026, 1, 15),  1)  == datetime(2026, 2, 15)
        _shift_months(datetime(2026, 1, 31),  1)  == datetime(2026, 2, 28)
        _shift_months(datetime(2024, 3, 31), -1)  == datetime(2024, 2, 29)
        _shift_months(datetime(2026, 11, 10), 3)  == datetime(2027, 2, 10)
    """
    total_months = dt.year * 12 + (dt.month - 1) + months
    new_year, new_month0 = divmod(total_months, 12)
    new_month = new_month0 + 1
    # 目标月最后一天：利用"下月第 0 天 = 上月最后一天"
    if new_month == 12:
        last_day = 31
    else:
        last_day = (datetime(new_year, new_month + 1, 1) - timedelta(days=1)).day
    new_day = min(dt.day, last_day)
    return dt.replace(year=new_year, month=new_month, day=new_day)


def time_offset(
    unit: str = "seconds",
    value: int = 0,
    direction: str = "future",
) -> int:
    """当前 unix 秒 + 单位化偏移量。

    支持单位：
      - 固定长度：milliseconds / seconds / minutes / hours / days / weeks
      - 日历长度：months / years（按真实日历算，月末溢出夹到目标月最后一天）

    输出恒为 int（unix 秒）。format 由下游 strategy / render 决定，本函数
    不参与字符串格式化。

    Examples::

        time_offset(unit="days",   value=30, direction="future")
        time_offset(unit="hours",  value=2,  direction="past")
        time_offset(unit="months", value=6,  direction="future")
        time_offset(unit="years",  value=1,  direction="future")
        time_offset(unit="milliseconds", value=500)
        time_offset()  # 当前 unix 秒
    """
    if unit not in _VALID_OFFSET_UNITS:
        raise ValueError(f"invalid unit: {unit!r}")

    sign = 1 if direction == "future" else -1
    delta_value = value * sign
    now = datetime.now()

    if unit == "milliseconds":
        # timedelta 不直接接收 milliseconds 关键字，转 seconds
        target = now + timedelta(seconds=delta_value / 1000.0)
    elif unit == "years":
        target = _shift_months(now, delta_value * 12)
    elif unit == "months":
        target = _shift_months(now, delta_value)
    else:
        kwarg = {_TIMEDELTA_UNIT_KEYWORD[unit]: delta_value}
        target = now + timedelta(**kwarg)

    return int(target.timestamp())
