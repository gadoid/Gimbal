"""cron_expr — 最小 5 段 cron 解析(集成任务触发周期)。

《GIMBAL-外部系统集成架构设计》§4 ``trigger_cron``。只做平台需要的
子集:每段支持 ``*``、``*/n``、``a``、``a-b``、``a-b/n`` 与逗号列表
组合(如 ``0 8-18/2 * * 1-5``);不支持的写法 ValueError(保存时
校验,前端提示)。命名( JAN/MON )与 7 段 cron 不做 —— 集成触发
用不到,避免引入 croniter 依赖。

纯函数、无 IO;``next_fire`` 最多向前探 4 年(366×4 天)兜底,
2/29 这类「一年最多出现一次」的位面也能算出。
"""
from __future__ import annotations

from datetime import datetime, timedelta

_FIELDS = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day_of_month", 1, 31),
    ("month", 1, 12),
    ("day_of_week", 0, 6),   # 0=周日(cron 传统语义;isoweekday()%7
                              # 恰好把周一..周日映到 1..6,0)
)
_FIELD_NAMES = " ".join(f[0] for f in _FIELDS)


class CronError(ValueError):
    """cron 表达式不合法(保存时 422)。"""


def _parse_field(spec: str, lo: int, hi: int, name: str) -> set[int]:
    values: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            raise CronError(f"cron {name} 段为空: {spec!r}")
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            try:
                step = int(step_s)
            except ValueError:
                raise CronError(f"cron {name} 步长非整数: {spec!r}") from None
            if step < 1:
                raise CronError(f"cron {name} 步长须 ≥1: {spec!r}")
        if part == "*":
            start, end = lo, hi
        elif "-" in part and not part.startswith("-"):
            a, b = part.split("-", 1)
            try:
                start, end = int(a), int(b)
            except ValueError:
                raise CronError(f"cron {name} 范围非整数: {spec!r}") from None
        else:
            try:
                start = end = int(part)
            except ValueError:
                raise CronError(f"cron {name} 非整数: {spec!r}") from None
        if start < lo or end > hi or start > end:
            raise CronError(
                f"cron {name} 越界({lo}-{hi}): {spec!r}")
        values.update(range(start, end + 1, step))
    if not values:
        raise CronError(f"cron {name} 段为空集: {spec!r}")
    return values


def parse_cron(expr: str) -> tuple[set[int], set[int], set[int],
                                   set[int], set[int]]:
    """解析 5 段 cron → (minute, hour, dom, month, dow) 取值集合。"""
    expr = (expr or "").strip()
    parts = expr.split()
    if len(parts) != 5:
        raise CronError(
            f"cron 须为 5 段(分 时 日 月 周),如 '*/5 * * * *': {expr!r}")
    return tuple(  # type: ignore[return-value]
        _parse_field(p, lo, hi, n)
        for p, (n, lo, hi) in zip(parts, _FIELDS)
    )


def next_fire(expr: str, after: datetime) -> datetime:
    """``after`` 之后(不含)的下一个触发时刻。naive/aware 均按原样
    对待(调用方统一用 naive UTC)。最多前探 4 年,兜底 2/29 位面。"""
    minutes, hours, doms, months, dows = parse_cron(expr)
    t = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
    limit = t + timedelta(days=366 * 4)
    while t < limit:
        if (t.minute in minutes and t.hour in hours and t.month in months
                and t.day in doms and t.isoweekday() % 7 in dows):
            return t
        # 分段跳:月不对 → 跳到下月 1 日 0 分;日/周不对 → 跳到明天
        # 0 点;只差分钟 → 逐分(触发密度上限 = 每分钟)
        if t.month not in months:
            y, m = (t.year + 1, 1) if t.month == 12 else (t.year, t.month + 1)
            t = t.replace(year=y, month=m, day=1, hour=0, minute=0)
        elif t.day not in doms or t.isoweekday() % 7 not in dows:
            t = (t.replace(hour=0, minute=0) + timedelta(days=1))
        elif t.hour not in hours:
            t = t.replace(minute=0) + timedelta(hours=1)
        else:
            t += timedelta(minutes=1)
    raise CronError(f"cron 在 4 年内无触发时刻: {expr!r}")


def describe_cron(expr: str) -> str:
    """人话摘要(卡片/列表副文案;不求全,求可读)。"""
    minutes, hours, doms, months, dows = parse_cron(expr)
    parts = expr.split()
    if parts[0].startswith("*/") and all(p == "*" for p in parts[1:]):
        return f"每 {parts[0][2:]} 分钟"
    if parts[0] != "*" and parts[1].startswith("*/") and \
            all(p == "*" for p in parts[2:]):
        return f"每 {parts[1][2:]} 小时的第 {sorted(minutes)[0]} 分"
    if set(parts[1]) == {"*"} and parts[0] != "*":
        hh = "每天" if len(hours) == 1 else f"每天 {sorted(hours)} 时"
        return f"{hh} {sorted(minutes)} 分"
    # 周位面:周一到周五
    if dows == {0, 1, 2, 3, 4} and months == set(range(1, 13)) and \
            doms == set(range(1, 32)):
        return f"工作日 {sorted(hours)} 时 {sorted(minutes)} 分"
    return expr
