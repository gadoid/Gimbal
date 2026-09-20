"""fin.order_task.get_tasks_by_assignee —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): create_time, customer_id, order_no
溯源统计: frontend=7, builtin=2, column=2, derived=2 | fe_high=7, enum=2
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

ORDER_TASK_GET_TASKS_BY_ASSIGNEE: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_task.get_tasks_by_assignee',
    system='fin',
    service='fin-service',
    name='OrderTask.getTasksByAssignee',
    description='OrderTask.getTasksByAssignee' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderTask/getTasksByAssignee',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='task_no', path=f'$.task_no', type='string', state='form', ui_kind='text', description='任务编号'),
            DeclarationEntry(name='task_object', path=f'$.task_object', type='string', state='form', ui_kind='select', description='任务对象'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='派发时间'),  # zh_ambiguous
            DeclarationEntry(name='assign_id', path=f'$.assign_id', type='string', state='form', ui_kind='select', default='0', description='处理人'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='select', default='0', description='下单客户名称'),  # zh_ambiguous
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', ui_kind='text', description='提单号'),
            DeclarationEntry(name='order_no', path=f'$.order_no', type='string', state='form', ui_kind='text', description='业务订单ID'),  # zh_ambiguous
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', description='每页条数'),
            DeclarationEntry(name='task_status', path=f'$.task_status', type='integer', state='form', ui_kind='select', description='任务状态:1-待处理,2-已完成', enum=['order_entry', 'bill_entry', 'manifest_entry', 'insurance_entry', 'trucking_entry', 'confirm_atd', 'push_asset', 'add_fee', 'put_invoice', 'bill_confirm', 'manifest_confirm', 'trucking_confirm', 'insurance_confirm']),
            DeclarationEntry(name='task_type', path=f'$.task_type', type='string', state='form', ui_kind='select', description='任务类型', enum=['order_entry', 'bill_entry', 'manifest_entry', 'insurance_entry', 'trucking_entry', 'confirm_atd', 'push_asset', 'add_fee', 'put_invoice', 'bill_confirm', 'manifest_confirm', 'trucking_confirm', 'insurance_confirm']),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form', ui_kind='text', description='派发时间开始'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form', ui_kind='text', description='派发时间结束'),
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description='成功(信封统一;data 行形状归场景用例)',
            declarations=[
            DeclarationEntry(name='code', path='$.code', type='number',
                             required=False, ui_kind='number',
                             description='业务状态码(200=成功)', assertable=True),
            DeclarationEntry(name='msg', path='$.msg', type='string',
                             required=False, ui_kind='text',
                             description='业务提示信息', assertable=True),
            DeclarationEntry(name='data', path='$.data', type='object',
                             required=False, ui_kind='json',
                             description='业务数据(行形状归场景用例)', assertable=True),
            DeclarationEntry(name='request_id', path='$.request_id', type='string',
                             required=False, ui_kind='text',
                             description='请求追踪ID', assertable=True),

            ],
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
