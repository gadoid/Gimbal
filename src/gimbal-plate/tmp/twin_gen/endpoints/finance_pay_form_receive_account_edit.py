"""fin.pay_form.receive_account_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): pay_form_no, pay_settle_object_address, pay_settle_object_receive_account, statement_receipt_time, cancel_by
溯源统计: column=40, 无zh=3 | fe_high=0, enum=0
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

PAY_FORM_RECEIVE_ACCOUNT_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_form.receive_account_edit',
    system='fin',
    service='fin-service',
    name='PayForm.receiveAccountEdit',
    description='PayForm.receiveAccountEdit' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payForm/receiveAccountEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_form_id', path=f'$.pay_form_id', type='string', state='form', ui_kind='text', required=True, description='付款单ID'),
            DeclarationEntry(name='finance_id', path=f'$.finance_id', type='string', state='form', ui_kind='text', required=True),
            DeclarationEntry(name='pay_demand_id', path=f'$.pay_demand_id', type='integer', state='carry', ui_kind='number', description='付款需求ID'),
            DeclarationEntry(name='pay_form_no', path=f'$.pay_form_no', type='string', state='carry', ui_kind='text', description='付款单编号'),  # needs_capture:value_source
            DeclarationEntry(name='pay_form_name', path=f'$.pay_form_name', type='string', state='carry', ui_kind='textarea'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='string', state='carry', ui_kind='textarea', description='下单客户ID'),
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='carry', ui_kind='textarea', description='下单客户名称'),
            DeclarationEntry(name='customer_main_id', path=f'$.customer_main_id', type='string', state='carry', ui_kind='textarea', description='对客订单主体ID'),
            DeclarationEntry(name='customer_main_name', path=f'$.customer_main_name', type='string', state='carry', ui_kind='textarea', description='对客订单主体'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='carry', ui_kind='number', description='费用主体ID'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='carry', ui_kind='text', description='费用主体'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='carry', ui_kind='number', description='应付结算对象ID'),
            DeclarationEntry(name='pay_settle_object', path=f'$.pay_settle_object', type='string', state='carry', ui_kind='text', description='应付结算对象'),
            DeclarationEntry(name='pay_settle_object_address', path=f'$.pay_settle_object_address', type='string', state='carry', ui_kind='text', description='应付结算对象地址'),  # needs_capture:value_source
            DeclarationEntry(name='pay_settle_object_receive_account', path=f'$.pay_settle_object_receive_account', type='string', state='carry', ui_kind='text', description='应付结算对象收款账户'),  # needs_capture:value_source
            DeclarationEntry(name='pay_settle_object_type', path=f'$.pay_settle_object_type', type='integer', state='carry', ui_kind='number', description='子订单类型  0 对客  1协同  2对商 3对客商'),
            DeclarationEntry(name='currency_is_turn', path=f'$.currency_is_turn', type='integer', state='carry', ui_kind='number', description='1未折币 2部分折币 3全部折币'),
            DeclarationEntry(name='account_create_id', path=f'$.account_create_id', type='string', state='carry', ui_kind='text', description='对账单创建者ID'),
            DeclarationEntry(name='account_create_name', path=f'$.account_create_name', type='string', state='carry', ui_kind='text', description='对账单创建者姓名'),
            DeclarationEntry(name='supplier_number', path=f'$.supplier_number', type='string', state='carry', ui_kind='text', description='供应商编号'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='carry', ui_kind='text', description='币制'),
            DeclarationEntry(name='real_total', path=f'$.real_total', type='number', state='carry', ui_kind='number', description='付款金额'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='carry', ui_kind='number', description='付款单状态 2已生效 3已作废'),
            DeclarationEntry(name='pay_writeoff_id', path=f'$.pay_writeoff_id', type='string', state='carry', ui_kind='text', description='核销ID'),
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='carry', ui_kind='number', description='核销状态 1未核销 2已核销 3部分核销'),
            DeclarationEntry(name='un_writeoff_amount', path=f'$.un_writeoff_amount', type='number', state='carry', ui_kind='number', description='未核销金额'),
            DeclarationEntry(name='use_writeoff_amount', path=f'$.use_writeoff_amount', type='number', state='carry', ui_kind='number', description='已核销金额'),
            DeclarationEntry(name='writeoff_force_audit_status', path=f'$.writeoff_force_audit_status', type='integer', state='carry', ui_kind='number', description='强制核销审批状态 0无状态 1审核中 2审核通过 3审核驳回 4审核撤销'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', ui_kind='text', description='付款单备注'),
            DeclarationEntry(name='download_num', path=f'$.download_num', type='integer', state='carry', ui_kind='number', description='付款单下载次数'),
            DeclarationEntry(name='statement_receipt_time', path=f'$.statement_receipt_time', type='string', state='carry', ui_kind='text', description='流水收付款时间'),  # needs_capture:value_source
            DeclarationEntry(name='cancel_id', path=f'$.cancel_id', type='integer', state='carry', ui_kind='number', description='作废人ID'),
            DeclarationEntry(name='cancel_by', path=f'$.cancel_by', type='string', state='carry', ui_kind='text', description='作废人'),  # needs_capture:value_source
            DeclarationEntry(name='cancel_time', path=f'$.cancel_time', type='integer', state='carry', ui_kind='number', description='作废时间'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number', description='创建人ID'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建人'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number', description='更新人ID'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新人'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number', description='更新时间'),
            DeclarationEntry(name='cancel_remark', path=f'$.cancel_remark', type='string', state='carry', ui_kind='text', description='作废原因'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='generate_time', path=f'$.generate_time', type='integer', state='carry', ui_kind='number', description='生成时间'),
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
