"""fin.order.order_detail —— 查询订单详情接口契约。在 scen_test_14 中出现4次。"""

from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_AUTHOR,
    FIN_DEFAULT_MODULE,
    FIN_DEFAULT_OWNER,
    FIN_DEFAULT_PRIORITY,
    FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION,
    FIN_SYSTEM,
)

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)

# ----------------------------------------------------------------------
# 来源: curl 导入 | 生成时间: 2026-09-03T02:55:39.763197+00:00
# 人工已确认: 类型/必填/绑定面/响应语义/能力声明
# 原始 curl(认证信息已脱敏):
#   curl --url 'https://fin-tidb.21eflag.com/api/order/order/orderDetail'    -H 'Accept: application/json, text/plain, */*'    -H 'Accept-Language: zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7'    -H 'Authorization: ***REDACTED***'    -H 'Connection: keep-alive'    -H 'Content-Type: application/json;charset=UTF-8'    -b 'rememberMe=true; PHPSESSID=grfb3ngdiae9pd44ihj91v8arr; username=18180789652; password=lviDIFggMeiDobkahsKHe4mcDvlAs+/vf2zjDFOP5Qpr7nock+Js1Bdbwcgmw6P19Qul10mo4eRH0LKXJdIq/Q==; think_language=zh-CN; Admin-Token=***REDACTED***'    -H 'Origin: https://fin-tidb.21eflag.com'    -H 'Referer: https://fin-tidb.21eflag.com/'    -H 'Sec-Fetch-Dest: empty'    -H 'Sec-Fetch-Mode: cors'    -H 'Sec-Fetch-Site: same-origin'    -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'    -H 'sec-ch-ua: "Not=A?Brand";v="99", "Microsoft Edge";v="151", "Chromium";v="151"'    -H 'sec-ch-ua-mobile: ?0'    -H 'sec-ch-ua-platform: "Windows"'    --data-raw '{"order_id":"353724757260108800"}'
# ----------------------------------------------------------------------
ORDER_ORDER_DETAIL: Final[EndpointSpec] = EndpointSpec(
    id='fin.order.order_detail',
    system='fin',
    service='fin-service',
    name='订单-查询订单详情',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/order/orderDetail',
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        
        declarations=[
            DeclarationEntry(name='order_id', path='$.order_id', type='string', example='353724757260108800', description='订单id', ui_kind='text'),
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
            declarations=[
                DeclarationEntry(name='code', path='$.code', type='integer', required=False, example=200, ui_kind='text', assertable=True),
                DeclarationEntry(name='msg', path='$.msg', type='string', required=False, example='成功', ui_kind='text', assertable=True),
                DeclarationEntry(name='order_id', path='$.data.order_id', type='string', required=False, example='353724757260108800', ui_kind='text', assertable=True),
                DeclarationEntry(name='order_no', path='$.data.order_no', type='string', required=False, example='YWDD20260903110794', ui_kind='text', assertable=True),
                DeclarationEntry(name='customer_id', path='$.data.customer_id', type='string', required=False, example='335247043402399744', ui_kind='text', assertable=True),
                # 2026-09-05 结构化:supplier 深实例叶子($.data.supplier[0].*)升为
                # 整容器模板 children(响应侧实例级角标不做,模板态匹配,实例化归
                # 渲染器);行形状 22 键与 order_add 请求 $.supplier 同构
                DeclarationEntry(name='supplier', path='$.data.supplier', type='array', required=False, assertable=True,
                    children=[
                        DeclarationEntry(name='order_supplier_id', path='$.data.supplier.order_supplier_id', type='string', required=False, example='354632242825266176', ui_kind='text', assertable=True),
                        DeclarationEntry(name='order_id', path='$.data.supplier.order_id', type='string', required=False, example='354632241306928128', ui_kind='text', assertable=True),
                        DeclarationEntry(name='isset_supplier', path='$.data.supplier.isset_supplier', type='string', required=False, example='1', ui_kind='text', assertable=True),
                        DeclarationEntry(name='is_primary', path='$.data.supplier.is_primary', type='string', required=False, example='1', ui_kind='text', assertable=True),
                        DeclarationEntry(name='supplier_id', path='$.data.supplier.supplier_id', type='string', required=False, example='1', ui_kind='text', assertable=True),
                        DeclarationEntry(name='supplier_name', path='$.data.supplier.supplier_name', type='string', required=False, example='山东旭禾国际贸易有限公司', ui_kind='text', assertable=True),
                        DeclarationEntry(name='settle_object_id', path='$.data.supplier.settle_object_id', type='string', required=False, example='15', ui_kind='text', assertable=True),
                        DeclarationEntry(name='user_id', path='$.data.supplier.user_id', type='string', required=False, example='41', ui_kind='text', assertable=True),
                        DeclarationEntry(name='user_name', path='$.data.supplier.user_name', type='string', required=False, example='孙奉盛', ui_kind='text', assertable=True),
                        DeclarationEntry(name='service_item', path='$.data.supplier.service_item', type='string', required=False, example='booking_space', ui_kind='text', assertable=True),
                        DeclarationEntry(name='supplier_period', path='$.data.supplier.supplier_period', type='string', required=False, example='30', ui_kind='text', assertable=True),
                        DeclarationEntry(name='settlement_date', path='$.data.supplier.settlement_date', type='string', required=False, example='20', ui_kind='text', assertable=True),
                        DeclarationEntry(name='supplier_pay_date', path='$.data.supplier.supplier_pay_date', type='string', required=False, example='1789833600', ui_kind='text', assertable=True),
                        DeclarationEntry(name='is_manual', path='$.data.supplier.is_manual', type='string', required=False, example='0', ui_kind='text', assertable=True),
                        DeclarationEntry(name='sys_upttime', path='$.data.supplier.sys_upttime', type='string', required=False, example='2026-09-05 22:22:00', ui_kind='text', assertable=True),
                        DeclarationEntry(name='pay_time_limit', path='$.data.supplier.pay_time_limit', type='string', required=False, example='10', ui_kind='text', assertable=True),
                        DeclarationEntry(name='supplier_pay_date_desc', path='$.data.supplier.supplier_pay_date_desc', type='string', required=False, example='月结规则', ui_kind='text', assertable=True),
                        DeclarationEntry(name='settle_type', path='$.data.supplier.settle_type', type='string', required=False, example='1', ui_kind='text', assertable=True),
                        DeclarationEntry(name='supplier_label', path='$.data.supplier.supplier_label', type='string', required=False, example='山东旭禾国际贸易有限公司-订舱', ui_kind='text', assertable=True),
                        DeclarationEntry(name='settle_type_name', path='$.data.supplier.settle_type_name', type='string', required=False, example='月结', ui_kind='text', assertable=True),
                        DeclarationEntry(name='service_item_name', path='$.data.supplier.service_item_name', type='string', required=False, example='订舱', ui_kind='text', assertable=True),
                        DeclarationEntry(name='isset_fee', path='$.data.supplier.isset_fee', type='boolean', required=False, example=False, ui_kind='boolean', assertable=True),
                    ]),
                DeclarationEntry(name='order_container_id', path='$.data.container[0].order_container_id', type='string', required=False, example='354178949166662656', ui_kind='text', assertable=True),
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