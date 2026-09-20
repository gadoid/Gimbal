"""fin.supplier.supplier_import —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): status
溯源统计: lang=4, column=3 | fe_high=0, enum=0
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

SUPPLIER_SUPPLIER_IMPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.supplier.supplier_import',
    system='fin',
    service='fin-service',
    name='Supplier.supplierImport',
    description='Supplier.supplierImport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/supplier/supplierImport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='self_support', path=f'$.self_support', type='string', state='form', ui_kind='text', default='0', description='是否为自营供应商'),
            DeclarationEntry(name='service_term', path=f'$.service_term', type='integer', state='form', ui_kind='number', description='自营服务项目账期'),
            DeclarationEntry(name='service_items', path=f'$.service_items', type='string', state='form', ui_kind='text', description='自营服务项目 1报关 2舱单 3保险 4拖车'),
            DeclarationEntry(name='supplier_contact', path=f'$.supplier_contact', type='string', state='form', ui_kind='text', description='联系人信息'),
            DeclarationEntry(name='supplier_finance', path=f'$.supplier_finance', type='string', state='form', ui_kind='text', description='财务信息'),
            DeclarationEntry(name='supplier_file', path=f'$.supplier_file', type='string', state='form', ui_kind='file', description='附件'),
            DeclarationEntry(name='status', path=f'$.status', type='string', state='form', ui_kind='text', default='0', description='状态（0停用  1草稿 2正常）\n'),  # zh_ambiguous
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
