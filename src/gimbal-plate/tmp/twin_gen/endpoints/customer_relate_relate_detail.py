"""fin.relate.relate_detail —— 孪生生成器产物(请求面;行为面归场景用例)。

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

RELATE_RELATE_DETAIL: Final[EndpointSpec] = EndpointSpec(
    id='fin.relate.relate_detail',
    system='fin',
    service='fin-service',
    name='Relate.relateDetail',
    description='Relate.relateDetail' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/relate/relateDetail',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='relate_id', path=f'$.relate_id', type='string', state='form'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='supplier_id', path=f'$.supplier_id', type='integer', state='form', default='0', description='变更账期供应商ID'),
            DeclarationEntry(name='show_history', path=f'$.show_history', type='string', state='form'),
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
