"""fin.receive_writeoff.confirm_receive_writeoff —— 孪生生成器产物(请求面;行为面归场景用例)。

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

RECEIVE_WRITEOFF_CONFIRM_RECEIVE_WRITEOFF: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_writeoff.confirm_receive_writeoff',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveWriteoff/confirmReceiveWriteoff',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='receive_writeoff_id', path=f'$.receive_writeoff_id', type='string', state='form', required=True, description='核销ID集合'),
            DeclarationEntry(name='statement', path=f'$.statement', type='string', state='form', required=True, description='核销流水'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', description='操作目的'),
            DeclarationEntry(name='writeoff_name', path=f'$.writeoff_name', type='string', state='form', description='应收核销记录名称'),
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
