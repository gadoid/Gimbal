"""fin.pay_account.amount_pay_account_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

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

PAY_ACCOUNT_AMOUNT_PAY_ACCOUNT_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_account.amount_pay_account_edit',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payAccount/amountPayAccountEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', required=True, default='0', description='客户ID'),
            DeclarationEntry(name='account_type', path=f'$.account_type', type='integer', state='form', default='0', description='0物流对账单  1对账单补件类型一， 对账单补件类型二'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', description='操作目的'),
            DeclarationEntry(name='operate_type', path=f'$.operate_type', type='integer', state='form', default='0', description='操作类型 0费用维度 1提单维度'),
            DeclarationEntry(name='pay_account_id', path=f'$.pay_account_id', type='integer', state='form', default='0', description='应付对账'),
            DeclarationEntry(name='pay_account_no', path=f'$.pay_account_no', type='string', state='form', description='应付对账编号'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='form', description='费用主体名称'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', default='0', description='费用主体ID'),
            DeclarationEntry(name='select_list', path=f'$.select_list', type='string', state='form'),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='pay_settle_object', path=f'$.pay_settle_object', type='string', state='form', description='应收结算对象'),
            DeclarationEntry(name='account_simple_name', path=f'$.account_simple_name', type='string', state='form', description='对账批次简称'),
            DeclarationEntry(name='cost_ids', path=f'$.cost_ids', type='string', state='form'),
            DeclarationEntry(name='selection_time', path=f'$.selection_time', type='string', state='form'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', default='0', description='业务订单ID'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', default='0', description='服务策略ID'),
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
