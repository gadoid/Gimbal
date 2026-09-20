"""fin.cost.cost_add —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): create_id, create_time, update_id, update_time
溯源统计: lang=10, frontend=6, 无zh=5, column=1 | fe_high=11, enum=2
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

COST_COST_ADD: Final[EndpointSpec] = EndpointSpec(
    id='fin.cost.cost_add',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/cost/costAdd',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='cost_name', path=f'$.cost_name', type='string', state='form', ui_kind='text', description='费用名称'),
            DeclarationEntry(name='cost_name_en', path=f'$.cost_name_en', type='string', state='form', ui_kind='text', description='费用名称(英文)'),
            DeclarationEntry(name='cost_type', path=f'$.cost_type', type='integer', state='form', ui_kind='select', default='0', description='费用类型', enum=['0', '1']),
            DeclarationEntry(name='cost_label', path=f'$.cost_label', type='integer', state='form', ui_kind='select', default='0', description='费用标签'),
            DeclarationEntry(name='special_cost', path=f'$.special_cost', type='integer', state='form', ui_kind='select', default='0', description='特殊费用'),
            DeclarationEntry(name='cost_no', path=f'$.cost_no', type='string', state='carry', ui_kind='text', default='0', description='费用ID'),
            DeclarationEntry(name='cost_ids', path=f'$.cost_ids', type='string', state='carry', ui_kind='select', description='费用名称'),
            DeclarationEntry(name='customer_ids', path=f'$.customer_ids', type='string', state='form', ui_kind='select', description='关联客户'),
            DeclarationEntry(name='supplier_ids', path=f'$.supplier_ids', type='string', state='form', ui_kind='select', description='关联供应商'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='select', default='0', description='创建人'),  # zh_ambiguous
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='创建时间'),  # zh_ambiguous
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='select', description='更新人'),  # zh_ambiguous
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='text', default='0', description='更新时间'),  # zh_ambiguous
            DeclarationEntry(name='cost_id', path=f'$.cost_id', type='integer', state='form', ui_kind='number'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='submit', description='操作目的', enum=['check', 'submit']),
            DeclarationEntry(name='service_ids', path=f'$.service_ids', type='string', state='form', ui_kind='text', description='关联服务项目'),
            DeclarationEntry(name='price_unit', path=f'$.price_unit', type='string', state='form', ui_kind='text', description='计价单位'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', ui_kind='text', description='账户类型'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='delete_time', path=f'$.delete_time', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
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
