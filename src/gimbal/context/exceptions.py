class ContextError(Exception):
    """Context 相关错误的基类。"""


class SealedContextError(ContextError):
    """对已 sealed 的字段进行写入。"""


class PromotionRejected(ContextError):
    """变量提升被 policy 拒绝。"""


class LayerResolutionError(ContextError):
    """目标 layer 在当前链路中不存在。"""