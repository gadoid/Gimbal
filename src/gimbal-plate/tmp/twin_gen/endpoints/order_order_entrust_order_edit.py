"""fin.order_entrust.order_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): customer_contact_name, operator_name, remark, pot, del, terms_payment, terms_transport, pay_type, customer_order_sn, packer, shipper, consignee, notifier, terms_shipment
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

ORDER_ENTRUST_ORDER_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_entrust.order_edit',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderEntrust/orderEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', required=True, default='0', description='业务订单ID'),
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='carry', required=True, description='客户名字', value_source=ValueSource(view='customer_list', column='customer_name')),
            DeclarationEntry(name='customer_contact_name', path=f'$.customer_contact_name', type='string', state='carry', description='客户联系人名字'),  # needs_capture:value_source
            DeclarationEntry(name='operator_name', path=f'$.operator_name', type='string', state='carry', required=True, description='操作名字'),  # needs_capture:value_source
            DeclarationEntry(name='policy_type', path=f'$.policy_type', type='string', state='form', required=True, description='政策类型'),
            DeclarationEntry(name='service_items', path=f'$.service_items', type='string', state='form', required=True, description='服务项目'),
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='carry', required=True, description='提单号', value_source=ValueSource(view='pending_orders', column='bl_no')),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', required=True, default='0', description='服务策略ID'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', description='备注'),  # needs_capture:value_source
            DeclarationEntry(name='business_type', path=f'$.business_type', type='string', state='carry', description='业务类型'),
            DeclarationEntry(name='trade_term', path=f'$.trade_term', type='string', state='form', description='成交方式'),
            DeclarationEntry(name='carrier', path=f'$.carrier', type='string', state='carry', description='船公司/承运人'),
            DeclarationEntry(name='etd', path=f'$.etd', type='string', state='carry', description='预计开航日'),
            DeclarationEntry(name='atd', path=f'$.atd', type='integer', state='form', default='0', description='实际开航日'),
            DeclarationEntry(name='ship_name', path=f'$.ship_name', type='string', state='carry', description='船名'),
            DeclarationEntry(name='voy', path=f'$.voy', type='string', state='carry', description='航次'),
            DeclarationEntry(name='pol', path=f'$.pol', type='string', state='carry', description='起运港'),
            DeclarationEntry(name='pot', path=f'$.pot', type='string', state='carry', description='中转港'),  # needs_capture:value_source
            DeclarationEntry(name='pod', path=f'$.pod', type='string', state='carry', description='卸货港'),
            DeclarationEntry(name='del', path=f'$.del', type='string', state='carry', description='目的地'),  # needs_capture:value_source
            DeclarationEntry(name='terms_payment', path=f'$.terms_payment', type='string', state='carry', description='结汇方式'),  # needs_capture:value_source
            DeclarationEntry(name='terms_transport', path=f'$.terms_transport', type='string', state='carry', description='运输条款'),  # needs_capture:value_source
            DeclarationEntry(name='pay_type', path=f'$.pay_type', type='string', state='carry', description='付款方式'),  # needs_capture:value_source
            DeclarationEntry(name='customer_order_sn', path=f'$.customer_order_sn', type='string', state='carry', description='客户单号'),  # needs_capture:value_source
            DeclarationEntry(name='cargo_type', path=f'$.cargo_type', type='string', state='carry', description='货物类型'),
            DeclarationEntry(name='num', path=f'$.num', type='integer', state='carry', default='0', description='件数'),
            DeclarationEntry(name='gross_weight', path=f'$.gross_weight', type='number', state='carry', description='毛重'),
            DeclarationEntry(name='bulk', path=f'$.bulk', type='number', state='carry', description='体积'),
            DeclarationEntry(name='packer', path=f'$.packer', type='string', state='carry', description='包装'),  # needs_capture:value_source
            DeclarationEntry(name='sea_trans_currency', path=f'$.sea_trans_currency', type='string', state='form', description='海运费币制'),
            DeclarationEntry(name='container', path=f'$.container', type='string', state='form', description='集装箱信息'),
            DeclarationEntry(name='shipper', path=f'$.shipper', type='string', state='carry', description='发货人'),  # needs_capture:value_source
            DeclarationEntry(name='consignee', path=f'$.consignee', type='string', state='carry', description='收货人'),  # needs_capture:value_source
            DeclarationEntry(name='notifier', path=f'$.notifier', type='string', state='carry', description='通知人'),  # needs_capture:value_source
            DeclarationEntry(name='terms_shipment', path=f'$.terms_shipment', type='string', state='carry', description='装运条款'),  # needs_capture:value_source
            DeclarationEntry(name='is_usd_project', path=f'$.is_usd_project', type='integer', state='carry', default='2', description='是否USD项目'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', default='submit', description='操作目的'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
            DeclarationEntry(name='entrust_status', path=f'$.entrust_status', type='integer', state='form', default='1', description='1未分发 2已分发'),
            DeclarationEntry(name='supplier', path=f'$.supplier', type='string', state='form'),
            DeclarationEntry(name='oldSupplierMap', path=f'$.oldSupplierMap', type='string', state='form'),
            DeclarationEntry(name='order_self_id', path=f'$.order_self_id', type='integer', state='form', default='0', description='订单id'),
            DeclarationEntry(name='sea_trans_cost', path=f'$.sea_trans_cost', type='number', state='form', default='0.00', description='海运费总价'),
            DeclarationEntry(name='settle_type', path=f'$.settle_type', type='integer', state='form', default='0', description='1月结 2票结'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='airline_type', path=f'$.airline_type', type='string', state='form', description='航线分类'),
            DeclarationEntry(name='volume_desc', path=f'$.volume_desc', type='string', state='form', description='箱型箱量描述'),
            DeclarationEntry(name='order_file', path=f'$.order_file', type='string', state='form'),
            DeclarationEntry(name='operator_id', path=f'$.operator_id', type='integer', state='form', default='0', description='操作ID'),
            DeclarationEntry(name='sale_id', path=f'$.sale_id', type='integer', state='form', default='0', description='销售ID  关联sys_user'),
            DeclarationEntry(name='service_id', path=f'$.service_id', type='integer', state='form', default='0', description='客服ID  关联sys_user'),
            DeclarationEntry(name='client_expand_id', path=f'$.client_expand_id', type='integer', state='form', description='直客拓展ID'),
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
