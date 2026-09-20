"""fin.order_self.order_self_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): order_self_id, service_items, order_id
溯源统计: column=16, 无zh=6, lang=2 | fe_high=0, enum=1
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

ORDER_SELF_ORDER_SELF_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_self.order_self_edit',
    system='fin',
    service='fin-service',
    name='操作',
    description='操作' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderSelf/orderSelfEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_self_id', path=f'$.order_self_id', type='integer', state='form', ui_kind='number', default='0', description='订单id'),  # zh_ambiguous
            DeclarationEntry(name='entrust_status', path=f'$.entrust_status', type='integer', state='form', ui_kind='number', default='1', description='1未分发 2已分发'),
            DeclarationEntry(name='service_items', path=f'$.service_items', type='array', state='form', ui_kind='unknown', description='服务项目'),  # needs_capture:children
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='submit', description='操作', enum=['check', 'submit']),
            DeclarationEntry(name='supplier', path=f'$.supplier', type='array', state='form', ui_kind='unknown',
                children=[
                DeclarationEntry(name='order_supplier_id', path=f'$.supplier.order_supplier_id', type='integer', state='form', ui_kind='number'),
                DeclarationEntry(name='order_id', path=f'$.supplier.order_id', type='integer', state='form', ui_kind='number', description='订单ID'),
                DeclarationEntry(name='isset_supplier', path=f'$.supplier.isset_supplier', type='integer', state='form', ui_kind='number', description='是否无供应商'),
                DeclarationEntry(name='is_primary', path=f'$.supplier.is_primary', type='integer', state='form', ui_kind='number', description='是否是主要供应商 0否  1是'),
                DeclarationEntry(name='supplier_id', path=f'$.supplier.supplier_id', type='integer', state='form', ui_kind='number', description='供应商id'),
                DeclarationEntry(name='supplier_name', path=f'$.supplier.supplier_name', type='string', state='form', ui_kind='text', description='供应商名称'),
                DeclarationEntry(name='settle_object_id', path=f'$.supplier.settle_object_id', type='integer', state='form', ui_kind='number', description='结算对象id'),
                DeclarationEntry(name='user_id', path=f'$.supplier.user_id', type='integer', state='form', ui_kind='number', description='服务人员'),
                DeclarationEntry(name='user_name', path=f'$.supplier.user_name', type='string', state='form', ui_kind='text', description='服务人员'),
                DeclarationEntry(name='service_item', path=f'$.supplier.service_item', type='string', state='form', ui_kind='text', description='服务项目'),
                DeclarationEntry(name='supplier_period', path=f'$.supplier.supplier_period', type='integer', state='form', ui_kind='number', description='供应商账期'),
                DeclarationEntry(name='settlement_date', path=f'$.supplier.settlement_date', type='integer', state='form', ui_kind='number', description='结算日'),
                DeclarationEntry(name='supplier_pay_date', path=f'$.supplier.supplier_pay_date', type='integer', state='form', ui_kind='number', description='供应商应付日'),
                DeclarationEntry(name='is_manual', path=f'$.supplier.is_manual', type='integer', state='form', ui_kind='number', description='是否手动设置  0否  1是'),
                DeclarationEntry(name='sys_upttime', path=f'$.supplier.sys_upttime', type='string', state='form', ui_kind='text'),
                DeclarationEntry(name='pay_time_limit', path=f'$.supplier.pay_time_limit', type='integer', state='form', ui_kind='number', description='付款时效'),
                DeclarationEntry(name='supplier_pay_date_desc', path=f'$.supplier.supplier_pay_date_desc', type='string', state='form', ui_kind='text', description='应付日计算描述'),
                DeclarationEntry(name='settle_type', path=f'$.supplier.settle_type', type='integer', state='form', ui_kind='number', description='结算方式 1月结 2票结'),
                ]),
            DeclarationEntry(name='self_supplier', path=f'$.self_supplier', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', ui_kind='number', default='0', description='订单ID'),  # zh_ambiguous
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='carry', ui_kind='number', description='1 创建中  2已确认  3已作废'),
            DeclarationEntry(name='insurance_supplier_id', path=f'$.insurance_supplier_id', type='integer', state='carry', ui_kind='number', description='保险供应商id'),
            DeclarationEntry(name='insurance_fee_status', path=f'$.insurance_fee_status', type='integer', state='carry', ui_kind='number', description='保险费用状态'),
            DeclarationEntry(name='customs_clearance_supplier_id', path=f'$.customs_clearance_supplier_id', type='integer', state='carry', ui_kind='number', description='报关供应商'),
            DeclarationEntry(name='customs_clearance_fee_status', path=f'$.customs_clearance_fee_status', type='integer', state='carry', ui_kind='number', description='报关费用状态'),
            DeclarationEntry(name='manifest_fee_status', path=f'$.manifest_fee_status', type='integer', state='carry', ui_kind='number', description='仓单费用状态'),
            DeclarationEntry(name='manifest_supplier_id', path=f'$.manifest_supplier_id', type='integer', state='carry', ui_kind='number', description='仓单供应商id'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建人'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number', description='修改时间'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='修改人'),
            DeclarationEntry(name='delete_time', path=f'$.delete_time', type='integer', state='carry', ui_kind='number', description='删除时间'),
            DeclarationEntry(name='delete_by', path=f'$.delete_by', type='string', state='carry', ui_kind='text', description='删除人'),
            DeclarationEntry(name='delete_id', path=f'$.delete_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number'),
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
