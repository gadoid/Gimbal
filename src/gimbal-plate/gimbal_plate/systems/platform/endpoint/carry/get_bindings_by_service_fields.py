"""platform.carry.get_bindings_by_service_fields —— Service Fields

`GET /api/carry/bindings/{service}/fields`

该服务全部接口 carry 面并集:GET /api/endpoint?service= → 逐 id /full。
任一端点 /full 失败(抛错或 404)→ degraded=True:面不完整,
配置页整表替换保存会删不可见端点的绑定值,须据此禁存。

键归一(配套方案 §2.3):``service`` 允许传别名全名 —— Plate 只认
目录服务,先 ``derive_base`` 归一到 base 再过滤。裸声明键(目录内
无此服务也无其 base)无面可言,返回空面且不标 degraded(空是确定
结论,不是面不完整);目录本身不可得(services dim 失败 → 空集)时
无从归一,原样过滤 —— 退化为修复前行为,而不是全局面瘫痪。

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

CARRY_GET_BINDINGS_BY_SERVICE_FIELDS: Final[EndpointSpec] = EndpointSpec(
    id="platform.carry.get_bindings_by_service_fields",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Service Fields",
    description="该服务全部接口 carry 面并集:GET /api/endpoint?service= → 逐 id /full。\n任一端点 /full 失败(抛错或 404)→ degraded=True:面不完整,\n配置页整表替换保存会删不可见端点的绑定值,须据此禁存。\n\n键归一(配套方案 §2.3):``service`` 允许传别名全名 —— Plate 只认\n目录服务,先 ``derive_base`` 归一到 base 再过滤。裸声明键(目录内\n无此服务也无其 base)无面可言,返回空面且不标 degraded(空是确定\n结论,不是面不完整);目录本身不可得(services dim 失败 → 空集)时\n无从归一,原样过滤 —— 退化为修复前行为,而不是全局面瘫痪。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/carry/bindings/{service}/fields",
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
                DeclarationEntry(name="degraded", path="$.degraded", type="boolean",
                                  ui_kind="boolean", assertable=True),
                DeclarationEntry(name="fields", path="$.fields", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="description",
                                                       path="$.fields.description",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                     DeclarationEntry(name="endpoints",
                                                       path="$.fields.endpoints",
                                                       type="array", ui_kind="json",
                                                       assertable=True, children=[
                                                          DeclarationEntry(name="id",
                                                                            path="$.fields.endpoints.id",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            required=True,
                                                                            assertable=True),
                                                          DeclarationEntry(name="method",
                                                                            path="$.fields.endpoints.method",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                          DeclarationEntry(name="name",
                                                                            path="$.fields.endpoints.name",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                          DeclarationEntry(name="path",
                                                                            path="$.fields.endpoints.path",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            assertable=True),
                                                      ]
                                     ),
                                     DeclarationEntry(name="path", path="$.fields.path",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="type", path="$.fields.type",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                 ]
                ),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="carry",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
