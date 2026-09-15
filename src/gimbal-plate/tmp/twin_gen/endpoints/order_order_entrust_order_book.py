"""fin.order_entrust.order_book —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): policy_type, main_sort, service_items, track_bl_no, remark, pot, country_name, terms_payment, terms_transport, pay_type, customer_order_sn, packer, volume_desc
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

ORDER_ENTRUST_ORDER_BOOK: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_entrust.order_book',
    system='fin',
    service='fin-service',
    name='OrderEntrust.orderBook',
    description='OrderEntrust.orderBook' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderEntrust/orderBook',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', required=True, default='0', description='客户ID'),
            DeclarationEntry(name='customer_contact_id', path=f'$.customer_contact_id', type='integer', state='form', description='客户联系人id'),
            DeclarationEntry(name='operator_id', path=f'$.operator_id', type='integer', state='form', required=True, default='0', description='操作ID'),
            DeclarationEntry(name='policy_type', path=f'$.policy_type', type='string', state='carry', required=True, description='政策类型'),  # needs_capture:value_source
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', required=True, default='0', description='服务策略ID'),
            DeclarationEntry(name='policy_name', path=f'$.policy_name', type='string', state='carry', required=True, description='服务策略名字', value_source=ValueSource(view='customer_policy', column='policy_name')),
            DeclarationEntry(name='main_sort', path=f'$.main_sort', type='string', state='carry', required=True, description='主体顺序'),  # needs_capture:value_source
            DeclarationEntry(name='service_items', path=f'$.service_items', type='string', state='carry', required=True, description='服务项目'),  # needs_capture:value_source
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', required=True, description='提单号'),
            DeclarationEntry(name='track_bl_no', path=f'$.track_bl_no', type='string', state='carry', required=True, description='提单号'),  # needs_capture:value_source
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', description='备注'),  # needs_capture:value_source
            DeclarationEntry(name='num', path=f'$.num', type='integer', state='form', default='0', description='件数'),
            DeclarationEntry(name='service_id', path=f'$.service_id', type='integer', state='carry', default='0', description='客服ID'),
            DeclarationEntry(name='sale_id', path=f'$.sale_id', type='integer', state='form', default='0', description='销售ID'),
            DeclarationEntry(name='settle_type', path=f'$.settle_type', type='integer', state='carry', default='0', description='1月结 2票结'),
            DeclarationEntry(name='business_type', path=f'$.business_type', type='string', state='form', description='业务类型'),
            DeclarationEntry(name='trade_term', path=f'$.trade_term', type='string', state='form', description='成交方式'),
            DeclarationEntry(name='carrier', path=f'$.carrier', type='string', state='carry', description='船公司/承运人'),
            DeclarationEntry(name='etd', path=f'$.etd', type='string', state='form', description='预计开航日'),
            DeclarationEntry(name='ship_name', path=f'$.ship_name', type='string', state='carry', description='船名'),
            DeclarationEntry(name='voy', path=f'$.voy', type='string', state='carry', description='航次'),
            DeclarationEntry(name='pol', path=f'$.pol', type='string', state='form', description='起运港'),
            DeclarationEntry(name='pot', path=f'$.pot', type='string', state='carry', description='中转港'),  # needs_capture:value_source
            DeclarationEntry(name='pod', path=f'$.pod', type='string', state='form', description='卸货港'),
            DeclarationEntry(name='del', path=f'$.del', type='string', state='form', description='目的地'),
            DeclarationEntry(name='country_name', path=f'$.country_name', type='string', state='carry', description='卸货港国家'),  # needs_capture:value_source
            DeclarationEntry(name='terms_payment', path=f'$.terms_payment', type='string', state='carry', description='结汇方式'),  # needs_capture:value_source
            DeclarationEntry(name='terms_transport', path=f'$.terms_transport', type='string', state='carry', description='运输条款'),  # needs_capture:value_source
            DeclarationEntry(name='pay_type', path=f'$.pay_type', type='string', state='carry', description='付款方式'),  # needs_capture:value_source
            DeclarationEntry(name='customer_order_sn', path=f'$.customer_order_sn', type='string', state='carry', description='客户单号'),  # needs_capture:value_source
            DeclarationEntry(name='cargo_type', path=f'$.cargo_type', type='string', state='carry', description='货物类型'),
            DeclarationEntry(name='gross_weight', path=f'$.gross_weight', type='number', state='form', description='毛重'),
            DeclarationEntry(name='bulk', path=f'$.bulk', type='number', state='form', description='体积'),
            DeclarationEntry(name='packer', path=f'$.packer', type='string', state='carry', description='包装'),  # needs_capture:value_source
            DeclarationEntry(name='volume', path=f'$.volume', type='string', state='carry', description='箱型箱量'),
            DeclarationEntry(name='volume_desc', path=f'$.volume_desc', type='string', state='carry', description='箱型箱量描述'),  # needs_capture:value_source
            DeclarationEntry(name='container', path=f'$.container', type='string', state='form', description='箱型'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='carry', default='0', description='订单状态'),
            DeclarationEntry(name='shipper', path=f'$.shipper', type='string', state='form', description='发货人'),
            DeclarationEntry(name='consignee', path=f'$.consignee', type='string', state='form', description='收货人'),
            DeclarationEntry(name='notifier', path=f'$.notifier', type='string', state='form', description='通知人'),
            DeclarationEntry(name='ship_mark', path=f'$.ship_mark', type='string', state='form', description='唛头'),
            DeclarationEntry(name='commodity', path=f'$.commodity', type='string', state='form', description='品名'),
            DeclarationEntry(name='notes', path=f'$.notes', type='string', state='form', description='托书备注'),
            DeclarationEntry(name='terms_shipment', path=f'$.terms_shipment', type='string', state='form', description='装运条款'),
            DeclarationEntry(name='is_usd_project', path=f'$.is_usd_project', type='integer', state='carry', default='2', description='是否USD项目'),
            DeclarationEntry(name='supplier', path=f'$.supplier', type='string', state='form'),
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='form', description='客户名称'),
            DeclarationEntry(name='book_supplier_name', path=f'$.book_supplier_name', type='string', state='form'),
            DeclarationEntry(name='atd', path=f'$.atd', type='integer', state='form', default='0', description='实际开航日'),
            DeclarationEntry(name='sea_trans_cost', path=f'$.sea_trans_cost', type='number', state='form', default='0.00', description='海运费总价'),
            DeclarationEntry(name='sea_trans_currency', path=f'$.sea_trans_currency', type='string', state='form', description='海运费币制'),
            DeclarationEntry(name='book_supplier_id', path=f'$.book_supplier_id', type='integer', state='form', default='0'),
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
