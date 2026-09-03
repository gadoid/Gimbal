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
        schema={
            'type': 'object',
            'properties': {
                'order_id': {
                    'type': 'string',
                    'description': '订单id',
                    'x-type-hint': '疑似 int(字符串形态)',
                },
            },
            'required': ['order_id'],
        },
        declarations=[
            DeclarationEntry(name='order_id', path='$.order_id', channel='binding', example='353724757260108800', description='订单id', ui_kind='text'),
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
            declarations=[
                DeclarationEntry(name='code', path='$.code', channel='view_only', required=False, example=200, ui_kind='text', assertable=True),
                DeclarationEntry(name='msg', path='$.msg', channel='view_only', required=False, example='成功', ui_kind='text', assertable=True),
                DeclarationEntry(name='order_id', path='$.data.order_id', channel='view_only', required=False, example='353724757260108800', ui_kind='text', assertable=True),
                DeclarationEntry(name='order_no', path='$.data.order_no', channel='view_only', required=False, example='YWDD20260903110794', ui_kind='text', assertable=True),
                DeclarationEntry(name='customer_id', path='$.data.customer_id', channel='view_only', required=False, example='335247043402399744', ui_kind='text', assertable=True),
                DeclarationEntry(name='order_supplier_id', path='$.data.supplier[0].order_supplier_id', channel='view_only', required=False, example='353724758581314560', ui_kind='text', assertable=True),
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