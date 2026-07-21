from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus

from gimbal.log import get_logger
logger = get_logger(__name__)


class CallExecutor(StrategyExecutor):
    """执行 HTTP 调用，将响应存入 scratch。

    这个 executor 比较特殊：它不对应 schema 里的某个 Strategy 子类，
    而是由 ScenarioRunner 在 CALLING 阶段直接调用，
    传入一个内部合成的 _CallSpec。
    """

    kind = "_call"

    def execute(self, spec, view) -> StrategyResult:
        """执行 HTTP 调用策略：基于 spec.method/url/headers/timeout 发出请求，把响应 status/headers/body 写入 view scratch。"""
        method = spec.method
        url = spec.url
        headers = spec.headers
        timeout = spec.timeout
        # 如果 scratch 中没有 request_body，先用 spec.body 初始化
        # 注意：用 `is None` 而非 `not ...` —— 空 dict / 空 list 是合法的 request body，
        # 不应被 falsy 判定重新覆盖。
        if view.read_scratch("request_body") is None:
            view.write_scratch("request_body", spec.body)
        # 从 scratch 读取实时渲染的 request_body（可能被 Assign 等策略修改过）
        body = view.read_scratch("request_body")

        try:
            import httpx
            import time

            logger.info("[CallExecutor] HTTP 请求: {} {}", method, url)

            # 请求数据写入 scratch
            view.write_scratch("request_method", method)
            view.write_scratch("request_url", url)
            view.write_scratch("request_headers", headers)
            view.write_scratch("request_body", body)

            t_start = time.monotonic()
            with httpx.Client(timeout=timeout) as client:
                # body 形态分发（阶段 1：新增 str 形态支持）：
                #   GET/HEAD  → params=  （向后兼容：dict/list/str 都走 query string）
                #   str body  → content= （原始文本通道，Content-Type 由 api.headers 控制）
                #   dict/list  → json=    （Content-Type: application/json，httpx 兜底）
                # 互斥传递：httpx 接受同时传 json= 和 content= 但后者会覆盖前者，
                # 所以必须 if/elif/else 分发，不能传多个参数。
                method_upper = method.upper()
                if method_upper in ("GET", "HEAD"):
                    response = client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=body,
                    )
                elif isinstance(body, str):
                    # str body：原始文本通道
                    # Content-Type 完全由调用方在 api.headers 显式声明；
                    # 若未声明，httpx 默认 text/plain，建议显式。
                    if not headers or "Content-Type" not in headers:
                        logger.warning(
                            "[CallExecutor] str body 但 headers 缺少 Content-Type，"
                            "httpx 将使用 text/plain 兜底；"
                            "建议在 api.headers 显式声明（如 text/xml、application/xml）"
                        )
                    response = client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        content=body.encode("utf-8"),
                    )
                else:
                    # dict/list：JSON 通道
                    response = client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=body,
                    )
            duration_ms = (time.monotonic() - t_start) * 1000

            logger.info(
                "[CallExecutor] HTTP 响应: {} {} -> {} ({:.1f}ms)",
                method, url, response.status_code, duration_ms
            )

            try:
                resp_body = response.json()
            except Exception:
                resp_body = response.text

            # 响应数据写入 scratch
            view.write_scratch("response_status", response.status_code)
            view.write_scratch("response_headers", dict(response.headers))
            view.write_scratch("response_body", resp_body)
            view.write_scratch("duration_ms", duration_ms)

            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"HTTP {method} {url} -> {response.status_code}",
                extracted={
                    "response_status": response.status_code,
                    "response_body": resp_body,
                },
            )

        except httpx.TimeoutException as exc:
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=f"Request timeout: {exc}",
                error=traceback.format_exc(),
            )
        except httpx.RequestError as exc:
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=f"Request error: {exc}",
                error=traceback.format_exc(),
            )
        except Exception as exc:
            logger.exception("[CallExecutor] 异常: {} {}", method, url)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )
