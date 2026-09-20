"""fin.order_document.order_document_page —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): order_id, document_type, sort_field, sort_order
溯源统计: builtin=4, column=4 | fe_high=0, enum=3
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

ORDER_DOCUMENT_ORDER_DOCUMENT_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_document.order_document_page',
    system='fin',
    service='fin-service',
    name='OrderDocument.orderDocumentPage',
    description='OrderDocument.orderDocumentPage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderDocument/orderDocumentPage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', required=True, description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', required=True, description='每页条数'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', ui_kind='number', default='0', description='关联 sys_order订单表'),  # zh_ambiguous
            DeclarationEntry(name='order_sub_id', path=f'$.order_sub_id', type='integer', state='form', ui_kind='number', default='0', description='子订单ID'),
            DeclarationEntry(name='document_type', path=f'$.document_type', type='string', state='form', ui_kind='select', description='单证类型', enum=['BOOK_CUSTOMER', 'BOOK_MAIN', 'BOOK_SUPPLIER', 'COST_CONFIRMATION', 'COST_CONFIRMATION_ACCOUNT', 'COST_CONFIRMATION_LOAN', 'FEE_NOTICE', 'BILL', 'DECLARATION', 'SUPPLIER_ACCOUNT', 'INVOICE_FINANCE', 'INVOICE_TAKE', 'INVOICE_PAY', 'INVOICE_MAIN_TAKE', 'INVOICE_MAIN_PAY']),  # zh_ambiguous
            DeclarationEntry(name='document_status', path=f'$.document_status', type='integer', state='form', ui_kind='select', description='单证状态  1生效  2作废', enum=['BOOK_CUSTOMER', 'BOOK_MAIN', 'BOOK_SUPPLIER', 'COST_CONFIRMATION', 'COST_CONFIRMATION_ACCOUNT', 'COST_CONFIRMATION_LOAN', 'FEE_NOTICE', 'BILL', 'DECLARATION', 'SUPPLIER_ACCOUNT', 'INVOICE_FINANCE', 'INVOICE_TAKE', 'INVOICE_PAY', 'INVOICE_MAIN_TAKE', 'INVOICE_MAIN_PAY']),
            DeclarationEntry(name='sort_field', path=f'$.sort_field', type='string', state='carry', ui_kind='text', required=True, description='排序字段'),  # needs_capture:value_source
            DeclarationEntry(name='sort_order', path=f'$.sort_order', type='string', state='carry', ui_kind='select', required=True, description='排序方向', enum=['asc', 'desc']),  # needs_capture:enum_required
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
