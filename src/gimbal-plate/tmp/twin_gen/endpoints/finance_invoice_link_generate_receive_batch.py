"""fin.invoice_link.generate_receive_batch —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): pay_invoice_apply_id
溯源统计: column=7, 无zh=1 | fe_high=0, enum=1
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

INVOICE_LINK_GENERATE_RECEIVE_BATCH: Final[EndpointSpec] = EndpointSpec(
    id='fin.invoice_link.generate_receive_batch',
    system='fin',
    service='fin-service',
    name='操作',
    description='操作' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/invoiceLink/generateReceiveBatch',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_invoice_apply_id', path=f'$.pay_invoice_apply_id', type='integer', state='form', ui_kind='number', required=True, default='0', description='应付开票申请ID'),  # zh_ambiguous
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='check', description='操作', enum=['check', 'submit']),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', ui_kind='text', description='审批人备注'),
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='form', ui_kind='text', description='审批回显信息'),
            DeclarationEntry(name='code', path=f'$.code', type='string', state='form', ui_kind='text', description='编码'),
            DeclarationEntry(name='flow_type', path=f'$.flow_type', type='string', state='form', ui_kind='text', description='审批流配置类型'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', ui_kind='number', description='关联ID'),
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
