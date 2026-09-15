"""fin.receive_writeoff.writeoff_page —— 孪生生成器产物(请求面;行为面归场景用例)。

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

RECEIVE_WRITEOFF_WRITEOFF_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_writeoff.writeoff_page',
    system='fin',
    service='fin-service',
    name='ReceiveWriteoff.writeoffPage',
    description='ReceiveWriteoff.writeoffPage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveWriteoff/writeoffPage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', default='0', description='业务ID'),
            DeclarationEntry(name='receive_writeoff_id', path=f'$.receive_writeoff_id', type='string', state='form', description='核销ID集合'),
            DeclarationEntry(name='check_ids', path=f'$.check_ids', type='string', state='form'),
            DeclarationEntry(name='writeoff_no', path=f'$.writeoff_no', type='string', state='form', description='应收核销记录编号'),
            DeclarationEntry(name='writeoff_name', path=f'$.writeoff_name', type='string', state='form', description='应收核销记录名称'),
            DeclarationEntry(name='fee_match_type', path=f'$.fee_match_type', type='integer', state='form', default='0', description='匹配费用方式 1系统自动对应 2手动选择对应'),
            DeclarationEntry(name='writeoff_type', path=f'$.writeoff_type', type='integer', state='form', default='0', description='核销类型 1正常核销 2强制核销'),
            DeclarationEntry(name='receive_settle_object_id', path=f'$.receive_settle_object_id', type='integer', state='form', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='form', default='1', description='核销状态 1未核销 2已核销 3部分核销'),
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='form', default='1', description='审批状态 1待处理 2通过 3驳回 4撤销'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', description='币值'),
            DeclarationEntry(name='writeoff_user_id', path=f'$.writeoff_user_id', type='integer', state='form', default='0', description='核销人ID'),
            DeclarationEntry(name='writeoff_time_start', path=f'$.writeoff_time_start', type='string', state='form'),
            DeclarationEntry(name='writeoff_time_end', path=f'$.writeoff_time_end', type='string', state='form'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', default='0', description='费用主体ID'),
            DeclarationEntry(name='statement_receipt_account', path=f'$.statement_receipt_account', type='string', state='form', description='流水银行账号'),
            DeclarationEntry(name='conn_invoice_no', path=f'$.conn_invoice_no', type='string', state='form', description='关联发票号'),
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='form', description='关联提单号'),
            DeclarationEntry(name='statement_currency', path=f'$.statement_currency', type='string', state='form', description='流水币制'),
            DeclarationEntry(name='is_relate_writeoff', path=f'$.is_relate_writeoff', type='string', state='form'),
            DeclarationEntry(name='pay_writeoff_no', path=f'$.pay_writeoff_no', type='string', state='form', description='应付核销记录编号'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', default='0', description='发起人ID'),
            DeclarationEntry(name='receipt_time_start', path=f'$.receipt_time_start', type='string', state='form'),
            DeclarationEntry(name='receipt_time_end', path=f'$.receipt_time_end', type='string', state='form'),
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
