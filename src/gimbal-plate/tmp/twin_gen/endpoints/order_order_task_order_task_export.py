"""fin.order_task.order_task_export —— 孪生生成器产物(请求面;行为面归场景用例)。

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

ORDER_TASK_ORDER_TASK_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_task.order_task_export',
    system='fin',
    service='fin-service',
    name='OrderTask.orderTaskExport',
    description='OrderTask.orderTaskExport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderTask/orderTaskExport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='task_no', path=f'$.task_no', type='string', state='form', description='任务编码'),
            DeclarationEntry(name='task_status', path=f'$.task_status', type='integer', state='form', default='1', description='任务状态:1-待处理,2-已完成'),
            DeclarationEntry(name='task_object', path=f'$.task_object', type='string', state='form'),
            DeclarationEntry(name='task_type', path=f'$.task_type', type='string', state='form', description='任务类型'),
            DeclarationEntry(name='order_no', path=f'$.order_no', type='string', state='form', description='业务订单编号'),
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', description='提单号'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='assign_id', path=f'$.assign_id', type='integer', state='form', description='主键ID'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form'),
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
