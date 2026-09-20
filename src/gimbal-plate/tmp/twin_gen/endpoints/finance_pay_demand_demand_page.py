"""fin.pay_demand.demand_page —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): create_time, main_id, status, pay_settle_object_id, create_id, sort_field, sort_order
溯源统计: frontend=8, 无zh=6, builtin=4, column=3, derived=2 | fe_high=8, enum=1
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

PAY_DEMAND_DEMAND_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_demand.demand_page',
    system='fin',
    service='fin-service',
    name='PayDemand.demandPage',
    description='PayDemand.demandPage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payDemand/demandPage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_demand_no', path=f'$.pay_demand_no', type='string', state='form', ui_kind='text', description='付款需求ID'),
            DeclarationEntry(name='pay_demand_name', path=f'$.pay_demand_name', type='string', state='form', ui_kind='text', description='付款需求名称'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='创建时间'),  # zh_ambiguous
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='select', default='0', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', ui_kind='select', default='0', description='付款需求状态'),  # zh_ambiguous
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='form', ui_kind='select', description='审核状态'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', ui_kind='text', default='0', description='应付结算对象'),  # zh_ambiguous
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='form', ui_kind='text', description='提单号批量'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', required=True, description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', required=True, description='每页条数'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', ui_kind='number', description='关联ID'),
            DeclarationEntry(name='pay_demand_ids', path=f'$.pay_demand_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='check_ids', path=f'$.check_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='fee_main_id', path=f'$.fee_main_id', type='integer', state='form', ui_kind='number', default='0', description='费用主体ID'),
            DeclarationEntry(name='pay_amount_cny_start', path=f'$.pay_amount_cny_start', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='Demand_amount_end', path=f'$.Demand_amount_end', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='pay_amount_usd_start', path=f'$.pay_amount_usd_start', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='pay_amount_usd_end', path=f'$.pay_amount_usd_end', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', ui_kind='number', default='0', description='创建人ID'),  # zh_ambiguous
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form', ui_kind='text', description='创建时间开始'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form', ui_kind='text', description='创建时间结束'),
            DeclarationEntry(name='sort_field', path=f'$.sort_field', type='string', state='carry', ui_kind='text', required=True, description='排序字段'),  # needs_capture:value_source
            DeclarationEntry(name='sort_order', path=f'$.sort_order', type='string', state='carry', ui_kind='select', required=True, description='排序方向', enum=['asc', 'desc']),  # needs_capture:enum_required
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
