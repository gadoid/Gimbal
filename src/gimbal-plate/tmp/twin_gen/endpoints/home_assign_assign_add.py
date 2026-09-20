"""fin.assign.assign_add —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): assign_no, assign_type, assign_name, executor_by, executor_remark, callback_namespace, callback_method, transfer_by
溯源统计: column=20, 无zh=1 | fe_high=0, enum=0
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

ASSIGN_ASSIGN_ADD: Final[EndpointSpec] = EndpointSpec(
    id='fin.assign.assign_add',
    system='fin',
    service='fin-service',
    name='Assign.assignAdd',
    description='Assign.assignAdd' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/assign/assignAdd',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='assign_id', path=f'$.assign_id', type='integer', state='carry', ui_kind='number', description='主键ID'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='carry', ui_kind='number', description='业务ID'),
            DeclarationEntry(name='assign_no', path=f'$.assign_no', type='string', state='carry', ui_kind='text', description='任务编号'),  # needs_capture:value_source
            DeclarationEntry(name='assign_type', path=f'$.assign_type', type='string', state='carry', ui_kind='text', description='任务类型'),  # needs_capture:value_source
            DeclarationEntry(name='assign_name', path=f'$.assign_name', type='string', state='carry', ui_kind='text', description='任务类型名称'),  # needs_capture:value_source
            DeclarationEntry(name='assign_status', path=f'$.assign_status', type='integer', state='carry', ui_kind='number', description='任务状态 0待处理 1已处理'),
            DeclarationEntry(name='executor_id', path=f'$.executor_id', type='integer', state='carry', ui_kind='number', description='处理人ID'),
            DeclarationEntry(name='executor_by', path=f'$.executor_by', type='string', state='carry', ui_kind='text', description='处理人姓名'),  # needs_capture:value_source
            DeclarationEntry(name='executor_time', path=f'$.executor_time', type='integer', state='carry', ui_kind='number', description='处理时间'),
            DeclarationEntry(name='executor_remark', path=f'$.executor_remark', type='string', state='carry', ui_kind='text', description='处理备注'),  # needs_capture:value_source
            DeclarationEntry(name='callback_namespace', path=f'$.callback_namespace', type='string', state='carry', ui_kind='text', description='回调命名空间'),  # needs_capture:value_source
            DeclarationEntry(name='callback_method', path=f'$.callback_method', type='string', state='carry', ui_kind='text', description='回调方法名'),  # needs_capture:value_source
            DeclarationEntry(name='callback_data', path=f'$.callback_data', type='string', state='carry', ui_kind='text', description='回调数据'),
            DeclarationEntry(name='assign_msg', path=f'$.assign_msg', type='string', state='carry', ui_kind='text', description='任务回显信息'),
            DeclarationEntry(name='transfer_id', path=f'$.transfer_id', type='integer', state='carry', ui_kind='number', description='转派人ID'),
            DeclarationEntry(name='transfer_by', path=f'$.transfer_by', type='string', state='carry', ui_kind='text', description='转派人姓名'),  # needs_capture:value_source
            DeclarationEntry(name='transfer_time', path=f'$.transfer_time', type='integer', state='carry', ui_kind='number', description='转派时间'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number', description='发起人ID'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='发起人姓名'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='发起时间'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
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
