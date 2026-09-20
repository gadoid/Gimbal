"""fin.message.message_page —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): create_time, sort_field, sort_order
溯源统计: frontend=6, builtin=4, derived=4, column=2, 无zh=1 | fe_high=6, enum=1
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
            DeclarationEntry(name='message_no', path=f'$.message_no', type='string', state='form', ui_kind='text', description='消息编号'),
            DeclarationEntry(name='title', path=f'$.title', type='string', state='form', ui_kind='select', description='消息标题'),
            DeclarationEntry(name='source', path=f'$.source', type='integer', state='form', ui_kind='select', default='0', description='消息来源'),
            DeclarationEntry(name='message_status', path=f'$.message_status', type='integer', state='form', ui_kind='select', default='1', description='消息状态'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='发送时间'),  # zh_ambiguous
            DeclarationEntry(name='read_time', path=f'$.read_time', type='integer', state='carry', ui_kind='text', default='0', description='已读时间'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', required=True, description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', required=True, description='每页条数'),
            DeclarationEntry(name='active_tab', path=f'$.active_tab', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='type', path=f'$.type', type='string', state='form', ui_kind='text', description='审批流模块'),
            DeclarationEntry(name='send_id', path=f'$.send_id', type='integer', state='form', ui_kind='number', default='0', description='消息发送人ID'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form', ui_kind='text', description='发送时间开始'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form', ui_kind='text', description='发送时间结束'),
            DeclarationEntry(name='read_time_start', path=f'$.read_time_start', type='string', state='form', ui_kind='text', description='已读时间开始'),
            DeclarationEntry(name='read_time_end', path=f'$.read_time_end', type='string', state='form', ui_kind='text', description='已读时间结束'),
            DeclarationEntry(name='sort_field', path=f'$.sort_field', type='string', state='carry', ui_kind='text', required=True, description='排序字段'),  # needs_capture:value_source
            DeclarationEntry(name='sort_order', path=f'$.sort_order', type='string', state='carry', ui_kind='select', required=True, description='排序方向', enum=['asc', 'desc']),  # needs_capture:enum_required
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description='成功(信封统一;data 行形状归场景用例)',
            declarations=[
            DeclarationEntry(name='code', path='$.code', type='number',
                             required=False, ui_kind='number',
                             description='业务状态码(200=成功)', assertable=True),
            DeclarationEntry(name='msg', path='$.msg', type='string',
                             required=False, ui_kind='text',
                             description='业务提示信息', assertable=True),
            DeclarationEntry(name='data', path='$.data', type='object',
                             required=False, ui_kind='json',
                             description='业务数据(行形状归场景用例)', assertable=True),
            DeclarationEntry(name='request_id', path='$.request_id', type='string',
                             required=False, ui_kind='text',
                             description='请求追踪ID', assertable=True),

            ],
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
