"""Framework-level shared exceptions.

异常类层次结构：
    GimbalError (基类)
    ├── ContextError
    ├── AuthError
    ├── StateMachineError
    ├── ConfigError
    ├── StrategyError
    ├── ExecutionError
    ├── ValidationError

所有框架异常都应该继承自 GimbalError，以支持统一的异常捕获和处理。
"""
from __future__ import annotations


class GimbalError(Exception):
    """框架所有异常的基类。

    提供统一的错误码和上下文信息支持。
    """

    # 子类应覆盖此属性
    code: str = "GIMBAL_ERROR"

    def __init__(
        self,
        message: str = "",
        code: str | None = None,
        **kwargs: object,
    ) -> None:
        """初始化异常实例：保存错误消息、可选覆盖错误码，并收集任意附加上下文键值对以供日志/序列化使用。"""
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        # 存储额外上下文供日志使用
        self.context = kwargs

    def __str__(self) -> str:
        """返回带错误码前缀的字符串表示；存在上下文时附加 key=value 形式的尾部，便于日志直接展示。"""
        if self.context:
            ctx_str = " ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"[{self.code}] {self.message} ({ctx_str})"
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict:
        """将异常序列化为包含 type / code / message / context 的字典，供 JSON 报告或外部系统使用。"""
        return {
            "type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "context": self.context,
        }


# ── Context 相关异常 ────────────────────────────────────────────────────────────


class ContextError(GimbalError):
    """Context 相关错误的基类。"""
    code = "CONTEXT_ERROR"


class SealedContextError(ContextError):
    """对已 sealed 的字段进行写入。"""
    code = "CONTEXT_SEALED"


class PromotionRejected(ContextError):
    """变量提升被 policy 拒绝。"""
    code = "CONTEXT_PROMOTION_REJECTED"


class LayerResolutionError(ContextError):
    """目标 layer 在当前链路中不存在。"""
    code = "CONTEXT_LAYER_NOT_FOUND"


# ── Auth 相关异常 ─────────────────────────────────────────────────────────────


class AuthError(GimbalError):
    """认证异常基类。"""
    code = "AUTH_ERROR"


class AuthLoginFailed(AuthError):
    """登录失败。"""
    code = "AUTH_LOGIN_FAILED"


class AuthTokenExpired(AuthError):
    """Token 已过期或无效。"""
    code = "AUTH_TOKEN_EXPIRED"


class AuthSessionNotFound(AuthError):
    """AuthSession 未找到。"""
    code = "AUTH_SESSION_NOT_FOUND"


# ── StateMachine 相关异常 ──────────────────────────────────────────────────────


class StateMachineError(GimbalError):
    """状态机基类异常。"""
    code = "STATEMACHINE_ERROR"


class InvalidTransitionError(StateMachineError):
    """非法状态跃迁。"""
    code = "STATEMACHINE_INVALID_TRANSITION"

    def __init__(self, from_state: str, to_state: str) -> None:
        """构造非法跃迁异常：记录起始态、目标态到消息及 context，便于定位违规的状态机路径。"""
        super().__init__(
            f"Invalid transition: {from_state!r} → {to_state!r}",
            from_state=from_state,
            to_state=to_state,
        )
        self.from_state = from_state
        self.to_state = to_state


class AlreadyTerminalError(StateMachineError):
    """对已处于终态的状态机发起跃迁。"""
    code = "STATEMACHINE_ALREADY_TERMINAL"

    def __init__(self, state: str) -> None:
        """构造终态重复跃迁异常：将当前终态名写入消息与 context，明确告知调用方所处状态。"""
        super().__init__(f"State machine is already in terminal state: {state!r}", state=state)
        self.state = state


# ── Config 相关异常 ─────────────────────────────────────────────────────────────


class ConfigError(GimbalError):
    """配置相关错误的基类。"""
    code = "CONFIG_ERROR"


# ── Strategy 相关异常 ──────────────────────────────────────────────────────────


class StrategyError(GimbalError):
    """策略执行相关错误的基类。"""
    code = "STRATEGY_ERROR"


class StrategyNotFoundError(StrategyError):
    """策略类型未注册。"""
    code = "STRATEGY_NOT_FOUND"


# ── Execution 相关异常 ──────────────────────────────────────────────────────────


class ExecutionError(GimbalError):
    """执行过程中发生的错误。"""
    code = "EXECUTION_ERROR"


# ── Validation 相关异常 ────────────────────────────────────────────────────────


class ValidationError(GimbalError):
    """数据验证失败的错误。"""
    code = "VALIDATION_ERROR"
