"""fin.assign.assign_page —— 孪生生成器产物(请求面;行为面归场景用例)。

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

ASSIGN_ASSIGN_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.assign.assign_page',
    system='fin',
    service='fin-service',
    name='Assign.assignPage',
    description='Assign.assignPage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/assign/assignPage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
            DeclarationEntry(name='active_tab', path=f'$.active_tab', type='string', state='form'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', default='0', description='发起人ID'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form'),
            DeclarationEntry(name='assign_type', path=f'$.assign_type', type='string', state='form', description='任务类型'),
            DeclarationEntry(name='assign_no', path=f'$.assign_no', type='string', state='form', description='任务编号'),
            DeclarationEntry(name='executor_id', path=f'$.executor_id', type='integer', state='form', default='0', description='处理人ID'),
            DeclarationEntry(name='executor_time_start', path=f'$.executor_time_start', type='string', state='form'),
            DeclarationEntry(name='executor_time_end', path=f'$.executor_time_end', type='string', state='form'),
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
