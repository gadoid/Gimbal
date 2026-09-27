"""protocols/result.py — CallResult：所有协议统一的调用证据形状（v2 §3，v2.1 批次 A）。

设计要点：
  - 下游（Extract/Assertion/事件/台账）一律只认这个形状：
    ``$.call.response.status`` / ``$.call.response.meta.*`` / ``$.call.response.body.*``；
  - ``request`` 是**渲染后且已脱敏**的请求（经 redact），可安全入证据流；
  - ``response`` = {status, meta, body}：status 是协议自己的状态语义
    （http 状态码 / 自定义协议结果码），meta 放头信息等旁证，body 归一为
    JSON 可导航结构（非 JSON 载荷放 str）；
  - 证据出口硬约束（v2 §5）：``to_evidence()`` 做脱敏复核 + body 大小截断；
  - scratch 与证据分离（P0-3）：``to_scratch()`` 存**原值**（不脱敏、不截断），
    仅供本 step 的 Extract/Assertion/后续策略消费；事件、归档、报告等证据
    出口一律走 ``to_evidence()``；
  - 双读期（批次 A-F）：scratch 同时写 ``call`` 键（本形状）与旧键
    （response_* 等），批次 F 回收旧键。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field, PrivateAttr

from gimbal.log import get_logger

logger = get_logger(__name__)

# 证据体大小上限（单值序列化后字符数）；超限截断并标记。
EVIDENCE_BODY_MAX_CHARS = 64 * 1024
_TRUNCATED_FLAG = "_truncated"

# 默认脱敏键（大小写不敏感子串匹配）：命中即以 *** 占位。
_DEFAULT_REDACT_KEYS = ("authorization", "cookie", "x-auth-token", "token", "secret", "password")


def redact_value(value: Any) -> str:
    return "***redacted***"


def redact_mapping(data: dict, keys: tuple[str, ...] = _DEFAULT_REDACT_KEYS) -> dict:
    """按键名子串匹配递归脱敏 dict（含嵌套 dict/list），返回新 dict。

    只作用于传入方向（request/meta 等旁证）；response.body 是断言对象，
    不做键名脱敏（body 的截断由 truncate_oversize 负责）。
    """
    out: dict = {}
    for k, v in data.items():
        if any(pat in str(k).lower() for pat in keys):
            out[k] = redact_value(v)
        elif isinstance(v, dict):
            out[k] = redact_mapping(v, keys)
        elif isinstance(v, list):
            out[k] = [
                redact_mapping(item, keys) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            out[k] = v
    return out


def truncate_oversize(value: Any, max_chars: int = EVIDENCE_BODY_MAX_CHARS) -> Any:
    """序列化超限的 body 截断为 str 并加标记；小值原样返回。"""
    try:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        serialized = str(value)
    if len(serialized) <= max_chars:
        return value
    truncated = serialized[:max_chars]
    return f"{truncated}...[{_TRUNCATED_FLAG} size>{max_chars}chars]"


def evidence_from_call_dict(call: dict, *, max_chars: int = EVIDENCE_BODY_MAX_CHARS) -> dict:
    """从 scratch 的原值 ``call`` dict 复核出证据形态（脱敏 + 截断）。

    给拿不到 CallResult 对象、只有 scratch 快照的证据出口用（归档
    save_exchange 一类）；与 ``CallResult.to_evidence()`` 同口径——
    request/meta 脱敏、body 截断，其余键原样保留。
    """
    response = call.get("response") or {}
    out = dict(call)
    out["request"] = redact_mapping(call.get("request") or {})
    out["response"] = {
        **response,
        "meta": redact_mapping(response.get("meta") or {}),
        "body": truncate_oversize(response.get("body"), max_chars),
    }
    return out


class CallResult(BaseModel):
    """一次协议调用的统一证据。

    构造约定：``request`` 传入前应已过 adapter.redact；``response.body``
    传 JSON 可导航结构或 str。对外发布（事件/归档）一律经 ``to_evidence()``
    复核脱敏与大小上限；scratch 消费（Extract/Assertion）经 ``to_scratch()``
    取**原值**（P0-3：两套形状、两种出口）。
    """

    protocol: str
    request: dict = Field(default_factory=dict)
    response: dict = Field(default_factory=dict)   # {status, meta, body}
    elapsed_ms: float = 0.0
    auth_expired: bool = False

    # 请求侧原值（P0-3）：执行器模板在 redact 覆写 request 前经
    # remember_raw_request() 记下的渲染后原值，to_scratch 的请求侧来源。
    _raw_request: Optional[dict] = PrivateAttr(default=None)

    # ── 便利访问（scratch 旧键双写的取值来源）────────────────

    @property
    def status(self) -> Any:
        return self.response.get("status")

    @property
    def meta(self) -> dict:
        return self.response.get("meta") or {}

    @property
    def body(self) -> Any:
        return self.response.get("body")

    def to_evidence(self, *, max_chars: int = EVIDENCE_BODY_MAX_CHARS) -> dict:
        """产出可入证据流（事件/归档/报告）的 dict：脱敏复核 + body 截断。"""
        return {
            "protocol": self.protocol,
            "request": redact_mapping(self.request),
            "response": {
                "status": self.status,
                "meta": redact_mapping(self.meta),
                "body": truncate_oversize(self.body, max_chars),
            },
            "elapsed_ms": self.elapsed_ms,
            "auth_expired": self.auth_expired,
        }

    def to_scratch(self) -> dict:
        """scratch ``call`` 键的存态：**原值**（不脱敏、不截断）。

        仅供本 step 的 Extract/Assertion/后续策略消费原值（如
        ``$.call.response.meta.headers.accesstoken`` 取登录 token、
        大 body 全量断言）；事件、归档、报告等证据出口一律走
        ``to_evidence()``（脱敏 + 64KB 截断）。键结构与 to_evidence 一致。
        """
        response = self.response or {}
        return {
            "protocol": self.protocol,
            "request": self._raw_request if self._raw_request is not None else (self.request or {}),
            "response": {
                "status": response.get("status"),
                "meta": response.get("meta") or {},
                "body": response.get("body"),
            },
            "elapsed_ms": self.elapsed_ms,
            "auth_expired": self.auth_expired,
        }

    def remember_raw_request(self) -> None:
        """在 request 被脱敏覆写前记下请求侧原值（to_scratch 的来源）。

        执行器模板调用（send 返回后、redact 覆写前）；幂等——只记第一次。
        """
        if self._raw_request is None:
            self._raw_request = self.request

    @classmethod
    def build(
        cls,
        *,
        protocol: str,
        request: dict,
        status: Any,
        body: Any,
        meta: Optional[dict] = None,
        elapsed_ms: float = 0.0,
        auth_expired: bool = False,
    ) -> "CallResult":
        """协议执行器 send() 的常用构造入口。"""
        return cls(
            protocol=protocol,
            request=request,
            response={"status": status, "meta": meta or {}, "body": body},
            elapsed_ms=elapsed_ms,
            auth_expired=auth_expired,
        )
