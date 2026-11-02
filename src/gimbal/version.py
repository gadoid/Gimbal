"""Version information."""

__version__ = "0.1.0"

# 引擎能力声明(供外部方探测)。server 链经 healthz 的 cancel_scopes 上报;
# legacy 链(单子进程 spawn)没有 HTTP 面,平台在读本地 gimbal 包时读本常量
# 判定能否下发 --cancel-file。
#   "cancel-file": run launch --cancel-file PATH —— 文件出现 = 单元级取消
#   (drain 语义:跑完在飞单元、未启动主体记 cancelled、after 括号必达)。
FEATURES = ("cancel-file",)


def getVersion():
    return __version__