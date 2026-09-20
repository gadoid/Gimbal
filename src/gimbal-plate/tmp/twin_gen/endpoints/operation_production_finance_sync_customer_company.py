"""fin.production_finance.sync_customer_company —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): company_name, company_no, address, tripartite_agreement
溯源统计: column=8 | fe_high=0, enum=1
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

PRODUCTION_FINANCE_SYNC_CUSTOMER_COMPANY: Final[EndpointSpec] = EndpointSpec(
    id='fin.production_finance.sync_customer_company',
    system='fin',
    service='fin-service',
    name='ProductionFinance.syncCustomerCompany',
    description='ProductionFinance.syncCustomerCompany' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/productionFinance/syncCustomerCompany',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='company_name', path=f'$.company_name', type='string', state='carry', ui_kind='text', required=True, description='客户名称'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='company_no', path=f'$.company_no', type='string', state='carry', ui_kind='text', required=True, description='客户统一社会信用代码'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='address', path=f'$.address', type='string', state='carry', ui_kind='text', required=True, description='注册地址'),  # needs_capture:value_source
            DeclarationEntry(name='tripartite_agreement', path=f'$.tripartite_agreement', type='integer', state='carry', ui_kind='select', required=True, default='2', description='1签署 2未签署   三方协议', enum=['1', '2']),  # needs_capture:enum_required
            DeclarationEntry(name='signing_method', path=f'$.signing_method', type='integer', state='carry', ui_kind='number', default='1', description='1线上 2线下 3无需签约 '),
            DeclarationEntry(name='authorize_agreement', path=f'$.authorize_agreement', type='integer', state='carry', ui_kind='number', default='2', description='1签署 2未签署 信息查询及电子签章授权书'),
            DeclarationEntry(name='authorize_sign_time', path=f'$.authorize_sign_time', type='integer', state='carry', ui_kind='number', default='0', description='信息查询及电子签章授权书签署时间'),
            DeclarationEntry(name='tripartite_sign_time', path=f'$.tripartite_sign_time', type='integer', state='carry', ui_kind='number', default='0', description='三方协议签署时间'),
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
