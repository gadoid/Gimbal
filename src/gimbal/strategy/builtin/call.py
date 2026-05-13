from __future__ import annotations
 
import traceback
from typing import Any, TYPE_CHECKING
 
from gimbal.strategy.executor_base import StrategyExecutor, StrategyResult, StrategyStatus


class CallExecutor(StrategyExecutor):
    """执行 HTTP 调用，将响应存入 context。
 
    这个 executor 比较特殊：它不对应 schema 里的某个 Strategy 子类，
    而是由 ScenarioRunner 在 CALLING 阶段直接调用，
    传入一个内部合成的 _CallSpec。
    """
 
    kind = "_call"
 
    def execute(self, spec: "StrategyBase", view: "StrategyContextView") -> StrategyResult:
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
 
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if method.upper() not in ("GET", "HEAD") else None,
                    params=body if method.upper() in ("GET", "HEAD") else None,
                )
 
            # 将响应写入 scenario context，供后续 Extract 使用
            view.promote_variable("response_status", response.status_code, to=ContextLayer.SCENARIO)
            view.promote_variable("response_headers", dict(response.headers), to=ContextLayer.SCENARIO)
            try:
                resp_body = response.json()
            except Exception:
                resp_body = response.text
            view.promote_variable("response_body", resp_body, to=ContextLayer.SCENARIO)
 
            return StrategyResult(
                status=StrategyStatus.PASSED,
                message=f"HTTP {method} {url} → {response.status_code}",
                extracted={
                    "response_status": response.status_code,
                    "response_body": resp_body,
                },
            )
        except Exception as exc:
            return StrategyResult(
                status=StrategyStatus.ERROR,
                message=str(exc),
                error=traceback.format_exc(),
            )