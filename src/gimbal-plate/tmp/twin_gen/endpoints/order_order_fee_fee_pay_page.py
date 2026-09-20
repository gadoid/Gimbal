"""fin.order_fee.fee_pay_page —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): symbol, sort_field, sort_order
溯源统计: builtin=4, column=1, 无zh=1 | fe_high=0, enum=1
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

ORDER_FEE_FEE_PAY_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_fee.fee_pay_page',
    system='fin',
    service='fin-service',
    name='OrderFee.feePayPage',
    description='OrderFee.feePayPage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderFee/feePayPage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='symbol', path=f'$.symbol', type='integer', state='form', ui_kind='number', default='0', description='应收应付 0 应付  1应收'),  # zh_ambiguous
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', required=True, description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', required=True, description='每页条数'),
            DeclarationEntry(name='is_page', path=f'$.is_page', type='string', state='form', ui_kind='text'),
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
