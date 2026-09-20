"""fin.pay_writeoff.writeoff_batch_force —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): main_id, main_name
溯源统计: column=9, rule=7, 无zh=2 | fe_high=0, enum=1
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

PAY_WRITEOFF_WRITEOFF_BATCH_FORCE: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_writeoff.writeoff_batch_force',
    system='fin',
    service='fin-service',
    name='操作',
    description='操作' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payWriteoff/writeoffBatchForce',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='writeoff_object', path=f'$.writeoff_object', type='string', state='form', ui_kind='text', required=True, description='核销对象'),
            DeclarationEntry(name='un_writeoff_amount_cny_total', path=f'$.un_writeoff_amount_cny_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='未核销金额总计CNY'),
            DeclarationEntry(name='un_writeoff_amount_usd_total', path=f'$.un_writeoff_amount_usd_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='未核销金额总计USD'),
            DeclarationEntry(name='use_writeoff_amount_cny_total', path=f'$.use_writeoff_amount_cny_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='已核销金额总计CNY'),
            DeclarationEntry(name='use_writeoff_amount_usd_total', path=f'$.use_writeoff_amount_usd_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='已核销金额总计USD'),
            DeclarationEntry(name='statement_amount_cny_total', path=f'$.statement_amount_cny_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='流水金额总计CNY'),
            DeclarationEntry(name='statement_amount_usd_total', path=f'$.statement_amount_usd_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='流水金额总计USD'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', description='操作', enum=['check', 'submit']),
            DeclarationEntry(name='fee_match_type', path=f'$.fee_match_type', type='integer', state='form', ui_kind='number', default='0', description='匹配费用方式 1系统自动对应 2手动选择对应'),
            DeclarationEntry(name='statement', path=f'$.statement', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', ui_kind='text', description='审批人备注'),
            DeclarationEntry(name='writeoff_name', path=f'$.writeoff_name', type='string', state='form', ui_kind='text', description='应收核销记录名称'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='number', default='0', description='费用主体ID'),  # zh_ambiguous
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='form', ui_kind='text', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='form', ui_kind='text', description='审批回显信息'),
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
