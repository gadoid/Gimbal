"""platform.admin.get_audit_logs —— List Audit Logs

`GET /api/admin/audit-logs`

特权写审计(权限方案 §6):新→旧分页;``action`` 精确过滤;
``actions`` 带回词表供前端过滤 chip。

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

ADMIN_GET_AUDIT_LOGS: Final[EndpointSpec] = EndpointSpec(
    id="platform.admin.get_audit_logs",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="List Audit Logs",
    description="特权写审计(权限方案 §6):新→旧分页;``action`` 精确过滤;\n``actions`` 带回词表供前端过滤 chip。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/admin/audit-logs",
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
            declarations=[
                DeclarationEntry(name="actions", path="$.actions", type="array",
                                  ui_kind="json", assertable=True),
                DeclarationEntry(name="items", path="$.items", type="array", ui_kind="json",
                                  required=True, assertable=True, children=[
                                     DeclarationEntry(name="action", path="$.items.action",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="actorId",
                                                       path="$.items.actorId",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="actorName",
                                                       path="$.items.actorName",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="createdAt",
                                                       path="$.items.createdAt",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="detail", path="$.items.detail",
                                                       type="object", ui_kind="json",
                                                       assertable=True),
                                     DeclarationEntry(name="id", path="$.items.id",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="resourceId",
                                                       path="$.items.resourceId",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="resourceType",
                                                       path="$.items.resourceType",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                 ]
                ),
                DeclarationEntry(name="page", path="$.page", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="pageSize", path="$.pageSize", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="total", path="$.total", type="integer",
                                  ui_kind="number", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="admin",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
