"""fin.added_service.edit_service —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): id, effective_time_start
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

ADDED_SERVICE_EDIT_SERVICE: Final[EndpointSpec] = EndpointSpec(
    id='fin.added_service.edit_service',
    system='fin',
    service='fin-service',
    name='AddedService.editService',
    description='AddedService.editService' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/addedService/editService',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='id', path=f'$.id', type='string', state='carry', required=True),  # needs_capture:value_source
            DeclarationEntry(name='effective_time_start', path=f'$.effective_time_start', type='integer', state='carry', required=True, default='0', description='有效期起'),  # needs_capture:value_source
            DeclarationEntry(name='effective_time_end', path=f'$.effective_time_end', type='integer', state='form', required=True, default='0', description='有效期止'),
            DeclarationEntry(name='type', path=f'$.type', type='string', state='form', required=True),
            DeclarationEntry(name='num', path=f'$.num', type='integer', state='form', required=True, default='0', description='数量'),
            DeclarationEntry(name='total_num', path=f'$.total_num', type='integer', state='form', required=True, default='0', description='总额度'),
            DeclarationEntry(name='credit_num', path=f'$.credit_num', type='integer', state='form', default='0', description='资信报告剩余额度'),
            DeclarationEntry(name='credit_type', path=f'$.credit_type', type='string', state='form'),
            DeclarationEntry(name='service_type', path=f'$.service_type', type='string', state='form', default='track', description='服务类型   默认 轨迹订阅'),
            DeclarationEntry(name='source_type', path=f'$.source_type', type='integer', state='form', default='1', description='来源类型(应收批次)1自主创建 2应付联动发起(0910)'),
            DeclarationEntry(name='credit_total_num', path=f'$.credit_total_num', type='integer', state='form', default='0', description='资信报告总额度'),
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
