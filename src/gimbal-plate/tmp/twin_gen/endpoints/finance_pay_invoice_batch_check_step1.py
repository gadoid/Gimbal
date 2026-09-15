"""fin.pay_invoice_batch.check_step1 —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): (无)
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

PAY_INVOICE_BATCH_CHECK_STEP1: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_invoice_batch.check_step1',
    system='fin',
    service='fin-service',
    name='PayInvoiceBatch.checkStep1',
    description='PayInvoiceBatch.checkStep1' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payInvoiceBatch/checkStep1',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='apply_type', path=f'$.apply_type', type='integer', state='form', description='开票申请类型 1同一下单客户 2跨下单客户'),
            DeclarationEntry(name='batch_type', path=f'$.batch_type', type='integer', state='form', description='选中费用  1 按费用  2按提单'),
            DeclarationEntry(name='order_fee_real_id', path=f'$.order_fee_real_id', type='integer', state='form', default='0'),
            DeclarationEntry(name='order_sub_id', path=f'$.order_sub_id', type='integer', state='form', default='0', description='子订单ID'),
            DeclarationEntry(name='pay_invoice_batch_id', path=f'$.pay_invoice_batch_id', type='integer', state='form', default='0', description='应付开票批次ID'),
            DeclarationEntry(name='fee_status', path=f'$.fee_status', type='integer', state='form', default='0', description='费用状态  0未锁定   1已锁定 2已作废 锁定后无法解锁不可修改'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', default='0', description='费用主体ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='order_sub_customer_id', path=f'$.order_sub_customer_id', type='string', state='form'),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='cost_ids', path=f'$.cost_ids', type='string', state='form'),
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='form', description='服务项目'),
            DeclarationEntry(name='fee_type', path=f'$.fee_type', type='integer', state='form', default='0', description='费用类型 0标准费用 1特殊费用 2调节费用'),
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
