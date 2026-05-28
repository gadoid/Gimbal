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
        method = spec.method
        url = spec.url
        headers = spec.headers
        body = spec.body
        timeout = spec.timeout

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
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if method.upper() not in ("GET", "HEAD") else None,
                    params=body if method.upper() in ("GET", "HEAD") else None,
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
