"""fin.audit.carbon_copy_add —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): audit_no, audit_type, audit_name, callback_namespace, callback_method, audit_msg, audit_note
溯源统计: column=20, 无zh=3 | fe_high=0, enum=0
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

AUDIT_CARBON_COPY_ADD: Final[EndpointSpec] = EndpointSpec(
    id='fin.audit.carbon_copy_add',
    system='fin',
    service='fin-service',
    name='Audit.carbonCopyAdd',
    description='Audit.carbonCopyAdd' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/audit/carbonCopyAdd',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='audit_id', path=f'$.audit_id', type='integer', state='form', ui_kind='number', default='0', description='审批ID'),
            DeclarationEntry(name='carbon_copy_ids', path=f'$.carbon_copy_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='audit_no', path=f'$.audit_no', type='string', state='carry', ui_kind='text', description='审批编号'),  # needs_capture:value_source
            DeclarationEntry(name='audit_flow_id', path=f'$.audit_flow_id', type='integer', state='carry', ui_kind='number', description='审批流配置ID'),
            DeclarationEntry(name='audit_type', path=f'$.audit_type', type='string', state='carry', ui_kind='text', description='审批类型'),  # needs_capture:value_source
            DeclarationEntry(name='audit_name', path=f'$.audit_name', type='string', state='carry', ui_kind='text', description='审批名称'),  # needs_capture:value_source
            DeclarationEntry(name='type', path=f'$.type', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='string', state='carry', ui_kind='text', description='业务ID'),
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='carry', ui_kind='number', description='审批状态 1待处理 2通过 3驳回 4撤销'),
            DeclarationEntry(name='is_history', path=f'$.is_history', type='integer', state='carry', ui_kind='number', description='是否历史数据 1是'),
            DeclarationEntry(name='audit_end_time', path=f'$.audit_end_time', type='integer', state='carry', ui_kind='number', description='审批完成时间'),
            DeclarationEntry(name='cancel_remark', path=f'$.cancel_remark', type='string', state='carry', ui_kind='text', description='撤销描述'),
            DeclarationEntry(name='current_node_id', path=f'$.current_node_id', type='integer', state='carry', ui_kind='number', description='当前节点ID'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number', description='发起人ID'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='发起人姓名'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='发起时间'),
            DeclarationEntry(name='callback_namespace', path=f'$.callback_namespace', type='string', state='carry', ui_kind='text', description='回调命名空间'),  # needs_capture:value_source
            DeclarationEntry(name='callback_method', path=f'$.callback_method', type='string', state='carry', ui_kind='text', description='回调方法名'),  # needs_capture:value_source
            DeclarationEntry(name='callback_data', path=f'$.callback_data', type='string', state='carry', ui_kind='textarea', description='回调数据'),
            DeclarationEntry(name='callback_res', path=f'$.callback_res', type='string', state='carry', ui_kind='text', description='回调结果 '),
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='carry', ui_kind='text', description='审批回显信息'),  # needs_capture:value_source
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='carry', ui_kind='text', description='审批人备注'),  # needs_capture:value_source
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
