"""events/subscribe.py — 订阅规格编译与挂载（P1-04）。

``compile_subscribe`` 校验规格（未知 sink / 事件类型 / where 键 →
CompileError[SUBSCRIBE_INVALID]）；``attach`` 把每条规则落到两处：

  - events：InMemoryEventBus 订阅（事件类型模式 + where 属性匹配），
    命中即按 jsonl 同款形状写 sink（未设标签剥除，与 stdout 事件流一致）；
  - logs：loguru sink（级别下限 + category/where 过滤），行带 category
    与执行上下文标签（JsonSink 同款字段）。

CLI（--subscribe）、suite 配置（graph.subscribe）、server（RunsRequest.
subscribe）共用本模块 —— 同一份规格在任何入口产生相同的输出。
"""
from __future__ import annotations

import fnmatch
import json
import sys
from dataclasses import dataclass, field
from typing import Any

from gimbal.compiler.errors import CompileError, ErrCode
from gimbal.log.category import CATEGORIES, categorize_logger
from gimbal.log.exec_context import EXEC_LABEL_NAMES, exec_labels
from gimbal.schema.subscribe import (
    EVENT_WHERE_FIELDS, SubscribeSpec, normalize_subscribe_spec,
)


def _known_event_types() -> set[str]:
    from gimbal.events.types import known_event_types
    return known_event_types()


_LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")


def compile_subscribe(raw: Any) -> SubscribeSpec:
    """校验并归一订阅规格；非法即 CompileError（SUBSCRIBE_INVALID）。"""
    try:
        spec = normalize_subscribe_spec(raw)
    except Exception as e:  # noqa: BLE001  # 形状/pydantic 校验失败统一翻译
        raise CompileError(f"subscribe 规格非法: {e}", code=ErrCode.SUBSCRIBE_INVALID) from e

    known_events = _known_event_types()
    valid_where = set(EXEC_LABEL_NAMES) | set(EVENT_WHERE_FIELDS)
    for i, rule in enumerate(spec):
        if rule.sink == "file:":
            raise CompileError(
                f"subscribe[{i}].sink 非法: file: 后缺路径",
                code=ErrCode.SUBSCRIBE_INVALID)
        if rule.sink not in ("stdout", "stderr") and not rule.sink.startswith("file:"):
            raise CompileError(
                f"subscribe[{i}].sink 非法: {rule.sink!r}（合法: stdout | stderr | file:<path>）",
                code=ErrCode.SUBSCRIBE_INVALID)
        if rule.events is None and rule.logs is None:
            raise CompileError(
                f"subscribe[{i}] 未声明任何选择（events/logs 至少其一）",
                code=ErrCode.SUBSCRIBE_INVALID)
        for et in rule.events or []:
            if not any(ch in et for ch in "*?[") and et not in known_events:
                raise CompileError(
                    f"subscribe[{i}].events 未知事件类型: {et!r}"
                    f"（已知 {len(known_events)} 种；模式请用通配符，如 'step.*'）",
                    code=ErrCode.SUBSCRIBE_INVALID)
        for key in rule.where:
            if key not in valid_where:
                raise CompileError(
                    f"subscribe[{i}].where 未知键: {key!r}"
                    f"（合法: 执行上下文标签 {list(EXEC_LABEL_NAMES)}"
                    f" 或事件字段 {list(EVENT_WHERE_FIELDS)}）",
                    code=ErrCode.SUBSCRIBE_INVALID)
        if rule.logs is not None:
            if rule.logs.level is not None and rule.logs.level.upper() not in _LEVELS:
                raise CompileError(
                    f"subscribe[{i}].logs.level 非法: {rule.logs.level!r}（合法: {_LEVELS}）",
                    code=ErrCode.SUBSCRIBE_INVALID)
            if rule.logs.category is not None and not any(
                    fnmatch.fnmatchcase(c, rule.logs.category) for c in CATEGORIES):
                raise CompileError(
                    f"subscribe[{i}].logs.category 非法: {rule.logs.category!r}"
                    f"（词表: {list(CATEGORIES)}）",
                    code=ErrCode.SUBSCRIBE_INVALID)
    return spec


# ── where 匹配与行序列化 ────────────────────────────────────────

