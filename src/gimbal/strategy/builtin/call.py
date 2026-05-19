from __future__ import annotations

import logging
import traceback
from typing import Any, TYPE_CHECKING

from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus
from gimbal.context.step import HttpExchange
from gimbal.context.views import StepContextAdapter

logger = logging.getLogger(__name__)


class CallExecutor(StrategyExecutor):
    """执行 HTTP 调用，将响应存入 context。

    这个 executor 比较特殊：它不对应 schema 里的某个 Strategy 子类，
    而是由 ScenarioRunner 在 CALLING 阶段直接调用，
    传入一个内部合成的 _CallSpec。
    """

    kind = "_call"

    def execute(self, spec: "StrategyBase", view: "StepContextAdapter") -> StrategyResult:
        """
        spec 是内部 _CallSpec dataclass，包含：
          - method / url / headers / body / timeout
        执行成功后将 response_status / response_body / response_headers 写入 SCENARIO context。
        """
        try:
            import httpx
            from gimbal.context.base import ContextLayer

            method: str = spec.method        # type: ignore[attr-defined]
            url: str = spec.url              # type: ignore[attr-defined]
            headers: dict = spec.headers     # type: ignore[attr-defined]
            body: dict = spec.body           # type: ignore[attr-defined]
            timeout: float = spec.timeout    # type: ignore[attr-defined]

            logger.info("[CallExecutor] HTTP 请求开始: %s %s", method, url)
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if method.upper() not in ("GET", "HEAD") else None,
                    params=body if method.upper() in ("GET", "HEAD") else None,
                )

            logger.info("[CallExecutor] HTTP 响应: %s %s -> %d", method, url, response.status_code)

            # 将响应写入 scenario context，供后续 Extract 使用
            # view.promote_variable("response_status", response.status_code, to=ContextLayer.SCENARIO)
            # view.promote_variable("response_headers", dict(response.headers), to=ContextLayer.SCENARIO)
            # logger.info(f"{response.status_code}")
            view.write_http_exchange(response_status=response.status_code)
            # logger.info(f"{view.read_http_exchange("response_status")}")
            view.write_http_exchange(response_headers=response.headers)
            # logger.info(f"{view.read_http_exchange("response_headers")}")

            try:
                resp_body = response.json()
            except Exception:
                resp_body = response.text
            # view.promote_variable("response_body", resp_body, to=ContextLayer.SCENARIO)
            view.write_http_exchange(response_body=resp_body)
            logger.debug("[CallExecutor] 响应已写入 context: response_status=%s", response.status_code)

            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"HTTP {method} {url} -> {response.status_code}",
                extracted={
                    "response_status": response.status_code,
                    "response_body": resp_body,
                },
            )
        except httpx.TimeoutException as exc:
            logger.error("[CallExecutor] HTTP 请求超时: %s %s timeout=%.1fs", method, url, timeout)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=f"Request timeout: {exc}",
                error=traceback.format_exc(),
            )
        except httpx.RequestError as exc:
            logger.error("[CallExecutor] HTTP 请求失败: %s %s - %s", method, url, exc)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=f"Request error: {exc}",
                error=traceback.format_exc(),
            )
        except Exception as exc:
            logger.exception("[CallExecutor] HTTP 请求异常: %s %s", method, url)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )
