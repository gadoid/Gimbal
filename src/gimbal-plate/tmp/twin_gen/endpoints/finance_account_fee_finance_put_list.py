"""fin.account_fee.finance_put_list —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): main_id, customer_id, put_settle_object_id, symbol, pay_settle_object_id, currency, customer_put_date, sort_field, sort_order
溯源统计: column=6, lang=4, builtin=4, 无zh=3 | fe_high=0, enum=1
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

ACCOUNT_FEE_FINANCE_PUT_LIST: Final[EndpointSpec] = EndpointSpec(
    id='fin.account_fee.finance_put_list',
    system='fin',
    service='fin-service',
    name='AccountFee.financePutList',
    description='AccountFee.financePutList' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/accountFee/financePutList',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='number', required=True, default='0', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='number', required=True, default='0', description='下单客户名称'),  # zh_ambiguous
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', ui_kind='number', required=True, default='0', description='应收结算对象'),  # zh_ambiguous
            DeclarationEntry(name='account_type', path=f'$.account_type', type='integer', state='form', ui_kind='number', default='0', description='0物流对账单  1对账单补件类型一， 对账单补件类型二'),
            DeclarationEntry(name='symbol', path=f'$.symbol', type='integer', state='form', ui_kind='number', default='0', description='应收应付 0 应付  1应收'),  # zh_ambiguous
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', required=True, description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', required=True, description='每页条数'),
            DeclarationEntry(name='operate_type', path=f'$.operate_type', type='integer', state='form', ui_kind='number', default='0', description='操作类型 0费用维度 1提单维度'),
            DeclarationEntry(name='search_style', path=f'$.search_style', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', ui_kind='number', default='0', description='应付结算对象'),  # zh_ambiguous
            DeclarationEntry(name='contain_fee_type', path=f'$.contain_fee_type', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', ui_kind='text', description='币值  '),  # zh_ambiguous
            DeclarationEntry(name='atd_time', path=f'$.atd_time', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='customer_period', path=f'$.customer_period', type='integer', state='form', ui_kind='number', description='客户账期'),
            DeclarationEntry(name='customer_put_date', path=f'$.customer_put_date', type='integer', state='form', ui_kind='number', default='0', description='客户应收日'),  # zh_ambiguous
            DeclarationEntry(name='sort_field', path=f'$.sort_field', type='string', state='carry', ui_kind='text', required=True, description='排序字段'),  # needs_capture:value_source
            DeclarationEntry(name='sort_order', path=f'$.sort_order', type='string', state='carry', ui_kind='select', required=True, description='排序方向', enum=['asc', 'desc']),  # needs_capture:enum_required
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
