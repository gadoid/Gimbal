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
    EndpointSpec,
    DeclarationEntry,
    RequestSpec,
    ResponseSpec,
    EndpointMetadata,
)


# ----------------------------------------------------------------------
# 来源: curl 导入 | 生成时间: 2026-09-02T08:02:51.572363+00:00
# 人工已确认: 类型/必填/绑定面/响应语义/能力声明
# 原始 curl(认证信息已脱敏):
#   curl --url 'https://fin-tidb.21eflag.com/api/order/order/orderDetail'    -H 'Accept: application/json, text/plain, */*'    -H 'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'    -H 'Authorization: ***REDACTED***'    -H 'Connection: keep-alive'    -H 'Content-Type: application/json;charset=UTF-8'    -b 'PHPSESSID=73l16grejpmip1vs001q9tkns5; rememberMe=true; username=18180789652; password=b8gysm6KQ1t2GX1LrYisB8u2Ku7ugNNh8gUG6SHiEyroDJntkTSzidX+YVdAWLva0dpERL9FhZD33podNZe6uw==; Admin-Token=***REDACTED***; think_language=zh-CN'    -H 'Origin: https://fin-tidb.21eflag.com'    -H 'Referer: https://fin-tidb.21eflag.com/'    -H 'Sec-Fetch-Dest: empty'    -H 'Sec-Fetch-Mode: cors'    -H 'Sec-Fetch-Site: same-origin'    -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'    -H 'sec-ch-ua: "Not=A?Brand";v="99", "Microsoft Edge";v="151", "Chromium";v="151"'    -H 'sec-ch-ua-mobile: ?0'    -H 'sec-ch-ua-platform: "Windows"'    --data-raw '{"order_id":"353432653833176064"}'
# ----------------------------------------------------------------------
ORDER_ORDER_DETAIL: Final[EndpointSpec] = EndpointSpec(
    id='fin.order.order_detail',
    system='fin',
    service='fin-service',
    name='订单-查询订单详情',
    description='订单-查询订单详情',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/order/orderDetail',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        schema={
            'type': 'object',
            'properties': {
                'order_id': {
                    'type': 'string',
                    'description': '',
                    'x-type-hint': '疑似 int(字符串形态)',
                },
            },
            'required': ['order_id'],
        },
        declarations=[
            DeclarationEntry(name='order_id', path='$.order_id', channel='binding', required=True, example='353432653833176064', description='', ui_kind='text', source_kind='independent'),
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
            declarations=[
                DeclarationEntry(name='code', path='$.code', channel='view_only', required=False, example=200, description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='msg', path='$.msg', channel='view_only', required=False, example='成功', description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='order_id', path='$.data.data[0].order_id', channel='view_only', required=False, example='353432653833176064', description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='order_no', path='$.data.data[0].order_no', channel='view_only', required=False, example='YWDD20260902110779', description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='bl_no', path='$.data.data[0].bl_no', channel='view_only', required=False, example='Codfish-3KQI-Test', description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='policy_type', path='$.data.data[0].policy_type', channel='view_only', required=False, example='JSZX', description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='policy_id', path='$.data.data[0].policy_id', channel='view_only', required=False, example='295502731957764096', description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='business_type', path='$.data.data[0].business_type', channel='view_only', required=False, example='1', description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='main_ids', path='$.data.data[0].main_ids', channel='view_only', required=False, example=',1,3,', description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='supplier_names', path='$.data.data[0].supplier_names', channel='view_only', required=False, example='青岛跃航国际物流有限公司', description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='supplier_ids', path='$.data.data[0].supplier_ids', channel='view_only', required=False, example=['5'], description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='order_sub_no', path='$.data.data[0].order_sub_no', channel='view_only', required=False, example='ZDD20260902022947', description='', ui_kind='text', source_kind='independent', assertable=True),
                DeclarationEntry(name='business_no', path='$.data.data[0].business_no', channel='view_only', required=False, example='YHD20260902036490', description='', ui_kind='text', source_kind='independent', assertable=True),
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
