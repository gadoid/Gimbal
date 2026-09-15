"""fin.pay_account.export_account_summary —— 孪生生成器产物(请求面;行为面归场景用例)。

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

PAY_ACCOUNT_EXPORT_ACCOUNT_SUMMARY: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_account.export_account_summary',
    system='fin',
    service='fin-service',
    name='PayAccount.exportAccountSummary',
    description='PayAccount.exportAccountSummary' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payAccount/exportAccountSummary',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='form', description='费用主体名称'),
            DeclarationEntry(name='pay_account_id', path=f'$.pay_account_id', type='integer', state='form', default='0', description='应付对账'),
            DeclarationEntry(name='order_supplier_group', path=f'$.order_supplier_group', type='string', state='form'),
            DeclarationEntry(name='account_info', path=f'$.account_info', type='string', state='form'),
            DeclarationEntry(name='is_preview', path=f'$.is_preview', type='string', state='form'),
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
