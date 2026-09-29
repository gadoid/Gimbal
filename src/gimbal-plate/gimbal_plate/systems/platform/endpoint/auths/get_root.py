"""platform.auths.get_root —— List Auths

`GET /api/auths`

Page 信封 + 服务端过滤(M4,§6.3):``q``(alias/url 子串;
username 是 Fernet 密文,服务端不可检索 —— 如实收缩,不含 username)、
``token_type`` 精确。双计数一次扫描服务全部行(配套方案 §1.2):
alias_ref_count = service_aliases 绑定数;scenario_ref_count =
模板 ∪ 方案绑定去重场景数(快照不进计数 — 面板里按 kind 展示)。

``tokenTypeCounts`` 是**全量过滤集**(非当前页)的类型计数 —— 服务端
分页后前端拿不到全集,metaText「N Bearer · N 整段头」改由这里供给。

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

AUTHS_GET_ROOT: Final[EndpointSpec] = EndpointSpec(
    id="platform.auths.get_root",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="List Auths",
    description="Page 信封 + 服务端过滤(M4,§6.3):``q``(alias/url 子串;\nusername 是 Fernet 密文,服务端不可检索 —— 如实收缩,不含 username)、\n``token_type`` 精确。双计数一次扫描服务全部行(配套方案 §1.2):\nalias_ref_count = service_aliases 绑定数;scenario_ref_count =\n模板 ∪ 方案绑定去重场景数(快照不进计数 — 面板里按 kind 展示)。\n\n``tokenTypeCounts`` 是**全量过滤集**(非当前页)的类型计数 —— 服务端\n分页后前端拿不到全集,metaText「N Bearer · N 整段头」改由这里供给。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/auths",
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
                DeclarationEntry(name="items", path="$.items", type="array", ui_kind="json",
                                  required=True, assertable=True, children=[
                                     DeclarationEntry(name="alias", path="$.items.alias",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="alias_ref_count",
                                                       path="$.items.alias_ref_count",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="created_at",
                                                       path="$.items.created_at",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="expires_in",
                                                       path="$.items.expires_in",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="id", path="$.items.id",
                                                       type="integer", ui_kind="number",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="password_masked",
                                                       path="$.items.password_masked",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="scenario_ref_count",
                                                       path="$.items.scenario_ref_count",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="token_type",
                                                       path="$.items.token_type",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="updated_at",
                                                       path="$.items.updated_at",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="url", path="$.items.url",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="username",
                                                       path="$.items.username",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                 ]
                ),
                DeclarationEntry(name="page", path="$.page", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="pageSize", path="$.pageSize", type="integer",
                                  ui_kind="number", assertable=True),
                DeclarationEntry(name="tokenTypeCounts", path="$.tokenTypeCounts",
                                  type="object", ui_kind="json", assertable=True),
                DeclarationEntry(name="total", path="$.total", type="integer",
                                  ui_kind="number", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="auths",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
