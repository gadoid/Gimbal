"""fin.api_finance.generate_invoice_file —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): (无)
溯源统计: column=1, 无zh=1 | fe_high=0, enum=0
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

FINANCE_GENERATE_INVOICE_FILE: Final[EndpointSpec] = EndpointSpec(
    id='fin.api_finance.generate_invoice_file',
    system='fin',
    service='fin-service',
    name='Finance.generateInvoiceFile',
    description='Finance.generateInvoiceFile' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/api/finance/generateInvoiceFile',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='receive_invoice_batch_id', path=f'$.receive_invoice_batch_id', type='integer', state='form', ui_kind='number', default='0', description='应收开票批次ID'),
            DeclarationEntry(name='receive_invoice_id', path=f'$.receive_invoice_id', type='integer', state='form', ui_kind='number'),
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description='成功(信封统一;data 行形状归场景用例)',
            declarations=[
            DeclarationEntry(name='retCode', path='$.retCode', type='number',
                             required=False, ui_kind='number',
                             description='回调状态码(0=成功)', assertable=True),
            DeclarationEntry(name='retMsg', path='$.retMsg', type='string',
                             required=False, ui_kind='text',
                             description='回调提示信息', assertable=True),
            DeclarationEntry(name='data', path='$.data', type='object',
                             required=False, ui_kind='json',
                             description='业务数据(行形状归场景用例)', assertable=True),

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
