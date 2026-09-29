"""platform.users.delete_by_user_id —— Delete User

`DELETE /api/users/{user_id}`

Delete ``user_id``(P2-2:资源处置三选一)。

Authorization: admin only — a member can never delete another account
(403/4031).  Self-delete is separately refused below (409/code 4091),
so effectively "admin deleting someone else".

Constraints (both 409):
* caller cannot delete themselves (code 4091).
* cannot delete the last remaining admin (code 4092).

处置(权限方案 §4.3):``publicize`` 私有场景转公共库(默认,署名
保留 owner_name 快照)/ ``transfer`` 转让给指定成员(数据集/方案
随场景走,个人别名转共享,受让人收 resource_transferred 通知)/
``purge`` 一并删除。执行台账恒保留(outlive 用户:owner_id 置空 +
owner_name 快照,展示「已注销」);case 目录按 owner 定位 runId
当场清扫(case.json 含注入后明文凭证,不等 14 天周期)。

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

USERS_DELETE_BY_USER_ID: Final[EndpointSpec] = EndpointSpec(
    id="platform.users.delete_by_user_id",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Delete User",
    description="Delete ``user_id``(P2-2:资源处置三选一)。\n\nAuthorization: admin only — a member can never delete another account\n(403/4031).  Self-delete is separately refused below (409/code 4091),\nso effectively \"admin deleting someone else\".\n\nConstraints (both 409):\n* caller cannot delete themselves (code 4091).\n* cannot delete the last remaining admin (code 4092).\n\n处置(权限方案 §4.3):``publicize`` 私有场景转公共库(默认,署名\n保留 owner_name 快照)/ ``transfer`` 转让给指定成员(数据集/方案\n随场景走,个人别名转共享,受让人收 resource_transferred 通知)/\n``purge`` 一并删除。执行台账恒保留(outlive 用户:owner_id 置空 +\nowner_name 快照,展示「已注销」);case 目录按 owner 定位 runId\n当场清扫(case.json 含注入后明文凭证,不等 14 天周期)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="DELETE",
        path="/api/users/{user_id}",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="json",
        declarations=[
            DeclarationEntry(name="disposal", path="$.disposal", type="string",
                              ui_kind="text"),
            DeclarationEntry(name="transfer_to", path="$.transfer_to", type="integer",
                              ui_kind="number"),
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
        module="users",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
        business_notes="responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）",
    ),
)
