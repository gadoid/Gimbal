"""platform system 常量。

与 fin 的 system_info.py 同构。注意 service 名必须区别于 fin-service ——
plate 的 by_route 索引按 (service, method, path) 建，撞了后注册者静默覆盖前者。
"""

PLATFORM_SYSTEM = "platform"
PLATFORM_SERVICE = "platform-service"
PLATFORM_SERVICE_URL = "http://127.0.0.1:8000"
PLATFORM_DEFAULT_VERSION = "1.0.0"
PLATFORM_DEFAULT_MODULE = "platform"
PLATFORM_DEFAULT_TAGS = ["platform"]
PLATFORM_DEFAULT_OWNER = "gimbal-bootstrap"
