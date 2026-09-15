"""fin.login.get_info —— 孪生生成器产物(请求面;行为面归场景用例)。

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

LOGIN_GET_INFO: Final[EndpointSpec] = EndpointSpec(
    id='fin.login.get_info',
    system='fin',
    service='fin-service',
    name='Login.getInfo',
    description='Login.getInfo' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/login/getInfo',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='user_id', path=f'$.user_id', type='integer', state='form', default='0', description='用户ID'),
            DeclarationEntry(name='admin', path=f'$.admin', type='string', state='form'),
            DeclarationEntry(name='password', path=f'$.password', type='string', state='form'),
            DeclarationEntry(name='validatePass', path=f'$.validatePass', type='string', state='form'),
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
