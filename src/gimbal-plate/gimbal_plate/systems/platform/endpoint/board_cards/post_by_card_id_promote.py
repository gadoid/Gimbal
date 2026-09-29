"""platform.board_cards.post_by_card_id_promote —— Promote Card

`POST /api/board-cards/{card_id}/promote`

设为 root:同主体降旧升新,单条 UPDATE 原子完成(§3.3)。

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

BOARD_CARDS_POST_BY_CARD_ID_PROMOTE: Final[EndpointSpec] = EndpointSpec(
    id="platform.board_cards.post_by_card_id_promote",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Promote Card",
    description="设为 root:同主体降旧升新,单条 UPDATE 原子完成(§3.3)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="POST",
        path="/api/board-cards/{card_id}/promote",
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
                DeclarationEntry(name="annotatesNodeId", path="$.annotatesNodeId",
                                  type="string", ui_kind="text", assertable=True),
                DeclarationEntry(name="authorId", path="$.authorId", type="integer",
                                  ui_kind="number", required=True, assertable=True),
                DeclarationEntry(name="body", path="$.body", type="string", ui_kind="text",
                                  required=True, assertable=True),
                DeclarationEntry(name="createdAt", path="$.createdAt", type="string",
                                  ui_kind="text", assertable=True),
                DeclarationEntry(name="id", path="$.id", type="integer", ui_kind="number",
                                  required=True, assertable=True),
                DeclarationEntry(name="isRoot", path="$.isRoot", type="boolean",
                                  ui_kind="boolean", assertable=True),
                DeclarationEntry(name="quadrant", path="$.quadrant", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="subjectId", path="$.subjectId", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="subjectKind", path="$.subjectKind", type="string",
                                  ui_kind="text", required=True, assertable=True),
                DeclarationEntry(name="updatedAt", path="$.updatedAt", type="string",
                                  ui_kind="text", assertable=True),
            ]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="board-cards",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
