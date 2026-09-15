"""fin.pay_demand.pay_demand_export —— 孪生生成器产物(请求面;行为面归场景用例)。

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

PAY_DEMAND_PAY_DEMAND_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_demand.pay_demand_export',
    system='fin',
    service='fin-service',
    name='PayDemand.payDemandExport',
    description='PayDemand.payDemandExport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payDemand/payDemandExport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', default='0', description='业务ID'),
            DeclarationEntry(name='pay_demand_ids', path=f'$.pay_demand_ids', type='string', state='form'),
            DeclarationEntry(name='check_ids', path=f'$.check_ids', type='string', state='form'),
            DeclarationEntry(name='pay_demand_no', path=f'$.pay_demand_no', type='string', state='form', description='付款需求编号'),
            DeclarationEntry(name='pay_demand_name', path=f'$.pay_demand_name', type='string', state='form', description='付款需求名称'),
            DeclarationEntry(name='fee_main_id', path=f'$.fee_main_id', type='integer', state='form', default='0', description='费用主体ID'),
            DeclarationEntry(name='pay_amount_cny_start', path=f'$.pay_amount_cny_start', type='string', state='form'),
            DeclarationEntry(name='Demand_amount_end', path=f'$.Demand_amount_end', type='string', state='form'),
            DeclarationEntry(name='pay_amount_usd_start', path=f'$.pay_amount_usd_start', type='string', state='form'),
            DeclarationEntry(name='pay_amount_usd_end', path=f'$.pay_amount_usd_end', type='string', state='form'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='form', default='1', description='审批状态 1待处理 2通过 3驳回 4撤销'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', default='0', description='发起人ID'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='form', description='关联提单号'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', default='0', description='费用主体ID'),
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
