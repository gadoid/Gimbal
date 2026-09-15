"""fin.account_fee.finance_pay_export —— 孪生生成器产物(请求面;行为面归场景用例)。

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

ACCOUNT_FEE_FINANCE_PAY_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.account_fee.finance_pay_export',
    system='fin',
    service='fin-service',
    name='AccountFee.financePayExport',
    description='AccountFee.financePayExport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/accountFee/financePayExport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', required=True, default='0', description='客户ID'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', required=True, default='0', description='费用主体ID'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', required=True, default='0', description='应收结算对象ID'),
            DeclarationEntry(name='search_style', path=f'$.search_style', type='string', state='form'),
            DeclarationEntry(name='account_type', path=f'$.account_type', type='integer', state='form', default='0', description='0物流对账单  1对账单补件类型一， 对账单补件类型二'),
            DeclarationEntry(name='symbol', path=f'$.symbol', type='integer', state='form', default='0', description='应收应付 0 应付  1应收'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
            DeclarationEntry(name='operate_type', path=f'$.operate_type', type='integer', state='form', default='0', description='操作类型 0费用维度 1提单维度'),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='contain_fee_type', path=f'$.contain_fee_type', type='string', state='form'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', description='币值'),
            DeclarationEntry(name='atd_time', path=f'$.atd_time', type='string', state='form'),
            DeclarationEntry(name='book_supplier_period', path=f'$.book_supplier_period', type='integer', state='form', default='0', description='供应商账期'),
            DeclarationEntry(name='book_supplier_pay_date', path=f'$.book_supplier_pay_date', type='integer', state='form', default='0', description='供应商应付日'),
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
