"""fin.order_fee.real_amount_submit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): order_id, order_no, customer_id, flow_type, discount_status
溯源统计: column=16, 无zh=6, lang=1 | fe_high=0, enum=1
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

ORDER_FEE_REAL_AMOUNT_SUBMIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_fee.real_amount_submit',
    system='fin',
    service='fin-service',
    name='操作',
    description='操作' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderFee/realAmountSubmit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', description='操作', enum=['check', 'submit']),
            DeclarationEntry(name='box_no_continue', path=f'$.box_no_continue', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='check_self_fee_status', path=f'$.check_self_fee_status', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', ui_kind='number', default='0', description='业务订单ID'),  # zh_ambiguous
            DeclarationEntry(name='order_fee_real_ids', path=f'$.order_fee_real_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='main_ids', path=f'$.main_ids', type='string', state='form', ui_kind='text', description='主体顺序ID'),
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='form', ui_kind='text', description='审批回显信息'),
            DeclarationEntry(name='order_no', path=f'$.order_no', type='string', state='form', ui_kind='text', description='业务订单ID'),  # zh_ambiguous
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='number', default='0', description='客户ID'),  # zh_ambiguous
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='form', ui_kind='text', description='下单客户名称'),
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', ui_kind='text', description='提单号'),
            DeclarationEntry(name='pol', path=f'$.pol', type='string', state='form', ui_kind='text', description='起运港'),
            DeclarationEntry(name='pod', path=f'$.pod', type='string', state='form', ui_kind='text', description='卸货港'),
            DeclarationEntry(name='del', path=f'$.del', type='string', state='form', ui_kind='text', description='目的港'),
            DeclarationEntry(name='volume', path=f'$.volume', type='string', state='form', ui_kind='text', description='箱型箱量'),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', ui_kind='text', description='审批人备注'),
            DeclarationEntry(name='flow_type', path=f'$.flow_type', type='string', state='form', ui_kind='text', description='审批流配置类型'),  # zh_ambiguous
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', ui_kind='number'),
            DeclarationEntry(name='atd', path=f'$.atd', type='integer', state='form', ui_kind='number', default='0', description='实际开航日'),
            DeclarationEntry(name='discount_status', path=f'$.discount_status', type='integer', state='form', ui_kind='number', default='2', description='折扣标识   0正常  1异常  2全不参与补贴 3不符合的折扣规则 4折扣规则过期 5未维护ATD'),  # zh_ambiguous
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', ui_kind='number', description='服务策略ID'),
            DeclarationEntry(name='container', path=f'$.container', type='array', state='form', ui_kind='unknown',
                children=[
                DeclarationEntry(name='order_container_id', path=f'$.container.order_container_id', type='string', state='form', ui_kind='text'),
                DeclarationEntry(name='order_id', path=f'$.container.order_id', type='integer', state='form', ui_kind='number', description='关联 sys_order订单表'),
                DeclarationEntry(name='box_type', path=f'$.container.box_type', type='string', state='form', ui_kind='text', description='箱型'),
                DeclarationEntry(name='box_num', path=f'$.container.box_num', type='string', state='form', ui_kind='text', description='箱量'),
                DeclarationEntry(name='box_no', path=f'$.container.box_no', type='string', state='form', ui_kind='textarea', description='箱号'),
                DeclarationEntry(name='seal_number', path=f'$.container.seal_number', type='string', state='form', ui_kind='text', description='封号'),
                DeclarationEntry(name='sea_trans_unit_price', path=f'$.container.sea_trans_unit_price', type='number', state='form', ui_kind='number', description='海运费单价'),
                DeclarationEntry(name='create_id', path=f'$.container.create_id', type='integer', state='form', ui_kind='number'),
                DeclarationEntry(name='create_by', path=f'$.container.create_by', type='string', state='form', ui_kind='text'),
                DeclarationEntry(name='create_time', path=f'$.container.create_time', type='integer', state='form', ui_kind='number'),
                DeclarationEntry(name='delete_time', path=f'$.container.delete_time', type='integer', state='form', ui_kind='number', description='删除时间'),
                DeclarationEntry(name='sys_upttime', path=f'$.container.sys_upttime', type='string', state='form', ui_kind='text'),
                ]),
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
