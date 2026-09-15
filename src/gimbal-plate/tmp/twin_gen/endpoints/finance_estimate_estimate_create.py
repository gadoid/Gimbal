"""fin.estimate.estimate_create —— 孪生生成器产物(请求面;行为面归场景用例)。

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

ESTIMATE_ESTIMATE_CREATE: Final[EndpointSpec] = EndpointSpec(
    id='fin.estimate.estimate_create',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/estimate/estimateCreate',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', required=True, default='0', description='费用主体ID'),
            DeclarationEntry(name='estimate_start', path=f'$.estimate_start', type='integer', state='form', required=True, default='0', description='暂估开始时间'),
            DeclarationEntry(name='estimate_end', path=f'$.estimate_end', type='integer', state='form', required=True, default='0', description='暂估结束时间'),
            DeclarationEntry(name='lock_start', path=f'$.lock_start', type='integer', state='form', required=True, default='0', description='锁定开始时间'),
            DeclarationEntry(name='lock_end', path=f'$.lock_end', type='integer', state='form', required=True, default='0', description='锁定结束时间'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', description='操作目的'),
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
