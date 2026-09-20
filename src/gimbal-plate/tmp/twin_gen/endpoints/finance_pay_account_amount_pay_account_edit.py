"""fin.pay_account.amount_pay_account_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): customer_id, main_name, main_id, put_settle_object_id, pay_settle_object_id, pay_settle_object, account_batch_name
溯源统计: column=34, 无zh=15, lang=3 | fe_high=0, enum=1
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

PAY_ACCOUNT_AMOUNT_PAY_ACCOUNT_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_account.amount_pay_account_edit',
    system='fin',
    service='fin-service',
    name='操作',
    description='操作' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payAccount/amountPayAccountEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='number', default='0', description='下单客户名称'),  # zh_ambiguous
            DeclarationEntry(name='account_type', path=f'$.account_type', type='integer', state='form', ui_kind='number', default='0', description='0物流对账单  1对账单补件类型一， 对账单补件类型二'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', description='操作', enum=['check', 'submit']),
            DeclarationEntry(name='operate_type', path=f'$.operate_type', type='integer', state='form', ui_kind='number', default='0', description='操作类型 0费用维度 1提单维度'),
            DeclarationEntry(name='pay_account_id', path=f'$.pay_account_id', type='integer', state='form', ui_kind='number', default='0', description='应付对账'),
            DeclarationEntry(name='pay_account_no', path=f'$.pay_account_no', type='string', state='form', ui_kind='text', description='应付对账编号'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='form', ui_kind='text', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='number', default='0', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='select_list', path=f'$.select_list', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', ui_kind='number', default='0', description='应收结算对象ID'),  # zh_ambiguous
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', ui_kind='number', default='0', description='应付结算对象'),  # zh_ambiguous
            DeclarationEntry(name='pay_settle_object', path=f'$.pay_settle_object', type='string', state='form', ui_kind='text', description='应付结算对象'),  # zh_ambiguous
            DeclarationEntry(name='account_simple_name', path=f'$.account_simple_name', type='string', state='form', ui_kind='text', description='对账批次简称'),
            DeclarationEntry(name='cost_ids', path=f'$.cost_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='selection_time', path=f'$.selection_time', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='parent_id', path=f'$.parent_id', type='integer', state='carry', ui_kind='number', description='父级ID'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='relation_account_no', path=f'$.relation_account_no', type='string', state='carry', ui_kind='text', description='关联对账编号（应付/应收）'),
            DeclarationEntry(name='account_batch_name', path=f'$.account_batch_name', type='string', state='carry', ui_kind='text', description='对账批次名称'),  # needs_capture:value_source
            DeclarationEntry(name='customer_ids', path=f'$.customer_ids', type='string', state='carry', ui_kind='textarea'),
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='carry', ui_kind='text', description='下单客户'),
            DeclarationEntry(name='customer_num', path=f'$.customer_num', type='integer', state='carry', ui_kind='number', description='批次对应下单客户数量'),
            DeclarationEntry(name='customer_main_id', path=f'$.customer_main_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='customer_main_name', path=f'$.customer_main_name', type='string', state='carry', ui_kind='text', description='对客主体'),
            DeclarationEntry(name='customer_main_num', path=f'$.customer_main_num', type='integer', state='carry', ui_kind='number', description='对客主体数量'),
            DeclarationEntry(name='business_main_id', path=f'$.business_main_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='business_main_name', path=f'$.business_main_name', type='string', state='carry', ui_kind='textarea', description='对商主体'),
            DeclarationEntry(name='business_main_num', path=f'$.business_main_num', type='integer', state='carry', ui_kind='number', description='对商主体数量'),
            DeclarationEntry(name='book_supplier_id', path=f'$.book_supplier_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='book_supplier_ids', path=f'$.book_supplier_ids', type='string', state='carry', ui_kind='textarea'),
            DeclarationEntry(name='book_supplier_name', path=f'$.book_supplier_name', type='string', state='carry', ui_kind='text', description='订舱代理'),
            DeclarationEntry(name='book_supplier_num', path=f'$.book_supplier_num', type='integer', state='carry', ui_kind='number', description='订舱代理数量'),
            DeclarationEntry(name='pay_settle_object_num', path=f'$.pay_settle_object_num', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='put_settle_object', path=f'$.put_settle_object', type='string', state='carry', ui_kind='textarea', description='应收结算对象名称'),
            DeclarationEntry(name='put_settle_object_num', path=f'$.put_settle_object_num', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='batch_status', path=f'$.batch_status', type='string', state='carry', ui_kind='text', description='批次状态  1生效  2作废'),
            DeclarationEntry(name='account_status', path=f'$.account_status', type='string', state='carry', ui_kind='text', description='对账状态 1 对账中  2对账完成   3待核实  4已核实'),
            DeclarationEntry(name='account_num', path=f'$.account_num', type='integer', state='carry', ui_kind='number', description='对账轮数'),
            DeclarationEntry(name='account_cny', path=f'$.account_cny', type='number', state='carry', ui_kind='number', description='对账费用（CNY）'),
            DeclarationEntry(name='account_usd', path=f'$.account_usd', type='number', state='carry', ui_kind='number', description='对账费用（USD）'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='cancel_time', path=f'$.cancel_time', type='integer', state='carry', ui_kind='number', description='作废时间'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='etd', path=f'$.etd', type='string', state='carry', ui_kind='textarea', description='相关订单etd'),
            DeclarationEntry(name='atd', path=f'$.atd', type='string', state='carry', ui_kind='textarea', description='相关订单的atd'),
            DeclarationEntry(name='account_time', path=f'$.account_time', type='integer', state='carry', ui_kind='number', description='对账完成时间'),
            DeclarationEntry(name='account_by', path=f'$.account_by', type='integer', state='carry', ui_kind='number', description='对账完成用户ID'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='carry', ui_kind='text', description='币制'),
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='carry', ui_kind='textarea', description='关联提单号'),
            DeclarationEntry(name='cancel_remark', path=f'$.cancel_remark', type='string', state='carry', ui_kind='text', description='作废原因'),
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
