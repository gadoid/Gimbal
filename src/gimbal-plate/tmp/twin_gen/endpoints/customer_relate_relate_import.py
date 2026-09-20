"""fin.relate.relate_import —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): settle_type, period_rule, customer_id, supplier_id
溯源统计: lang=3, column=3, 无zh=3 | fe_high=0, enum=0
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

RELATE_RELATE_IMPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.relate.relate_import',
    system='fin',
    service='fin-service',
    name='Relate.relateImport',
    description='Relate.relateImport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/relate/relateImport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_time_limit', path=f'$.pay_time_limit', type='integer', state='form', ui_kind='number', description='付款时效'),
            DeclarationEntry(name='settle_type', path=f'$.settle_type', type='integer', state='form', ui_kind='number', default='0', description='结算方式'),  # zh_ambiguous
            DeclarationEntry(name='is_independent_email', path=f'$.is_independent_email', type='integer', state='form', ui_kind='number', default='0', description='是否独立对接供应商邮箱：0否 1是'),
            DeclarationEntry(name='period_rule', path=f'$.period_rule', type='string', state='form', ui_kind='text', default='1', description='账期截转规则'),  # zh_ambiguous
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='string', state='form', ui_kind='text', description='id 主键'),  # zh_ambiguous
            DeclarationEntry(name='supplier_id', path=f'$.supplier_id', type='integer', state='form', ui_kind='number', default='0', description='供应商ID'),  # zh_ambiguous
            DeclarationEntry(name='relate_account', path=f'$.relate_account', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='receive_contact_ids', path=f'$.receive_contact_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='cc_contact_ids', path=f'$.cc_contact_ids', type='string', state='form', ui_kind='text'),
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
