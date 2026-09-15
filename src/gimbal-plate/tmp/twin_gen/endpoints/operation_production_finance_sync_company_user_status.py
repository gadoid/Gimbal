"""fin.production_finance.sync_company_user_status —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): dlgt_mobile_no, status, company_no
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

PRODUCTION_FINANCE_SYNC_COMPANY_USER_STATUS: Final[EndpointSpec] = EndpointSpec(
    id='fin.production_finance.sync_company_user_status',
    system='fin',
    service='fin-service',
    name='ProductionFinance.syncCompanyUserStatus',
    description='ProductionFinance.syncCompanyUserStatus' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/productionFinance/syncCompanyUserStatus',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='dlgt_mobile_no', path=f'$.dlgt_mobile_no', type='string', state='carry', required=True, description='手机号'),  # needs_capture:value_source
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='carry', required=True, default='0', description='状态 1未通知 2已通知', enum=['0', '1']),  # needs_capture:enum_required
            DeclarationEntry(name='customer_source', path=f'$.customer_source', type='string', state='carry', description='客商类型 01 外贸客户 02供应商'),
            DeclarationEntry(name='company_no', path=f'$.company_no', type='string', state='carry', required=True, description='企业社会统一信用代码'),  # needs_capture:value_source
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
