"""fin.register_company.upload_intent_file —— 孪生生成器产物(请求面;行为面归场景用例)。

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

REGISTER_COMPANY_UPLOAD_INTENT_FILE: Final[EndpointSpec] = EndpointSpec(
    id='fin.register_company.upload_intent_file',
    system='fin',
    service='fin-service',
    name='RegisterCompany.uploadIntentFile',
    description='RegisterCompany.uploadIntentFile' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/registerCompany/uploadIntentFile',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='company_no', path=f'$.company_no', type='string', state='form', description='企业社会统一信用代码'),
            DeclarationEntry(name='intent_contract_file', path=f'$.intent_contract_file', type='string', state='form', description='意向函文件'),
            DeclarationEntry(name='intent_contract_file_name', path=f'$.intent_contract_file_name', type='string', state='form', description='意向函文件名称'),
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
