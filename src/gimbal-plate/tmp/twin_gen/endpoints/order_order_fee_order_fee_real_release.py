"""fin.order_fee.order_fee_real_release —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): order_id, customer_id, flow_type
溯源统计: column=8, 无zh=4, lang=1 | fe_high=0, enum=1
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

ORDER_FEE_ORDER_FEE_REAL_RELEASE: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_fee.order_fee_real_release',
    system='fin',
    service='fin-service',
    name='操作',
    description='操作' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderFee/orderFeeRealRelease',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', ui_kind='number', default='0', description='业务订单ID'),  # zh_ambiguous
            DeclarationEntry(name='order_fee_real_ids', path=f'$.order_fee_real_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='error_continue', path=f'$.error_continue', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', description='操作', enum=['check', 'submit']),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='form', ui_kind='text', description='审批回显信息'),
            DeclarationEntry(name='real_fee_status', path=f'$.real_fee_status', type='integer', state='form', ui_kind='number', default='0', description='业务订单状态(原实际费用状态)  0创建中  1 审核中  2已锁定  3审核驳回 4撤销 5作废'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='number', default='0', description='客户ID'),  # zh_ambiguous
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='form', ui_kind='text', description='下单客户名称'),
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', ui_kind='text', description='提单号'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', ui_kind='text', description='审批人备注'),
            DeclarationEntry(name='flow_type', path=f'$.flow_type', type='string', state='form', ui_kind='text', description='审批流配置类型'),  # zh_ambiguous
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', ui_kind='number'),
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
