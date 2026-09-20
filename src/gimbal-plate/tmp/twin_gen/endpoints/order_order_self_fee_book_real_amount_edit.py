"""fin.order_self_fee.book_real_amount_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): order_self_id, service_project, order_id, order_self_fee_id
溯源统计: column=14, 无zh=9, lang=2 | fe_high=0, enum=1
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

ORDER_SELF_FEE_BOOK_REAL_AMOUNT_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_self_fee.book_real_amount_edit',
    system='fin',
    service='fin-service',
    name='操作',
    description='操作' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderSelfFee/bookRealAmountEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_self_id', path=f'$.order_self_id', type='integer', state='form', ui_kind='number', default='0', description='订单id'),  # zh_ambiguous
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='form', ui_kind='text', description='服务项目'),  # zh_ambiguous
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', description='操作', enum=['check', 'submit']),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', ui_kind='number', default='0', description='业务订单ID'),  # zh_ambiguous
            DeclarationEntry(name='order_self_fee_id', path=f'$.order_self_fee_id', type='string', state='carry', ui_kind='text'),  # needs_capture:value_source
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='carry', ui_kind='text', description='币制'),
            DeclarationEntry(name='settle_object_id', path=f'$.settle_object_id', type='integer', state='carry', ui_kind='number', description='结算对象id'),
            DeclarationEntry(name='settle_object', path=f'$.settle_object', type='string', state='carry', ui_kind='text', description='结算对象'),
            DeclarationEntry(name='specs', path=f'$.specs', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='cost_name', path=f'$.cost_name', type='string', state='carry', ui_kind='text', description='费用名称'),
            DeclarationEntry(name='cost_id', path=f'$.cost_id', type='integer', state='carry', ui_kind='number', description='费用id'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', ui_kind='text', description='备注'),
            DeclarationEntry(name='unit', path=f'$.unit', type='string', state='carry', ui_kind='text', description='单位'),
            DeclarationEntry(name='unit_price', path=f'$.unit_price', type='number', state='carry', ui_kind='number', description='单价金额'),
            DeclarationEntry(name='num', path=f'$.num', type='integer', state='carry', ui_kind='number', description='数量'),
            DeclarationEntry(name='symbol', path=f'$.symbol', type='integer', state='carry', ui_kind='number', description='0 应付 1应收'),
            DeclarationEntry(name='unique_id', path=f'$.unique_id', type='string', state='carry', ui_kind='text', description='唯一标记  同源费用标记一致'),
            DeclarationEntry(name='pay_sync_status', path=f'$.pay_sync_status', type='integer', state='carry', ui_kind='number', description='前端同步标识 0不同步, 1同步'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
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
