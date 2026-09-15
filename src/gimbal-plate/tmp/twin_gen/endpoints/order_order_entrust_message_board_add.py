"""fin.order_entrust.message_board_add —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): type
"""
from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_MODULE,
    FIN_DEFAULT_OWNER,
    FIN_DEFAULT_PRIORITY,
    FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION,
    FIN_SYSTEM,
)

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    DeclarationEntry,
    RequestSpec,
    ResponseSpec,
    EndpointMetadata,
    ValueSource,
)

ORDER_ENTRUST_MESSAGE_BOARD_ADD: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_entrust.message_board_add',
    system='fin',
    service='fin-service',
    name='OrderEntrust.messageBoardAdd',
    description='OrderEntrust.messageBoardAdd' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderEntrust/messageBoardAdd',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', required=True, default='0', description='业务ID'),
            DeclarationEntry(name='type', path=f'$.type', type='string', state='carry', required=True, description='留言类型'),  # needs_capture:value_source
            DeclarationEntry(name='message', path=f'$.message', type='string', state='form', required=True, description='留言内容'),
            DeclarationEntry(name='user_ids', path=f'$.user_ids', type='string', state='form', required=True, description='通知人ID'),
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
