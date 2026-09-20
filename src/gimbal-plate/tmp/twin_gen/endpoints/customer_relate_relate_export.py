"""fin.relate.relate_export —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): status
溯源统计: column=4, 无zh=2, builtin=2 | fe_high=0, enum=0
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

RELATE_RELATE_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.relate.relate_export',
    system='fin',
    service='fin-service',
    name='Relate.relateExport',
    description='Relate.relateExport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/relate/relateExport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='customer_category', path=f'$.customer_category', type='string', state='form', ui_kind='text', description='客户分类'),
            DeclarationEntry(name='status', path=f'$.status', type='string', state='form', ui_kind='text', default='0', description='状态（0停用  1草稿 2正常）\n'),  # zh_ambiguous
            DeclarationEntry(name='creation_method', path=f'$.creation_method', type='string', state='form', ui_kind='text', description='创建方式'),
            DeclarationEntry(name='check_ids', path=f'$.check_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='is_independent_email', path=f'$.is_independent_email', type='integer', state='form', ui_kind='number', default='0', description='是否独立对接供应商邮箱：0否 1是'),
            DeclarationEntry(name='has_effective_account', path=f'$.has_effective_account', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', description='每页条数'),
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
