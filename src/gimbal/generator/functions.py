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


def _parse_base(base: str | None = None, base_format: str | None = None) -> datetime:
    """解析时间基准；未指定时使用当前本地时间。"""
    if base is None:
        return datetime.now()
    if base_format is not None:
        try:
            return datetime.strptime(base, base_format)
        except ValueError as exc:
            raise ValueError(
                f"invalid base time {base!r} for format {base_format!r}"
            ) from exc
    try:
        return datetime.fromisoformat(base)
    except ValueError:
        # 兼容用户常用的 ``YYYY-MM-DD HH:MM:SS`` 格式。
        try:
            return datetime.strptime(base, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise ValueError(
                f"invalid base time {base!r}; use ISO 8601 or provide base_format"
            ) from exc


def _format_timestamp(ts: datetime, format: str) -> int | str:
    if format == "epoch":
        return int(ts.timestamp())
    if format == "iso":
        return ts.isoformat()
    if format == "compact":
        return ts.strftime("%Y%m%d%H%M%S")
    if "%" in format:
        return ts.strftime(format)
    raise ValueError(f"invalid format: {format!r}")


def timestamp(
    format: str = "iso",
    offset_seconds: int = 0,
    base: str | None = None,
    base_format: str | None = None,
) -> int | str:
    """基准时间 + 秒级偏移；基准缺省为当前时间。"""
    ts = _parse_base(base, base_format) + timedelta(seconds=offset_seconds)
    return _format_timestamp(ts, format)


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
    base: str | None = None,
    base_format: str | None = None,
) -> int:
    """基准 Unix 秒 + 单位化偏移量；基准缺省为当前时间。"""
    if unit not in _VALID_OFFSET_UNITS:
        raise ValueError(f"invalid unit: {unit!r}")

    sign = 1 if direction == "future" else -1
    delta_value = value * sign
    base_time = _parse_base(base, base_format)

    if unit == "milliseconds":
        target = base_time + timedelta(seconds=delta_value / 1000.0)
    elif unit == "years":
        target = _shift_months(base_time, delta_value * 12)
    elif unit == "months":
        target = _shift_months(base_time, delta_value)
    else:
        kwarg = {_TIMEDELTA_UNIT_KEYWORD[unit]: delta_value}
        target = base_time + timedelta(**kwarg)

    return int(target.timestamp())
