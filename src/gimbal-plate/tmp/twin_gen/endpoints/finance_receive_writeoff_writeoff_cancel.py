"""fin.receive_writeoff.writeoff_cancel —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): writeoff_status
溯源统计: column=5, lang=1 | fe_high=0, enum=0
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
            DeclarationEntry(name='receive_writeoff_id', path=f'$.receive_writeoff_id', type='integer', state='form', ui_kind='number', required=True, default='0', description='核销ID'),
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='form', ui_kind='number', default='1', description='核销状态'),  # zh_ambiguous
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='form', ui_kind='number', description='审核状态 0无状态 1审核中 2审核通过 3审核驳回 4审核撤销'),
            DeclarationEntry(name='writeoff_type', path=f'$.writeoff_type', type='integer', state='form', ui_kind='number', default='0', description='核销类型 1正常核销 2强制核销'),
            DeclarationEntry(name='writeoff_no', path=f'$.writeoff_no', type='string', state='form', ui_kind='textarea', description='关联核销记录编号'),
            DeclarationEntry(name='writeoff_mode', path=f'$.writeoff_mode', type='string', state='form', ui_kind='text', description='核销方式 按费用核销fee 按发票核销 invoice 按提单核销order'),
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
