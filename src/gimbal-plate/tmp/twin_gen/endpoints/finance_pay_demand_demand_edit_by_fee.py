"""fin.pay_demand.demand_edit_by_fee —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): customer_id, pay_settle_object_id, put_settle_object_id, service_project, pay_demand_no, cancel_by
溯源统计: column=37, 无zh=8 | fe_high=0, enum=1
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
    name='操作',
    description='操作' + ' [generated:fin-test@2026-09-15]',
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
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', description='操作', enum=['check', 'submit']),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', ui_kind='text', description='审批人备注'),
            DeclarationEntry(name='operation_type', path=f'$.operation_type', type='integer', state='form', ui_kind='number', default='0', description='需求选择类型 0费用 1提单'),
            DeclarationEntry(name='select_list', path=f'$.select_list', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='payment_list', path=f'$.payment_list', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='pay_demand_id', path=f'$.pay_demand_id', type='integer', state='form', ui_kind='number', default='0', description='付款需求ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='number', default='0', description='客户ID'),  # zh_ambiguous
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', ui_kind='number', default='0', description='应付结算对象ID'),  # zh_ambiguous
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', ui_kind='number', default='0', description='应收结算对象ID'),  # zh_ambiguous
            DeclarationEntry(name='sub_put_settle_object_id', path=f'$.sub_put_settle_object_id', type='string', state='form', ui_kind='text', description='子订单应收结算对象ID'),
            DeclarationEntry(name='pay_demand_name', path=f'$.pay_demand_name', type='string', state='form', ui_kind='text', description='付款需求名称'),
            DeclarationEntry(name='pay_amount_usd_total', path=f'$.pay_amount_usd_total', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='pay_amount_cny_total', path=f'$.pay_amount_cny_total', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='pay_settle_object_total', path=f'$.pay_settle_object_total', type='integer', state='form', ui_kind='number'),
            DeclarationEntry(name='split_dimension', path=f'$.split_dimension', type='string', state='form', ui_kind='text', description='拆分维度'),
            DeclarationEntry(name='demand_remark', path=f'$.demand_remark', type='string', state='form', ui_kind='text', description='备注'),
            DeclarationEntry(name='all_money_data', path=f'$.all_money_data', type='string', state='form', ui_kind='text', description='搜索费用'),
            DeclarationEntry(name='right_money_data', path=f'$.right_money_data', type='string', state='form', ui_kind='text', description='已选费用'),
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='form', ui_kind='textarea', description='提单号'),
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='form', ui_kind='text', description='审批回显信息'),
            DeclarationEntry(name='flow_type', path=f'$.flow_type', type='string', state='form', ui_kind='text', description='审批流配置类型'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', ui_kind='number', description='关联ID'),
            DeclarationEntry(name='cost_ids', path=f'$.cost_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='form', ui_kind='text', description='服务项目'),  # zh_ambiguous
            DeclarationEntry(name='payment_type', path=f'$.payment_type', type='integer', state='form', ui_kind='number', default='0', description='付款类型 1确定性付款 2非确定性付款'),
            DeclarationEntry(name='pay_demand_no', path=f'$.pay_demand_no', type='string', state='carry', ui_kind='text', description='付款需求编号'),  # needs_capture:value_source
            DeclarationEntry(name='main_id', path=f'$.main_id', type='string', state='carry', ui_kind='textarea', description='费用主体ID'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='carry', ui_kind='textarea', description='费用主体'),
            DeclarationEntry(name='pay_amount_usd', path=f'$.pay_amount_usd', type='number', state='carry', ui_kind='number', description='付款金额（USD）'),
            DeclarationEntry(name='pay_amount_cny', path=f'$.pay_amount_cny', type='number', state='carry', ui_kind='number', description='付款金额（CNY）'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='carry', ui_kind='number', description='付款需求状态 2已生效 3已作废'),
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='carry', ui_kind='number', description='审核状态 1审核中 2已审核 3审核驳回 4审核撤销'),
            DeclarationEntry(name='cancel_amount_usd', path=f'$.cancel_amount_usd', type='number', state='carry', ui_kind='number', description='作废金额（USD）'),
            DeclarationEntry(name='cancel_amount_cny', path=f'$.cancel_amount_cny', type='number', state='carry', ui_kind='number', description='作废金额（CNY）'),
            DeclarationEntry(name='cancel_id', path=f'$.cancel_id', type='integer', state='carry', ui_kind='number', description='作废人ID'),
            DeclarationEntry(name='cancel_by', path=f'$.cancel_by', type='string', state='carry', ui_kind='text', description='作废人'),  # needs_capture:value_source
            DeclarationEntry(name='cancel_time', path=f'$.cancel_time', type='integer', state='carry', ui_kind='number', description='作废时间'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number', description='创建人ID'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建人'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number', description='更新人ID'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新人'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number', description='更新时间'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
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
