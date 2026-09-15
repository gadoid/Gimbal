"""fin.user.batch_edit_user_main —— 孪生生成器产物(请求面;行为面归场景用例)。

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

USER_BATCH_EDIT_USER_MAIN: Final[EndpointSpec] = EndpointSpec(
    id='fin.user.batch_edit_user_main',
    system='fin',
    service='fin-service',
    name='User.batchEditUserMain',
    description='User.batchEditUserMain' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/user/batchEditUserMain',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='user_id', path=f'$.user_id', type='integer', state='form', required=True, default='0', description='用户ID'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', required=True, default='0', description='费用主体ID'),
            DeclarationEntry(name='change_type', path=f'$.change_type', type='integer', state='form', required=True, description='订单变更类型 1变更服务政策 2变更服务策略', enum=['add', 'del']),
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
