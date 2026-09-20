"""fin.receive_invoice_batch.get_order_info_by_fee_id —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): exchange_rate, order_fee_real_id, put_settle_object_id, pay_settle_object_id, main_id, service_project, fee_type, fee_status
溯源统计: column=5, lang=5, 无zh=2 | fe_high=0, enum=0
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

RECEIVE_INVOICE_BATCH_GET_ORDER_INFO_BY_FEE_ID: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_invoice_batch.get_order_info_by_fee_id',
    system='fin',
    service='fin-service',
    name='ReceiveInvoiceBatch.getOrderInfoByFeeId',
    description='ReceiveInvoiceBatch.getOrderInfoByFeeId' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveInvoiceBatch/getOrderInfoByFeeId',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='exchange_rate', path=f'$.exchange_rate', type='number', state='form', ui_kind='number', default='0.0000', description='记账汇率'),  # zh_ambiguous
            DeclarationEntry(name='usd_invoice_remark', path=f'$.usd_invoice_remark', type='string', state='form', ui_kind='text', description='美金发票备注'),
            DeclarationEntry(name='style', path=f'$.style', type='integer', state='form', ui_kind='number', description='开票申请样式'),
            DeclarationEntry(name='order_fee_real_id', path=f'$.order_fee_real_id', type='integer', state='form', ui_kind='number', description='费用'),  # zh_ambiguous
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', ui_kind='number', default='0', description='应收结算对象'),  # zh_ambiguous
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', ui_kind='number', default='0', description='应付结算对象'),  # zh_ambiguous
            DeclarationEntry(name='order_sub_customer_id', path=f'$.order_sub_customer_id', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='number', default='0', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='cost_ids', path=f'$.cost_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='form', ui_kind='text', description='服务项目'),  # zh_ambiguous
            DeclarationEntry(name='fee_type', path=f'$.fee_type', type='integer', state='form', ui_kind='number', default='0', description='费用类型 0标准费用 1特殊费用 2调节费用'),  # zh_ambiguous
            DeclarationEntry(name='fee_status', path=f'$.fee_status', type='integer', state='form', ui_kind='number', default='0', description='费用状态  0未锁定   1已锁定 2已作废 锁定后无法解锁不可修改'),  # zh_ambiguous
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
