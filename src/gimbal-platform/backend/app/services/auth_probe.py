"""Auth-session connectivity probe。

改走 Authenticator 抽象(物理迁移自 gimbal 后):
 - 通过 ``get_authenticator(url)`` 按 URL 模式选择对应的认证器
 - 成功调 Authenticator.authenticate(auth, tag) 会自动写 token 到 AuthSession
 - 返回连通性 + 是否有 token(供 /auths/{id}/test 端点使用)

原简化版实现保持向后兼容的 ``probe()`` 签名(ok, status_code, message)三元组。
"""
from __future__ import annotations

from app.auth import AuthSession, get_authenticator
from app.auth.exceptions import AuthError


async def probe(url: str, username: str, password: str) -> tuple[bool, int | None, str]:
    """Dial the auth endpoint via Authenticator → ``(ok, status_code, message)``.

    Args:
        url: 认证接口地址
        username: 用户名
        password: 密码

    Returns:
        (ok, status_code, message) 三元组,与历史签名一致。
        ok=False 时 status_code 可能是 None 或被测系统返回的状态码。
    """
    # 1. 构造内存中的 AuthSession
    auth = AuthSession(url=url, username=username, password=password)

    # 2. 按 URL 路由选择对应的 Authenticator
    authenticator = get_authenticator(url)

    try:
        # 3. 执行认证(authenticator 内部会调 apply_token 写入 token)
        authenticator.authenticate(auth, tag="probe")
    except AuthError as e:
        # 已认证但返回了 AuthError(如 GitHub 没拿到 token 等)
        return False, None, f"认证失败: {e}"
    except Exception as e:
        # 网络错误 / 5xx / 凭据错误等
        return False, None, f"网络/认证错误: {type(e).__name__}: {e}"

    # 4. 拿到 token → 连通成功
    if auth.token:
        token_preview = str(auth.token)[:12]
        return True, 200, f"连通成功,已提取 token(前 12 字符:{token_preview}…)"

    # 5. 没拿到 token,但没抛异常(说明连通但响应不包含 token)
    return True, 200, "连通成功(响应未提取到 token)"