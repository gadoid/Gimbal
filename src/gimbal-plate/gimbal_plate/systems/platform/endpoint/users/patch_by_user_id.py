"""platform.users.patch_by_user_id —— Patch User

`PATCH /api/users/{user_id}`

Update ``display_name`` / ``is_admin`` / ``is_active`` / ``new_password``.

Authorization:
* admin caller — may patch any user, any field.
* member caller — may only patch **themselves** (403/4032 on other
  targets) and may never touch ``role`` (privilege-escalation fix).

Constraint: demoting the last admin(``role`` 从 admin 降下)被 409 拒。

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

USERS_PATCH_BY_USER_ID: Final[EndpointSpec] = EndpointSpec(
    id="platform.users.patch_by_user_id",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Patch User",
    description="Update ``display_name`` / ``is_admin`` / ``is_active`` / ``new_password``.\n\nAuthorization:\n* admin caller — may patch any user, any field.\n* member caller — may only patch **themselves** (403/4032 on other\n  targets) and may never touch ``role`` (privilege-escalation fix).\n\nConstraint: demoting the last admin(``role`` 从 admin 降下)被 409 拒。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="PATCH",
        path="/api/users/{user_id}",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="display_name", path="$.display_name", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="is_active", path="$.is_active", type="boolean",
                              ui_kind="boolean"),
            DeclarationEntry(name="new_password", path="$.new_password", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="role", path="$.role", type="string", ui_kind="text"),
        ]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[
                DeclarationEntry(name="created_at", path="$.created_at", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="display_name", path="$.display_name", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="id", path="$.id", type="integer", ui_kind="number",
                                  required=True, assertable=True),
                DeclarationEntry(name="is_active", path="$.is_active", type="boolean",
                                  ui_kind="boolean", required=True, assertable=True),
                DeclarationEntry(name="is_admin", path="$.is_admin", type="boolean",
                                  ui_kind="boolean", assertable=True),
                DeclarationEntry(name="role", path="$.role", type="string", ui_kind="text",
                                  assertable=True),
                DeclarationEntry(name="updated_at", path="$.updated_at", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="username", path="$.username", type="string",
                                  ui_kind="text", required=True, assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="users",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
