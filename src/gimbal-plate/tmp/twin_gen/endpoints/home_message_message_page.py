"""fin.message.message_page —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): (无)
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

MESSAGE_MESSAGE_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.message.message_page',
    system='fin',
    service='fin-service',
    name='Message.messagePage',
    description='Message.messagePage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/message/messagePage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
            DeclarationEntry(name='active_tab', path=f'$.active_tab', type='string', state='form'),
            DeclarationEntry(name='message_no', path=f'$.message_no', type='string', state='form', description='消息编号'),
            DeclarationEntry(name='type', path=f'$.type', type='string', state='form'),
            DeclarationEntry(name='title', path=f'$.title', type='string', state='form', description='消息标题'),
            DeclarationEntry(name='source', path=f'$.source', type='integer', state='form', default='0', description='消息来源 1审批中心 2任务中心 3系统用户 4订单中心'),
            DeclarationEntry(name='send_id', path=f'$.send_id', type='integer', state='form', default='0', description='消息发送人ID'),
            DeclarationEntry(name='message_status', path=f'$.message_status', type='integer', state='form', default='1', description='消息状态 1未读 2已读'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form'),
            DeclarationEntry(name='read_time_start', path=f'$.read_time_start', type='string', state='form'),
            DeclarationEntry(name='read_time_end', path=f'$.read_time_end', type='string', state='form'),
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
