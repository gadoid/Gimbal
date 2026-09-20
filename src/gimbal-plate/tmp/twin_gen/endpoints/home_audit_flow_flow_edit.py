"""fin.audit_flow.flow_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): flow_type, flow_name, callback_namespace, callback_method
溯源统计: column=15, 无zh=4, lang=2 | fe_high=0, enum=1
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

AUDIT_FLOW_FLOW_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.audit_flow.flow_edit',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/auditFlow/flowEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='node_list', path=f'$.node_list', type='string', state='form', ui_kind='text', description='审批流程设置'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='submit', description='操作目的', enum=['check', 'submit']),
            DeclarationEntry(name='flow_id', path=f'$.flow_id', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='flow_desc', path=f'$.flow_desc', type='string', state='form', ui_kind='text', description='备注'),
            DeclarationEntry(name='carbon_copy_list', path=f'$.carbon_copy_list', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='audit_flow_id', path=f'$.audit_flow_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='flow_type', path=f'$.flow_type', type='string', state='carry', ui_kind='text', description='审批流配置类型'),  # needs_capture:value_source
            DeclarationEntry(name='flow_name', path=f'$.flow_name', type='string', state='carry', ui_kind='text', description='审批流配置名称'),  # needs_capture:value_source
            DeclarationEntry(name='type', path=f'$.type', type='string', state='carry', ui_kind='text', description='审批流模块'),
            DeclarationEntry(name='callback_namespace', path=f'$.callback_namespace', type='string', state='carry', ui_kind='text', description='回调命名空间'),  # needs_capture:value_source
            DeclarationEntry(name='callback_method', path=f'$.callback_method', type='string', state='carry', ui_kind='text', description='回调方法'),  # needs_capture:value_source
            DeclarationEntry(name='carbon_copy_id', path=f'$.carbon_copy_id', type='string', state='carry', ui_kind='text', description='抄送人ID'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='carry', ui_kind='number', description='审批配置状态  2生效  3失效'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number', description='创建人ID'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建人姓名'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number', description='更新人ID'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新人姓名'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number', description='更新人时间'),
            DeclarationEntry(name='delete_time', path=f'$.delete_time', type='integer', state='carry', ui_kind='number', description='删除时间 0为未删除'),
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
