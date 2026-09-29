"""schema/debug.py — 调试会话命令结构（定稿 A6 / 路线图 N6，P3-04）。

文本协议（CLI 终端）与结构化协议（server ``POST /runs/{id}/debug``）统一
到同一组模型：

* CLI/测试会话的文本行经 :func:`parse_debug_command` 解析为 ``DebugCommand``
  （解析失败抛 :class:`DebugCommandError`，会话内友好重试）；
* server 请求体直接携带 ``DebugCommand`` —— pydantic 校验即红线（write/patch
  的键与值必须成对出现），非法 422，不再有"未知命令"运行期分支。

点位校验（write 仅 step.before、patch 仅 call.before）依赖运行期暂停点，
留在 DebuggerPlugin（schema 不知道点位）。
"""
from __future__ import annotations

import json
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DebugCommandError(ValueError):
    """文本命令解析失败（面向会话的友好错误，不崩会话循环）。"""


class DebugCommand(BaseModel):
    """一条调试会话命令。

    kind 语义与拦截决策一一对应：
      continue / step —— 放行（step 在 every_step 档位下=步进到下一暂停点，
                          与 continue 同一 Decision，保留拼写便于前端表达）；
      abort           —— 终止 run；
      read            —— 查看最近调用证据（不产生 Decision，继续等下一条）；
      write           —— 注入 scratch 变量后继续（仅 step.before 暂停点）；
      patch           —— 补丁待发请求后继续（仅 call.before 暂停点）；
      retry / skip    —— 仅 step.failed 暂停点。
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["continue", "step", "abort", "read",
                  "write", "patch", "retry", "skip"]
    # write 专用：scratch 变量名
    variable: Optional[str] = Field(None, description="write：变量名")
    # patch 专用：待发请求的 JSONPath
    path: Optional[str] = Field(None, description="patch：JSONPath")
    # write/patch 的值（JSON 任意形态；可为 null）
    value: Any = Field(None, description="write/patch：写入值")

    @model_validator(mode="after")
    def _check_payload(self) -> "DebugCommand":
        if self.kind == "write":
            if not self.variable:
                raise ValueError("write 需要 variable（变量名）")
        elif self.kind == "patch":
            if not self.path:
                raise ValueError("patch 需要 path（JSONPath）")
        else:
            if self.variable is not None or self.path is not None:
                raise ValueError(f"{self.kind} 不携带 variable/path")
        return self

    def key(self) -> str:
        """write → variable；patch → path。"""
        return self.variable if self.kind == "write" else (self.path or "")


# 文本 → kind 的别名表（与旧 _pause 文本协议逐一对应）
_TEXT_ALIASES = {
    "": "continue", "c": "continue", "continue": "continue",
    "step": "step",
    "q": "abort", "quit": "abort", "abort": "abort",
    "r": "read", "read": "read",
    "retry": "retry", "skip": "skip",
}

_ALLOWED = ("continue/step/c/回车, abort/q, read/r, retry, skip, "
            "write <变量名>=<json>, patch <jsonpath>=<json>")


def _parse_value(raw: str) -> Any:
    """宽松值解析：json.loads 失败回落原串（裸 token 按字符串，旧口径）。"""
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


def parse_debug_command(text: str) -> DebugCommand:
    """文本行 → DebugCommand（CLI 终端/测试脚本会话的唯一入口）。

    改值命令 ``write k=v`` / ``patch $.p=v``：v 先按 JSON、失败回落原串。
    """
    cmd = (text or "").strip()
    if not cmd:
        return DebugCommand(kind="continue")
    head = cmd.split(" ", 1)[0]
    if head in ("write", "patch"):
        rest = cmd[len(head):].strip()
        key, eq, raw = rest.partition("=")
        key, raw = key.strip(), raw.strip()
        if not key or not eq or not raw:
            usage = ("write <变量名>=<json>（如 write orderId=\"O-9\"）"
                     if head == "write"
                     else "patch <jsonpath>=<json>（如 patch $.request.body.qty=5）")
            raise DebugCommandError(f"命令格式错误，用法: {usage}")
        if head == "write":
            return DebugCommand(kind="write", variable=key, value=_parse_value(raw))
        return DebugCommand(kind="patch", path=key, value=_parse_value(raw))
    if cmd in _TEXT_ALIASES:
        return DebugCommand(kind=_TEXT_ALIASES[cmd])
    raise DebugCommandError(f"未知命令 {cmd!r}（{_ALLOWED}）")
