"""fin.assign.assign_page —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): create_id, create_time, audit_no, audit_type, sort_field, sort_order
溯源统计: frontend=9, builtin=4, derived=4, 无zh=1 | fe_high=9, enum=1
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

ASSIGN_ASSIGN_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.assign.assign_page',
    system='fin',
    service='fin-service',
    name='Assign.assignPage',
    description='Assign.assignPage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/assign/assignPage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='assign_no', path=f'$.assign_no', type='string', state='form', ui_kind='text', description='任务编号'),
            DeclarationEntry(name='assign_type', path=f'$.assign_type', type='string', state='form', ui_kind='select', description='任务类型'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', ui_kind='select', default='0', description='发起人'),  # zh_ambiguous
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='发起时间'),  # zh_ambiguous
            DeclarationEntry(name='executor_id', path=f'$.executor_id', type='integer', state='form', ui_kind='select', default='0', description='处理人'),
            DeclarationEntry(name='executor_time', path=f'$.executor_time', type='integer', state='carry', ui_kind='text', default='0', description='处理时间'),
            DeclarationEntry(name='audit_no', path=f'$.audit_no', type='string', state='carry', ui_kind='text', description='审批编号'),  # needs_capture:value_source
            DeclarationEntry(name='audit_type', path=f'$.audit_type', type='string', state='carry', ui_kind='select', description='审批类型'),  # needs_capture:value_source
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='carry', ui_kind='select', default='1', description='审批状态'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', required=True, description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', required=True, description='每页条数'),
            DeclarationEntry(name='active_tab', path=f'$.active_tab', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form', ui_kind='text', description='发起时间开始'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form', ui_kind='text', description='发起时间结束'),
            DeclarationEntry(name='executor_time_start', path=f'$.executor_time_start', type='string', state='form', ui_kind='text', description='处理时间开始'),
            DeclarationEntry(name='executor_time_end', path=f'$.executor_time_end', type='string', state='form', ui_kind='text', description='处理时间结束'),
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
