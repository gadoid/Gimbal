"""fin.cost.cost_add —— 孪生生成器产物(请求面;行为面归场景用例)。

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
            DeclarationEntry(name='cost_name', path=f'$.cost_name', type='string', state='form', required=True, description='费用名称'),
            DeclarationEntry(name='cost_name_en', path=f'$.cost_name_en', type='string', state='form', description='费用英文名称'),
            DeclarationEntry(name='cost_type', path=f'$.cost_type', type='integer', state='form', required=True, default='0', description='通用对象 0 通用  1定制', enum=['0', '1']),
            DeclarationEntry(name='cost_label', path=f'$.cost_label', type='integer', state='form', default='0', description='费用标签   0非  1是'),
            DeclarationEntry(name='special_cost', path=f'$.special_cost', type='integer', state='form', default='0', description='特殊费用  0非  1是'),
            DeclarationEntry(name='cost_id', path=f'$.cost_id', type='integer', state='form'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', default='submit', description='操作目的'),
            DeclarationEntry(name='supplier_ids', path=f'$.supplier_ids', type='string', state='form', description='供应商ids'),
            DeclarationEntry(name='customer_ids', path=f'$.customer_ids', type='string', state='form', description='客户ids'),
            DeclarationEntry(name='service_ids', path=f'$.service_ids', type='string', state='form', description='服务项目ids'),
            DeclarationEntry(name='price_unit', path=f'$.price_unit', type='string', state='form', description='单位'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', description='币值'),
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
