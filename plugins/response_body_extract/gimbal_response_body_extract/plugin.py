"""gimbal_response_body_extract/plugin.py

为每个执行的 step 自动注入"提取 response_body"的策略（默认 scope = STEP）。

设计要点
--------
- 复用框架的 hook 机制（HTTP_AFTER_RECV），不修改 step_schema.strategy。
- 在 HTTP 响应到达后、AFTER_REQUEST 阶段前，从 scratch 读 response_body
  并写到 target key（在 scratch 里，与 step 同生命周期）。
- 等价于追加一条 Extract 策略：
      Extract(
          phase=AFTER_REQUEST,
          expression="$.response_body",
          target=<config.target>,
          scope=STEP,        # 默认 scope
          onFailure=warn,
      )

可配置项
--------
- target       (str, default="response_body")  写入 scratch 的 key 名
- on_missing   (str, default="warn")           response_body 缺失时的策略
                                                "warn" = 记录 warning，不抛错
                                                "ignore" = 静默跳过
                                                "raise" = 抛 HookSignal.STOP（阻断 step）
- overwrite    (bool, default=True)            target 已存在时是否覆盖
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from gimbal.core.hooks import HookPoint, HookSignal
from gimbal.core.plugin import Plugin, PluginContext, PluginManifest

logger = logging.getLogger(__name__)


# ── 默认配置常量 ──────────────────────────────────────────────────

_DEFAULT_TARGET = "response_body"
_DEFAULT_ON_MISSING = "warn"   # "warn" | "ignore" | "raise"
_DEFAULT_OVERWRITE = True

_ALLOWED_ON_MISSING = ("warn", "ignore", "raise")


# ── 插件主类 ─────────────────────────────────────────────────────

class ResponseBodyExtractPlugin(Plugin):
    """为每个 step 自动注入"提取 response_body"的策略。"""

    manifest = PluginManifest(
        name="gimbal-response-body-extract",
        version="0.1.0",
        entry_point="gimbal_response_body_extract.plugin:ResponseBodyExtractPlugin",
        description=(
            "Auto-extract response_body from every executed step into a "
            "step-scoped scratch variable (default scope = STEP)."
        ),
        capabilities=["generic"],
        default_config={
            "target": _DEFAULT_TARGET,
            "on_missing": _DEFAULT_ON_MISSING,
            "overwrite": _DEFAULT_OVERWRITE,
        },
    )

    def __init__(self) -> None:
        super().__init__()
        # 运行时配置（在 on_activate 里从 ctx.config 读取）
        self._target: str = _DEFAULT_TARGET
        self._on_missing: str = _DEFAULT_ON_MISSING
        self._overwrite: bool = _DEFAULT_OVERWRITE

        # 简单统计：用于 debug / 日志
        self._stats = {
            "extracted": 0,
            "missing": 0,
            "overwritten": 0,
            "raised": 0,
        }

    # ── 生命周期 ──────────────────────────────────────

    def on_activate(self, ctx: PluginContext) -> None:
        """读取配置 + 订阅 HTTP_AFTER_RECV 钩子。"""
        cfg = ctx.config or {}

        # 读取并校验配置（合并 default_config 后用户可覆盖）
        target = cfg.get("target", _DEFAULT_TARGET)
        if not isinstance(target, str) or not target:
            logger.warning(
                "[ResponseBodyExtractPlugin] invalid target=%r, fallback to %r",
                target, _DEFAULT_TARGET,
            )
            target = _DEFAULT_TARGET

        on_missing = cfg.get("on_missing", _DEFAULT_ON_MISSING)
        if on_missing not in _ALLOWED_ON_MISSING:
            logger.warning(
                "[ResponseBodyExtractPlugin] invalid on_missing=%r, fallback to %r",
                on_missing, _DEFAULT_ON_MISSING,
            )
            on_missing = _DEFAULT_ON_MISSING

        overwrite = cfg.get("overwrite", _DEFAULT_OVERWRITE)
        overwrite = bool(overwrite)

        self._target = target
        self._on_missing = on_missing
        self._overwrite = overwrite

        # HTTP_AFTER_RECV 在每次 HTTP 调用返回后触发（AFTER_REQUEST 阶段前）。
        # 钩子触发顺序按 priority 升序；用默认 priority=100 即可。
        ctx.register_hook(
            HookPoint.HTTP_AFTER_RECV,
            self._handle_http_after_recv,
            description=(
                "Auto-extract response_body from scratch into target key "
                "(default scope = STEP)."
            ),
        )

        # 订阅 step.start / step.end 事件，方便日志统计与排查
        ctx.register_event("step.start", self._handle_step_start)
        ctx.register_event("step.end",   self._handle_step_end)

        logger.info(
            "[ResponseBodyExtractPlugin] activated: target=%r on_missing=%r overwrite=%s",
            self._target, self._on_missing, self._overwrite,
        )

    def on_deactivate(self) -> None:
        """卸载时打印一次统计。"""
        logger.info(
            "[ResponseBodyExtractPlugin] deactivated: stats=%s",
            self._stats,
        )

    # ── 钩子与事件 ──────────────────────────────────

    def _handle_http_after_recv(self, payload: Any) -> None:
        """HTTP_AFTER_RECV 钩子：从 scratch 读 response_body 并写到 target。

        payload 字段（由 engine.py 传入）：
            method, url, status, headers, body, duration_ms, step_id, ctx
        其中 ctx 是 StepContextAdapter（实现 StrategyContextView Protocol）。

        注：payload["body"] 通常是 None（StrategyResult 没有 body 属性），
        所以本钩子从 ctx.read_scratch("response_body") 取值——
        该值由 CallExecutor 在 HTTP 调用成功后写入 scratch。
        """
        if not isinstance(payload, dict):
            return

        ctx = payload.get("ctx")
        step_id = payload.get("step_id", "?")
        if ctx is None:
            logger.debug(
                "[ResponseBodyExtractPlugin] payload missing 'ctx', skip: step_id=%s",
                step_id,
            )
            return

        # 1. 从 scratch 读 response_body（CallExecutor 写入的）
        try:
            response_body = ctx.read_scratch("response_body")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[ResponseBodyExtractPlugin] read_scratch('response_body') failed: "
                "step_id=%s err=%s",
                step_id, exc,
            )
            response_body = None

        # 2. 处理缺失值
        if response_body is None:
            self._stats["missing"] += 1
            msg = (
                f"[ResponseBodyExtractPlugin] response_body not in scratch: "
                f"step_id={step_id}"
            )
            if self._on_missing == "warn":
                logger.warning(msg)
            elif self._on_missing == "ignore":
                logger.debug(msg)
            elif self._on_missing == "raise":
                self._stats["raised"] += 1
                logger.warning(msg)
                raise HookSignal.STOP("response_body missing")
            return

        # 3. 处理 overwrite
        if not self._overwrite:
            try:
                if ctx.read_scratch(self._target) is not None:
                    logger.debug(
                        "[ResponseBodyExtractPlugin] target=%r already set, skip "
                        "(overwrite=false): step_id=%s",
                        self._target, step_id,
                    )
                    return
            except Exception:  # noqa: BLE001
                # read_scratch 出错时按"未设置"处理
                pass
        else:
            try:
                if ctx.read_scratch(self._target) is not None:
                    self._stats["overwritten"] += 1
            except Exception:  # noqa: BLE001
                pass

        # 4. 写入 target（写入 scratch，等价于 STEP scope 的 Extract）
        try:
            ctx.write_scratch(self._target, response_body)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[ResponseBodyExtractPlugin] write_scratch(%r) failed: step_id=%s err=%s",
                self._target, step_id, exc,
            )
            return

        self._stats["extracted"] += 1
        logger.debug(
            "[ResponseBodyExtractPlugin] extracted response_body → scratch[%r]: "
            "step_id=%s body_type=%s",
            self._target, step_id, type(response_body).__name__,
        )

    def _handle_step_start(self, event: Any) -> None:
        """step.start 事件：仅用于日志（每 step 开始时打印一次 hint）。"""
        step_id = getattr(event, "step_id", "?")
        scenario_id = getattr(event, "scenario_id", "?")
        logger.debug(
            "[ResponseBodyExtractPlugin] step.start: scenario_id=%s step_id=%s "
            "(target scratch key = %r)",
            scenario_id, step_id, self._target,
        )

    def _handle_step_end(self, event: Any) -> None:
        """step.end 事件：仅用于日志（每 step 结束时打印一次状态）。"""
        step_id = getattr(event, "step_id", "?")
        status = getattr(event, "status", "?")
        logger.debug(
            "[ResponseBodyExtractPlugin] step.end: step_id=%s status=%s stats=%s",
            step_id, status, self._stats,
        )

    # ── 调试用 ──────────────────────────────────────────

    @property
    def stats(self) -> dict:
        """暴露当前统计，便于测试断言。"""
        return dict(self._stats)