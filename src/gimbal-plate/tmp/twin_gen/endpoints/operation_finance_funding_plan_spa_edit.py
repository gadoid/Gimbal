"""fin.finance.funding_plan_spa_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): total_spa, year, month
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

FINANCE_FUNDING_PLAN_SPA_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.finance.funding_plan_spa_edit',
    system='fin',
    service='fin-service',
    name='Finance.fundingPlanSpaEdit',
    description='Finance.fundingPlanSpaEdit' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/finance/fundingPlanSpaEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='total_spa', path=f'$.total_spa', type='string', state='carry', required=True),  # needs_capture:value_source
            DeclarationEntry(name='year', path=f'$.year', type='string', state='carry', required=True, description='年份'),  # needs_capture:value_source
            DeclarationEntry(name='month', path=f'$.month', type='string', state='carry', required=True),  # needs_capture:value_source
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
