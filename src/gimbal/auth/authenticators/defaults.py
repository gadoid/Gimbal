"""AuthSession 默认配置常量
当 AuthSession 对象的字段为空时，使用此文件中的默认值。
每个认证器可按需引用这些常量。
"""

# ── 默认超时时间（秒）───────────────────────────────────────
DEFAULT_TIMEOUT: int = 30

# ── 默认 Token 有效期（秒）──────────────────────────────────
DEFAULT_EXPIRES_IN: int = 7200  # 1 小时

# ── 默认过期时间阈值（秒）───────────────────────────────────
# 用于 should_refresh 判断，提前多久开始刷新
DEFAULT_REFRESH_THRESHOLD: int = 300  # 5 分钟

