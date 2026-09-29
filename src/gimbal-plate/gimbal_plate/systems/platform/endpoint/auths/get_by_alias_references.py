"""platform.auths.get_by_alias_references —— Get References

`GET /api/auths/{alias}/references`

反查面板:谁在用这个凭证名(配套方案 §1.3)。四类引用,读时实时
扫(单一事实源,不建反向索引);计数照给、场景名按 can_read_scenario
过滤(admin 全量 / public / owner),剩余 = hidden_count(§1.4)。
名字命中 ≠ 对象引用 — 引用解析按执行者本人池,文案须如实。

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

AUTHS_GET_BY_ALIAS_REFERENCES: Final[EndpointSpec] = EndpointSpec(
    id="platform.auths.get_by_alias_references",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get References",
    description="反查面板:谁在用这个凭证名(配套方案 §1.3)。四类引用,读时实时\n扫(单一事实源,不建反向索引);计数照给、场景名按 can_read_scenario\n过滤(admin 全量 / public / owner),剩余 = hidden_count(§1.4)。\n名字命中 ≠ 对象引用 — 引用解析按执行者本人池,文案须如实。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/auths/{alias}/references",
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
                DeclarationEntry(name="alias_refs", path="$.alias_refs", type="array",
                                  ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="alias_name",
                                                       path="$.alias_refs.alias_name",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="base_service",
                                                       path="$.alias_refs.base_service",
                                                       type="string", ui_kind="text",
                                                       required=True, assertable=True),
                                     DeclarationEntry(name="group_tag",
                                                       path="$.alias_refs.group_tag",
                                                       type="string", ui_kind="text",
                                                       assertable=True),
                                 ]
                ),
                DeclarationEntry(name="scenario_refs", path="$.scenario_refs",
                                  type="object", ui_kind="json", assertable=True, children=[
                                     DeclarationEntry(name="hidden_count",
                                                       path="$.scenario_refs.hidden_count",
                                                       type="integer", ui_kind="number",
                                                       assertable=True),
                                     DeclarationEntry(name="visible",
                                                       path="$.scenario_refs.visible",
                                                       type="array", ui_kind="json",
                                                       assertable=True, children=[
                                                          DeclarationEntry(name="kinds",
                                                                            path="$.scenario_refs.visible.kinds",
                                                                            type="array",
                                                                            ui_kind="json",
                                                                            required=True,
                                                                            assertable=True),
                                                          DeclarationEntry(name="name",
                                                                            path="$.scenario_refs.visible.name",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            required=True,
                                                                            assertable=True),
                                                          DeclarationEntry(name="owner_id",
                                                                            path="$.scenario_refs.visible.owner_id",
                                                                            type="integer",
                                                                            ui_kind="number",
                                                                            required=True,
                                                                            assertable=True),
                                                          DeclarationEntry(name="scenario_id",
                                                                            path="$.scenario_refs.visible.scenario_id",
                                                                            type="string",
                                                                            ui_kind="text",
                                                                            required=True,
                                                                            assertable=True),
                                                      ]
                                     ),
                                 ]
                ),
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
