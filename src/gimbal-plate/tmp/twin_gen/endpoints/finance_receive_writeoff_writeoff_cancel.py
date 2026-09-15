"""fin.receive_writeoff.writeoff_cancel —— 孪生生成器产物(请求面;行为面归场景用例)。

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

RECEIVE_WRITEOFF_WRITEOFF_CANCEL: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_writeoff.writeoff_cancel',
    system='fin',
    service='fin-service',
    name='ReceiveWriteoff.writeoffCancel',
    description='ReceiveWriteoff.writeoffCancel' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveWriteoff/writeoffCancel',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='receive_writeoff_id', path=f'$.receive_writeoff_id', type='string', state='form', required=True, description='核销ID集合'),
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='form', default='1', description='核销状态 1未核销 2已核销 3部分核销'),
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='form', default='1', description='审批状态 1待处理 2通过 3驳回 4撤销'),
            DeclarationEntry(name='writeoff_type', path=f'$.writeoff_type', type='integer', state='form', default='0', description='核销类型 1正常核销 2强制核销'),
            DeclarationEntry(name='writeoff_no', path=f'$.writeoff_no', type='string', state='form', description='应收核销记录编号'),
            DeclarationEntry(name='writeoff_mode', path=f'$.writeoff_mode', type='string', state='form', description='核销方式 按费用核销fee 按发票核销 invoice 按提单核销order'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', default='0', description='业务订单ID'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', default='0', description='服务策略ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
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
