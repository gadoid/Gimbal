"""fin.pay_demand.demand_edit_by_fee —— 孪生生成器产物(请求面;行为面归场景用例)。

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

PAY_DEMAND_DEMAND_EDIT_BY_FEE: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_demand.demand_edit_by_fee',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payDemand/demandEditByFee',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', description='操作目的'),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', description='审批人备注'),
            DeclarationEntry(name='operation_type', path=f'$.operation_type', type='integer', state='form', default='0', description='需求选择类型 0费用 1提单'),
            DeclarationEntry(name='select_list', path=f'$.select_list', type='string', state='form'),
            DeclarationEntry(name='payment_list', path=f'$.payment_list', type='string', state='form'),
            DeclarationEntry(name='pay_demand_id', path=f'$.pay_demand_id', type='integer', state='form', default='0', description='付款需求ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='sub_put_settle_object_id', path=f'$.sub_put_settle_object_id', type='string', state='form', description='子订单应收结算对象ID'),
            DeclarationEntry(name='pay_demand_name', path=f'$.pay_demand_name', type='string', state='form', description='付款需求名称'),
            DeclarationEntry(name='pay_amount_usd_total', path=f'$.pay_amount_usd_total', type='string', state='form'),
            DeclarationEntry(name='pay_amount_cny_total', path=f'$.pay_amount_cny_total', type='string', state='form'),
            DeclarationEntry(name='pay_settle_object_total', path=f'$.pay_settle_object_total', type='integer', state='form'),
            DeclarationEntry(name='split_dimension', path=f'$.split_dimension', type='string', state='form', description='拆分维度'),
            DeclarationEntry(name='demand_remark', path=f'$.demand_remark', type='string', state='form', description='备注'),
            DeclarationEntry(name='all_money_data', path=f'$.all_money_data', type='string', state='form', description='搜索费用'),
            DeclarationEntry(name='right_money_data', path=f'$.right_money_data', type='string', state='form', description='已选费用'),
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='form', description='关联提单号'),
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='form', description='审批回显信息'),
            DeclarationEntry(name='flow_type', path=f'$.flow_type', type='string', state='form', description='审批流配置类型'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', default='0', description='业务ID'),
            DeclarationEntry(name='cost_ids', path=f'$.cost_ids', type='string', state='form'),
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='form', description='服务项目'),
            DeclarationEntry(name='payment_type', path=f'$.payment_type', type='integer', state='form', default='0', description='付款类型 1确定性付款 2非确定性付款'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', default='0', description='业务订单ID'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', default='0', description='服务策略ID'),
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
