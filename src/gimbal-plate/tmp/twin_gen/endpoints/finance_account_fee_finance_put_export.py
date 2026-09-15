"""fin.account_fee.finance_put_export —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): main_id, put_settle_object_id
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

ACCOUNT_FEE_FINANCE_PUT_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.account_fee.finance_put_export',
    system='fin',
    service='fin-service',
    name='AccountFee.financePutExport',
    description='AccountFee.financePutExport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/accountFee/financePutExport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='carry', required=True, default='0', description='费用主体ID'),  # needs_capture:value_source
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='carry', required=True, default='0', description='客户ID', value_source=ValueSource(view='customer_list', column='customer_id')),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='carry', required=True, default='0', description='应收结算对象ID'),  # needs_capture:value_source
            DeclarationEntry(name='account_type', path=f'$.account_type', type='integer', state='form', default='0', description='0物流对账单  1对账单补件类型一， 对账单补件类型二'),
            DeclarationEntry(name='symbol', path=f'$.symbol', type='integer', state='form', default='0', description='应收应付 0 应付  1应收'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
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
