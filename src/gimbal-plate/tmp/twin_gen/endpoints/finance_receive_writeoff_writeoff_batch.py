"""fin.receive_writeoff.writeoff_batch —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): estimate_no, main_id, create_id, create_time, receive_invoice_batch_no, link_audit_status, customer_id, currency, pay_invoice_batch_no, exchange_rate_no, month, original_currency, target_currency, update_id, update_time, receive_invoice_apply_no, cancel_status, put_settle_object_id, invoice_status, invoice_no, writeoff_status, create_by, main_name
溯源统计: frontend=30, rule=8, column=7, 无zh=2, lang=1 | fe_high=31, enum=2
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

RECEIVE_WRITEOFF_WRITEOFF_BATCH: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_writeoff.writeoff_batch',
    system='fin',
    service='fin-service',
    name='操作',
    description='操作' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveWriteoff/writeoffBatch',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='writeoff_mode', path=f'$.writeoff_mode', type='string', state='form', ui_kind='select', required=True, description='核销模式', enum=['invoice', 'fee', 'order']),
            DeclarationEntry(name='writeoff_object', path=f'$.writeoff_object', type='string', state='form', ui_kind='text', required=True, description='核销对象'),
            DeclarationEntry(name='un_writeoff_amount_cny_total', path=f'$.un_writeoff_amount_cny_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='未核销金额总计CNY'),
            DeclarationEntry(name='un_writeoff_amount_usd_total', path=f'$.un_writeoff_amount_usd_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='未核销金额总计USD'),
            DeclarationEntry(name='use_writeoff_amount_cny_total', path=f'$.use_writeoff_amount_cny_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='已核销金额总计CNY'),
            DeclarationEntry(name='use_writeoff_amount_usd_total', path=f'$.use_writeoff_amount_usd_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='已核销金额总计USD'),
            DeclarationEntry(name='statement_amount_cny_total', path=f'$.statement_amount_cny_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='流水金额总计CNY'),
            DeclarationEntry(name='statement_amount_usd_total', path=f'$.statement_amount_usd_total', type='number', state='form', ui_kind='number', required=True, default='0.00', description='流水金额总计USD'),
            DeclarationEntry(name='estimate_no', path=f'$.estimate_no', type='string', state='carry', ui_kind='text', description='暂估凭证ID'),  # needs_capture:value_source
            DeclarationEntry(name='estimate', path=f'$.estimate', type='string', state='carry', ui_kind='text', description='暂估范围'),
            DeclarationEntry(name='lock', path=f'$.lock', type='string', state='carry', ui_kind='text', description='锁定时间'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='select', default='0', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', ui_kind='select', default='0', description='创建人'),  # zh_ambiguous
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='form', ui_kind='text', default='0', description='创建时间'),  # zh_ambiguous
            DeclarationEntry(name='receive_invoice_batch_no', path=f'$.receive_invoice_batch_no', type='string', state='carry', ui_kind='text', description='开票批次ID'),  # zh_ambiguous
            DeclarationEntry(name='batch_apply_name', path=f'$.batch_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='carry', ui_kind='text', description='提单号批量'),
            DeclarationEntry(name='link_role', path=f'$.link_role', type='integer', state='carry', ui_kind='select', default='0', description='关联身份'),
            DeclarationEntry(name='link_apply_no', path=f'$.link_apply_no', type='string', state='carry', ui_kind='text', description='关联对向申请ID'),
            DeclarationEntry(name='link_audit_status', path=f'$.link_audit_status', type='integer', state='carry', ui_kind='select', default='0', description='关联应收审核状态'),  # zh_ambiguous
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='text', default='0', description='下单客户名称'),  # zh_ambiguous
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='carry', ui_kind='select', description='开票申请币制'),  # zh_ambiguous
            DeclarationEntry(name='batch_status', path=f'$.batch_status', type='integer', state='carry', ui_kind='select', description='批次状态'),
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='form', ui_kind='select', description='审核状态'),
            DeclarationEntry(name='pay_invoice_batch_no', path=f'$.pay_invoice_batch_no', type='string', state='carry', ui_kind='text', description='开票批次ID'),  # zh_ambiguous
            DeclarationEntry(name='exchange_rate_no', path=f'$.exchange_rate_no', type='string', state='carry', ui_kind='text', description='汇率ID'),  # needs_capture:value_source
            DeclarationEntry(name='month', path=f'$.month', type='string', state='carry', ui_kind='text', description='汇率月份'),  # needs_capture:value_source
            DeclarationEntry(name='original_currency', path=f'$.original_currency', type='string', state='carry', ui_kind='select', description='原始币制'),  # needs_capture:value_source
            DeclarationEntry(name='target_currency', path=f'$.target_currency', type='string', state='carry', ui_kind='select', description='目标币制'),  # needs_capture:value_source
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='select', default='0', description='更新人'),  # zh_ambiguous
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='text', default='0', description='更新时间'),  # zh_ambiguous
            DeclarationEntry(name='receive_invoice_apply_no', path=f'$.receive_invoice_apply_no', type='string', state='carry', ui_kind='text', description='开票申请ID'),  # zh_ambiguous
            DeclarationEntry(name='cancel_status', path=f'$.cancel_status', type='integer', state='carry', ui_kind='select', description='开票申请状态'),  # zh_ambiguous
            DeclarationEntry(name='invoice_apply_name', path=f'$.invoice_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
            DeclarationEntry(name='link_batch_no', path=f'$.link_batch_no', type='string', state='carry', ui_kind='text', description='关联对向批次ID'),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='carry', ui_kind='select', default='0', description='应收结算对象'),  # zh_ambiguous
            DeclarationEntry(name='invoice_status', path=f'$.invoice_status', type='integer', state='carry', ui_kind='select', default='0', description='登记状态'),  # zh_ambiguous
            DeclarationEntry(name='invoice_no', path=f'$.invoice_no', type='string', state='carry', ui_kind='text', description='关联发票号'),  # zh_ambiguous
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='form', ui_kind='select', default='1', description='核销状态'),  # zh_ambiguous
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', description='操作', enum=['check', 'submit']),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='form', ui_kind='text', description='创建人'),  # zh_ambiguous
            DeclarationEntry(name='fee_match_type', path=f'$.fee_match_type', type='integer', state='form', ui_kind='number', default='0', description='匹配费用方式 1系统自动对应 2手动选择对应'),
            DeclarationEntry(name='statement', path=f'$.statement', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', ui_kind='text', description='审批人备注'),
            DeclarationEntry(name='writeoff_name', path=f'$.writeoff_name', type='string', state='form', ui_kind='text', description='应收核销记录名称'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='form', ui_kind='text', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='form', ui_kind='text', description='审批回显信息'),
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
