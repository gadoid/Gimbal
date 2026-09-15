"""fin.relate.relate_import —— 孪生生成器产物(请求面;行为面归场景用例)。

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

RELATE_RELATE_IMPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.relate.relate_import',
    system='fin',
    service='fin-service',
    name='Relate.relateImport',
    description='Relate.relateImport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/relate/relateImport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_time_limit', path=f'$.pay_time_limit', type='integer', state='form', description='付款时效'),
            DeclarationEntry(name='settle_type', path=f'$.settle_type', type='integer', state='form', default='0', description='1月结 2票结'),
            DeclarationEntry(name='is_independent_email', path=f'$.is_independent_email', type='integer', state='form', default='0', description='是否独立对接供应商邮箱：0否 1是'),
            DeclarationEntry(name='period_rule', path=f'$.period_rule', type='string', state='form', default='1', description='废弃 125日后订单截转下月计算账期 2按ATD本月计算账期'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='supplier_id', path=f'$.supplier_id', type='integer', state='form', default='0', description='变更账期供应商ID'),
            DeclarationEntry(name='relate_account', path=f'$.relate_account', type='string', state='form'),
            DeclarationEntry(name='receive_contact_ids', path=f'$.receive_contact_ids', type='string', state='form'),
            DeclarationEntry(name='cc_contact_ids', path=f'$.cc_contact_ids', type='string', state='form'),
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
