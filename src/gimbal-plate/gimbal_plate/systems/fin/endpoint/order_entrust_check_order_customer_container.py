"""由 curl 导入生成 —— 经人工确认,提交前须完成 code review。"""
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
    EndpointSpec,
    DeclarationEntry,
    RequestSpec,
    ResponseSpec,
    EndpointMetadata,
)

# ----------------------------------------------------------------------
# 来源: curl 导入 | 生成时间: 2026-09-04T06:21:11.716258+00:00
# 人工已确认: 类型/必填/绑定面/响应语义/能力声明
# 原始 curl(认证信息已脱敏):
#   curl --url 'https://fin-tidb.21eflag.com/api/order/OrderEntrust/checkOrderCustomerContainer'    -H 'Accept: application/json, text/plain, */*'    -H 'Accept-Language: zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7'    -H 'Authorization: ***REDACTED***'    -H 'Connection: keep-alive'    -H 'Content-Type: application/json;charset=UTF-8'    -b 'rememberMe=true; username=18180789652; PHPSESSID=85notr904d259oqm2ur9qr7slj; think_language=zh-CN; password=QCwXlCgfCCPSRo8OUrAYK33KN6bbyNOJHwpzE6xgf3YHEnJSwC0m1eiiw+eYoSUbDk9SBwdGcs0i2vjSGXmP1Q==; Admin-Token=***REDACTED***'    -H 'Origin: https://fin-tidb.21eflag.com'    -H 'Referer: https://fin-tidb.21eflag.com/'    -H 'Sec-Fetch-Dest: empty'    -H 'Sec-Fetch-Mode: cors'    -H 'Sec-Fetch-Site: same-origin'    -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0'    -H 'sec-ch-ua: "Chromium";v="152", "Not?A_Brand";v="24", "Microsoft Edge";v="152"'    -H 'sec-ch-ua-mobile: ?0'    -H 'sec-ch-ua-platform: "Windows"'    --data-raw '{"customer_id":"335247043402399744","order_id":"354066893969032192","container":[{"box_type":"20GP","box_num":"1","box_no":[""],"seal_number":[""],"sea_trans_unit_price":"100"}],"policy_type":"JSZX"}'
# ----------------------------------------------------------------------
ORDER_ENTRUST_CHECK_ORDER_CUSTOMER_CONTAINER: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_entrust.order_customer_container',
    system='fin',
    service='fin-service',
    name='检查订舱信息',
    description='检查订舱信息',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/OrderEntrust/checkOrderCustomerContainer',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        
        declarations=[
            DeclarationEntry(name='customer_id', path='$.customer_id', type='string', example='335247043402399744', ui_kind='text'),
            DeclarationEntry(name='order_id', path='$.order_id', type='string', example='354066893969032192', ui_kind='text'),
            DeclarationEntry(name='container', path='$.container', type='array', example=[{'order_container_id':'','box_type': '20GP', 'box_num': '1', 'box_no': [''], 'seal_number': [''], 'sea_trans_unit_price': '100'}], ui_kind='text'),
            DeclarationEntry(name='policy_type', path='$.policy_type', type='string', example='JSZX', ui_kind='text'),
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