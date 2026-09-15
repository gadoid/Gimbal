"""fin.monthly_reconciliation.list —— 孪生生成器产物(请求面;行为面归场景用例)。

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

MONTHLY_RECONCILIATION_LIST: Final[EndpointSpec] = EndpointSpec(
    id='fin.monthly_reconciliation.list',
    system='fin',
    service='fin-service',
    name='MonthlyReconciliation.list',
    description='MonthlyReconciliation.list' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/monthlyReconciliation/list',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
            DeclarationEntry(name='batch_status', path=f'$.batch_status', type='string', state='form', description='批次状态：供应商端(已上传/已确认/已作废/已退回)、运营端(待确认/已确认/已作废)'),
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', description='提单号'),
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='form', description='关联提单号'),
            DeclarationEntry(name='batch_code', path=f'$.batch_code', type='string', state='form', description='对外展示的对账批次编号（如：MRB2026030001）'),
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='form', description='客户名称'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='form', description='费用主体名称'),
            DeclarationEntry(name='booking_opt_branch', path=f'$.booking_opt_branch', type='string', state='form', description='订舱供应商名称（运营端用）'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='form', description='修改人'),
            DeclarationEntry(name='update_time_start', path=f'$.update_time_start', type='string', state='form'),
            DeclarationEntry(name='update_time_end', path=f'$.update_time_end', type='string', state='form'),
            DeclarationEntry(name='schedule_actual_delivery_date_start', path=f'$.schedule_actual_delivery_date_start', type='string', state='form'),
            DeclarationEntry(name='schedule_actual_delivery_date_end', path=f'$.schedule_actual_delivery_date_end', type='string', state='form'),
            DeclarationEntry(name='settlement_date_start', path=f'$.settlement_date_start', type='string', state='form'),
            DeclarationEntry(name='settlement_date_end', path=f'$.settlement_date_end', type='string', state='form'),
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
