"""compiler/errors.py — 编译错误类型与错误码（独立模块避免 pipeline/modes 循环）。

P0-06（2026-09-28）：CompileError 携带稳定错误码与定位，CLI `-o json`
输出 ``{code, message, location}``；消费方（平台 / Agent）按 code 分支，
不解析消息文本。错误码只增不改值。
"""


class ErrCode:
    """稳定错误码（字符串枚举）。

    分组：加载 / 协议与调用 / 生命周期 / 图结构 / 连线与静态分析。
    p_validate 的字符串错误以 ``"CODE: message"`` 前缀携带同一组码。
    """

    # ── 加载与目标形态 ──────────────────────────────────────
    BAD_TARGET_KIND = "BAD_TARGET_KIND"          # payload 的 kind 不是 scenario/graph
    BAD_TARGET_TYPE = "BAD_TARGET_TYPE"          # 编译目标类型不受支持
    SCHEMA_INVALID = "SCHEMA_INVALID"            # pydantic schema 校验失败（CLI 装载期包装）

    # ── 协议与调用（normalize 期）──────────────────────────
    UNKNOWN_PROTOCOL = "UNKNOWN_PROTOCOL"        # call.protocol 未注册（权威表下）
    CALL_FIELD_INVALID = "CALL_FIELD_INVALID"    # 协议字段未知/类型不符（extra=forbid）

    # ── 生命周期条目（normalize 期）────────────────────────
    LIFECYCLE_KIND_UNKNOWN = "LIFECYCLE_KIND_UNKNOWN"
    LIFECYCLE_PARAMS_INVALID = "LIFECYCLE_PARAMS_INVALID"

    # ── 图结构 ─────────────────────────────────────────────
    UNKNOWN_MODE = "UNKNOWN_MODE"                # mode 不在四模式注册表
    DUP_UNIT_ID = "DUP_UNIT_ID"                  # 单元 id 重复
    EMPTY_OR_DUP_REF = "EMPTY_OR_DUP_REF"        # 空 ref / ref 重复
    NEEDS_REF_INVALID = "NEEDS_REF_INVALID"      # needs 引用不存在/自环/指向 after
    BRACKET_NEEDS_FORBIDDEN = "BRACKET_NEEDS_FORBIDDEN"  # 括号单元声明 needs
    CONTROL_ONLY_EMPTY = "CONTROL_ONLY_EMPTY"    # control.only 闭包后主体为空
    CONTROL_REF_INVALID = "CONTROL_REF_INVALID"  # control.only 引用不存在
    CYCLE = "CYCLE"                              # 依赖成环
    EXPAND_LIMIT = "EXPAND_LIMIT"                # repeat × 数据集展开超上限
    SHARED_MISMATCH = "SHARED_MISMATCH"          # 同 shared key 生效定义不一致

    # ── 连线与静态分析（bind 期）───────────────────────────
    INPUT_UNSATISFIED = "INPUT_UNSATISFIED"      # 硬输入无上游供给
    INPUT_AMBIGUOUS = "INPUT_AMBIGUOUS"          # 输入命中多个上游输出（需 map 改名）
    WIRING_TARGET_INVALID = "WIRING_TARGET_INVALID"  # wiring 目标格式/引用非法
    SUITE_VAR_CONFLICT = "SUITE_VAR_CONFLICT"    # 并发分支同名输出（P0-11 S2）

    # ── users 标签（validate 期）──────────────────────────
    USERS_TAG_UNKNOWN = "USERS_TAG_UNKNOWN"      # 引用了未在 config.users 声明的标签（P0-11 S1）

    # ── 未分类（历史调用点 / 外部包装）─────────────────────
    GENERIC = "GENERIC"


class CompileError(Exception):
    """编译失败（用户输入问题；CLI 层转 exit code 2）。

    Attributes:
        code: 稳定错误码（ErrCode.*；缺省 GENERIC）。
        location: 可选定位 ``{unit?, step?, path?, field?}``——
            尽量给最具体的锚点，缺省为空 dict。
    """

    def __init__(self, message: str, *, code: str = ErrCode.GENERIC,
                 location: "dict | None" = None):
        super().__init__(message)
        self.code = code
        self.location = location or {}

    def to_json(self) -> dict:
        """机器可读形态（CLI `-o json` 失败输出单条错误的形状）。"""
        return {"code": self.code, "message": str(self), "location": self.location}
