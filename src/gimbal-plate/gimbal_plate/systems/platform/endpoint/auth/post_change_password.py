"""platform.auth.post_change_password —— Change Password

`POST /api/auth/change-password`

自服务改密(P2-1):核验旧密码 → 写新哈希。改密后现有会话保留
(JWT 不含密码指纹;审计按特权写口径不记 —— 本人常规自管)。

字段面由 gimbal-bootstrap 的 contract_gen 从平台 OpenAPI 生成。这个文件
**可以手改** —— 实测核订的语义（description / ui_kind / required）写在
这里，重新生成默认不覆盖；要覆盖用 --force。
"""

from typing import Final

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.systems.platform.system_info import (
    PLATFORM_DEFAULT_OWNER,
    PLATFORM_DEFAULT_TAGS,
    PLATFORM_DEFAULT_VERSION,
    PLATFORM_SERVICE,
    PLATFORM_SYSTEM,
)

_RESPONSE_DECLS: Final[list[DeclarationEntry]] = []

AUTH_POST_CHANGE_PASSWORD: Final[EndpointSpec] = EndpointSpec(
    id="platform.auth.post_change_password",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Change Password",
    description="自服务改密(P2-1):核验旧密码 → 写新哈希。改密后现有会话保留\n(JWT 不含密码指纹;审计按特权写口径不记 —— 本人常规自管)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/auth/change-password",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="new_password", path="$.new_password", type="string",
                              ui_kind="text", required=True),
            DeclarationEntry(name="old_password", path="$.old_password", type="string",
                              ui_kind="text", required=True),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            declarations=_RESPONSE_DECLS,
        ),
        204: ResponseSpec(
            status=204,
            description="Successful Response",
            declarations=_RESPONSE_DECLS,
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="auth",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