def _where_matches(event: Any, where: dict[str, str]) -> bool:
    """事件的 where 匹配：键取事件属性（执行上下文标签 + 事件自有字段），
    值 fnmatch 通配；缺失属性不匹配。"""
    for key, pattern in where.items():
        value = getattr(event, key, None)
        if value is None or not fnmatch.fnmatchcase(str(value), pattern):
            return False
    return True


def _event_line(event: Any) -> str:
    """jsonl 同款单行（未设执行上下文标签剥除，与 cli/common.py 一致）。"""
    try:
        d = event.model_dump(mode="json")
        for label in EXEC_LABEL_NAMES:
            if d.get(label) is None:
                d.pop(label, None)
        return json.dumps(d, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return json.dumps({"event_type": getattr(event, "event_type", "?")})


@dataclass
class AttachedSubscriptions:
    """attach 的反向句柄：detach 撤销全部订阅、loguru sink 与文件句柄。"""
    _bus: Any = None
    _subscription_ids: list[str] = field(default_factory=list)
    _loguru_sink_ids: list[int] = field(default_factory=list)
    _files: list = field(default_factory=list)

    def detach(self) -> None:
        for sid in self._subscription_ids:
            try:
                self._bus.unsubscribe(sid)
            except Exception:  # noqa: BLE001
                pass
        self._subscription_ids.clear()
        if self._loguru_sink_ids:
            from loguru import logger as _root
            for sid in self._loguru_sink_ids:
                try:
                    _root.remove(sid)
                except Exception:  # noqa: BLE001
                    pass
            self._loguru_sink_ids.clear()
        for fh in self._files:
            try:
                fh.close()
            except Exception:  # noqa: BLE001
                pass
        self._files.clear()


def attach(spec: SubscribeSpec, event_bus: Any) -> AttachedSubscriptions:
    """把编译后的规格挂到 event_bus（+ loguru 根 logger）；返回 detach 句柄。"""
    attached = AttachedSubscriptions(_bus=event_bus)

    def _writer(sink: str):
        if sink == "stdout":
            def write(line: str) -> None:
                print(line, file=sys.stdout, flush=True)
            return write
        if sink == "stderr":
            def write(line: str) -> None:  # noqa: F811
                print(line, file=sys.stderr, flush=True)
            return write
        fh = open(sink[len("file:"):], "a", encoding="utf-8")
        attached._files.append(fh)

        def write(line: str) -> None:  # noqa: F811
            fh.write(line + "\n")
            fh.flush()
        return write

    for rule in spec:
        write = _writer(rule.sink)

        # ① 事件订阅（events 声明时）
        if rule.events is not None:
            patterns = tuple(rule.events)

            def _handler(event, _patterns=patterns, _where=rule.where, _write=write) -> None:
                et = getattr(event, "event_type", "") or ""
                if _patterns and not any(fnmatch.fnmatchcase(et, p) for p in _patterns):
                    return
                if _where and not _where_matches(event, _where):
                    return
                _write(_event_line(event))

            attached._subscription_ids.append(event_bus.subscribe(_handler))

        # ② 日志订阅（logs 声明时）：loguru 可调用 sink，行经 write 落通道
        if rule.logs is not None:
            from loguru import logger as _root
            level = rule.logs.level.upper() if rule.logs.level else "DEBUG"
            category_pat = rule.logs.category
            where = rule.where

            def _sink_filter(record) -> bool:
                name = (record.get("extra", {}).get("name")
                        or record.get("name") or record.get("module", ""))
                if category_pat and not fnmatch.fnmatchcase(
                        categorize_logger(name), category_pat):
                    return False
                if where:
                    labels = exec_labels()
                    for key, pattern in where.items():
                        value = labels.get(key)
                        if value is None or not fnmatch.fnmatchcase(str(value), pattern):
                            return False
                return True

            def _sink_write(message) -> None:
                record = message.record
                name = (record.get("extra", {}).get("name")
                        or record.get("name") or record.get("module", ""))
                payload = {
                    "timestamp": record["time"].isoformat(),
                    "level": record["level"].name,
                    "logger": name,
                    "category": categorize_logger(name),
                    "message": record["message"],
                    **exec_labels(),
                }
                write(json.dumps(payload, ensure_ascii=False, default=str))

            attached._loguru_sink_ids.append(
                _root.add(_sink_write, level=level, filter=_sink_filter))

    return attached
