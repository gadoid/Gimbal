"""fin.king_dee_export.statement_export —— 孪生生成器产物(请求面;行为面归场景用例)。

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

KING_DEE_EXPORT_STATEMENT_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.king_dee_export.statement_export',
    system='fin',
    service='fin-service',
    name='KingDeeExport.statementExport',
    description='KingDeeExport.statementExport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/kingDeeExport/statementExport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='symbol', path=f'$.symbol', type='integer', state='form', default='0', description='应收应付 0 应付  1应收'),
            DeclarationEntry(name='start_time', path=f'$.start_time', type='integer', state='form', default='0', description='有效期起'),
            DeclarationEntry(name='end_time', path=f'$.end_time', type='integer', state='form', default='0', description='有效期止'),
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
