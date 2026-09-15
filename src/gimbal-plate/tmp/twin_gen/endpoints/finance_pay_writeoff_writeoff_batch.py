"""fin.pay_writeoff.writeoff_batch —— 孪生生成器产物(请求面;行为面归场景用例)。

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

PAY_WRITEOFF_WRITEOFF_BATCH: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_writeoff.writeoff_batch',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payWriteoff/writeoffBatch',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='writeoff_object', path=f'$.writeoff_object', type='string', state='form', required=True, description='核销对象'),
            DeclarationEntry(name='un_writeoff_amount_cny_total', path=f'$.un_writeoff_amount_cny_total', type='number', state='form', required=True, default='0.00', description='未核销金额总计CNY'),
            DeclarationEntry(name='un_writeoff_amount_usd_total', path=f'$.un_writeoff_amount_usd_total', type='number', state='form', required=True, default='0.00', description='未核销金额总计USD'),
            DeclarationEntry(name='use_writeoff_amount_cny_total', path=f'$.use_writeoff_amount_cny_total', type='number', state='form', required=True, default='0.00', description='已核销金额总计CNY'),
            DeclarationEntry(name='use_writeoff_amount_usd_total', path=f'$.use_writeoff_amount_usd_total', type='number', state='form', required=True, default='0.00', description='已核销金额总计USD'),
            DeclarationEntry(name='statement_amount_cny_total', path=f'$.statement_amount_cny_total', type='number', state='form', required=True, default='0.00', description='流水金额总计CNY'),
            DeclarationEntry(name='statement_amount_usd_total', path=f'$.statement_amount_usd_total', type='number', state='form', required=True, default='0.00', description='流水金额总计USD'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', description='操作目的'),
            DeclarationEntry(name='fee_match_type', path=f'$.fee_match_type', type='integer', state='form', default='0', description='匹配费用方式 1系统自动对应 2手动选择对应'),
            DeclarationEntry(name='statement', path=f'$.statement', type='string', state='form'),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', description='审批人备注'),
            DeclarationEntry(name='writeoff_name', path=f'$.writeoff_name', type='string', state='form', description='应收核销记录名称'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', default='0', description='费用主体ID'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='form', description='费用主体名称'),
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='form', description='审批回显信息'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', default='0', description='业务订单ID'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', default='0', description='服务策略ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
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
