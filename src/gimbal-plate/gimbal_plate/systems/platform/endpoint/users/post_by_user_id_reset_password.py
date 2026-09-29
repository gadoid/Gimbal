"""platform.users.post_by_user_id_reset_password —— Reset Password

`POST /api/users/{user_id}/reset-password`

Generate a fresh random password for ``user_id`` and persist its hash.

Authorization: admin (any target) or the target user themselves
(account-takeover fix: a member can no longer reset *someone else's*
password and receive the plaintext).  The plaintext password is
returned **once** in the response and is never stored on the server.

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

USERS_POST_BY_USER_ID_RESET_PASSWORD: Final[EndpointSpec] = EndpointSpec(
    id="platform.users.post_by_user_id_reset_password",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Reset Password",
    description="Generate a fresh random password for ``user_id`` and persist its hash.\n\nAuthorization: admin (any target) or the target user themselves\n(account-takeover fix: a member can no longer reset *someone else's*\npassword and receive the plaintext).  The plaintext password is\nreturned **once** in the response and is never stored on the server.",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/users/{user_id}/reset-password",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="none",
        declarations=[]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="users",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
