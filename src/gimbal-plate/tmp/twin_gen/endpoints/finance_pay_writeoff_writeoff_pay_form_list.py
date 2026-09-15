"""fin.pay_writeoff.writeoff_pay_form_list —— 孪生生成器产物(请求面;行为面归场景用例)。

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

PAY_WRITEOFF_WRITEOFF_PAY_FORM_LIST: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_writeoff.writeoff_pay_form_list',
    system='fin',
    service='fin-service',
    name='PayWriteoff.writeoffPayFormList',
    description='PayWriteoff.writeoffPayFormList' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payWriteoff/writeoffPayFormList',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_form_ids', path=f'$.pay_form_ids', type='string', state='form', required=True),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', default='0', description='业务ID'),
            DeclarationEntry(name='check_ids', path=f'$.check_ids', type='string', state='form'),
            DeclarationEntry(name='pay_form_no', path=f'$.pay_form_no', type='string', state='form', description='付款单编号'),
            DeclarationEntry(name='pay_form_name', path=f'$.pay_form_name', type='string', state='form'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='customer_main_id', path=f'$.customer_main_id', type='integer', state='form', default='0', description='对客主体ID'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', default='0', description='费用主体ID'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', description='币值'),
            DeclarationEntry(name='real_total_start', path=f'$.real_total_start', type='string', state='form'),
            DeclarationEntry(name='real_total_end', path=f'$.real_total_end', type='string', state='form'),
            DeclarationEntry(name='pay_settle_object_receive_account', path=f'$.pay_settle_object_receive_account', type='string', state='form', description='应付结算对象收款账户'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='form', default='1', description='核销状态 1未核销 2已核销 3部分核销'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', default='0', description='发起人ID'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form'),
            DeclarationEntry(name='generate_time_start', path=f'$.generate_time_start', type='string', state='form'),
            DeclarationEntry(name='generate_time_end', path=f'$.generate_time_end', type='string', state='form'),
            DeclarationEntry(name='supplier_number', path=f'$.supplier_number', type='string', state='form', description='供应商编号'),
            DeclarationEntry(name='currency_is_turn', path=f'$.currency_is_turn', type='integer', state='form', description='1未折币 2部分折币 3全部折币'),
            DeclarationEntry(name='account_create_id', path=f'$.account_create_id', type='string', state='form', description='对账单创建者ID'),
            DeclarationEntry(name='download_num', path=f'$.download_num', type='integer', state='form', default='0', description='付款单下载次数'),
            DeclarationEntry(name='statement_receipt_time_start', path=f'$.statement_receipt_time_start', type='string', state='form'),
            DeclarationEntry(name='statement_receipt_time_end', path=f'$.statement_receipt_time_end', type='string', state='form'),
            DeclarationEntry(name='sort_order', path=f'$.sort_order', type='string', state='form', default='desc'),
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
