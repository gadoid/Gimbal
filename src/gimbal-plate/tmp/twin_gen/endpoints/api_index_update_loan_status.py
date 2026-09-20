"""fin.index.update_loan_status —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): pay_account_no, account_batch_name, create_time, account_simple_name, customer_id, account_status, currency, receive_account_no, put_settle_object_id
溯源统计: frontend=17, 无zh=1 | fe_high=17, enum=0
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

INDEX_UPDATE_LOAN_STATUS: Final[EndpointSpec] = EndpointSpec(
    id='fin.index.update_loan_status',
    system='fin',
    service='fin-service',
    name='Index.updateLoanStatus',
    description='Index.updateLoanStatus' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/api/index/updateLoanStatus',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_account_no', path=f'$.pay_account_no', type='string', state='carry', ui_kind='text', description='对账批次ID'),  # needs_capture:value_source
            DeclarationEntry(name='account_batch_name', path=f'$.account_batch_name', type='string', state='carry', ui_kind='text', description='对账批次名称'),  # needs_capture:value_source
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='carry', ui_kind='text', description='提单号批量'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', description='创建时间'),  # zh_ambiguous
            DeclarationEntry(name='account_simple_name', path=f'$.account_simple_name', type='string', state='carry', ui_kind='text', description='对账批次简称'),  # needs_capture:value_source
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='text', default='0', description='下单客户名称'),  # zh_ambiguous
            DeclarationEntry(name='etd', path=f'$.etd', type='integer', state='form', ui_kind='text', default='0', description='预计开航（ETD）'),
            DeclarationEntry(name='atd', path=f'$.atd', type='integer', state='form', ui_kind='text', default='0', description='实际开航（ATD）'),
            DeclarationEntry(name='account_status', path=f'$.account_status', type='integer', state='carry', ui_kind='select', default='0', description='对账轮次状态'),  # zh_ambiguous
            DeclarationEntry(name='batch_identity', path=f'$.batch_identity', type='string', state='carry', ui_kind='select', description='批次身份'),
            DeclarationEntry(name='main_batch_no', path=f'$.main_batch_no', type='string', state='carry', ui_kind='text', description='对账主批次ID'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', ui_kind='select', description='币制'),  # zh_ambiguous
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='select', default='0', description='创建人'),
            DeclarationEntry(name='account_by', path=f'$.account_by', type='integer', state='carry', ui_kind='select', description='对账完成人'),
            DeclarationEntry(name='account_time', path=f'$.account_time', type='integer', state='carry', ui_kind='text', description='对账完成时间'),
            DeclarationEntry(name='receive_account_no', path=f'$.receive_account_no', type='string', state='carry', ui_kind='text', description='对账批次ID'),  # needs_capture:value_source
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', ui_kind='select', default='0', description='应收结算对象'),  # zh_ambiguous
            DeclarationEntry(name='data', path=f'$.data', type='string', state='form', ui_kind='text'),
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description='成功(信封统一;data 行形状归场景用例)',
            declarations=[
            DeclarationEntry(name='retCode', path='$.retCode', type='number',
                             required=False, ui_kind='number',
                             description='回调状态码(0=成功)', assertable=True),
            DeclarationEntry(name='retMsg', path='$.retMsg', type='string',
                             required=False, ui_kind='text',
                             description='回调提示信息', assertable=True),
            DeclarationEntry(name='data', path='$.data', type='object',
                             required=False, ui_kind='json',
                             description='业务数据(行形状归场景用例)', assertable=True),

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
