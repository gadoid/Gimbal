"""fin.production_finance.sync_customer_user_account —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): dlgt_mobile_no, status, id_no, id_no_type, name, add_time, company_name
溯源统计: frontend=9, column=2 | fe_high=9, enum=2
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

PRODUCTION_FINANCE_SYNC_CUSTOMER_USER_ACCOUNT: Final[EndpointSpec] = EndpointSpec(
    id='fin.production_finance.sync_customer_user_account',
    system='fin',
    service='fin-service',
    name='ProductionFinance.syncCustomerUserAccount',
    description='ProductionFinance.syncCustomerUserAccount' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/productionFinance/syncCustomerUserAccount',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='dlgt_mobile_no', path=f'$.dlgt_mobile_no', type='string', state='carry', ui_kind='text', required=True, description='手机号码'),  # needs_capture:value_source
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='carry', ui_kind='select', required=True, default='1', description='用户状态', enum=['0', '1']),  # zh_ambiguous, needs_capture:enum_required
            DeclarationEntry(name='id_no', path=f'$.id_no', type='string', state='carry', ui_kind='text', required=True, description='身份证号'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='id_no_type', path=f'$.id_no_type', type='integer', state='carry', ui_kind='select', required=True, default='10', description='证件类型  10身份证 11护照', enum=['10', '11']),  # needs_capture:enum_required
            DeclarationEntry(name='name', path=f'$.name', type='string', state='carry', ui_kind='text', required=True, description='姓名'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='add_time', path=f'$.add_time', type='integer', state='carry', ui_kind='text', required=True, default='0', description='添加日期'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='company_name', path=f'$.company_name', type='string', state='carry', ui_kind='select', description='企业名称'),  # zh_ambiguous
            DeclarationEntry(name='status_time', path=f'$.status_time', type='integer', state='carry', ui_kind='text', default='0', description='状态更新日期'),
            DeclarationEntry(name='role', path=f'$.role', type='integer', state='carry', ui_kind='select', default='0', description='个人角色'),
            DeclarationEntry(name='register_source', path=f'$.register_source', type='integer', state='carry', ui_kind='select', default='0', description='来源'),
            DeclarationEntry(name='customer_source', path=f'$.customer_source', type='string', state='form', ui_kind='text', description='客商类型 01 外贸客户 02供应商'),
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
