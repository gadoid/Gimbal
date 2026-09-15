"""fin.king_dee_log.voucher_log_export —— 孪生生成器产物(请求面;行为面归场景用例)。

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

KING_DEE_LOG_VOUCHER_LOG_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.king_dee_log.voucher_log_export',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/kingDeeLog/voucherLogExport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='voucher_batch_no', path=f'$.voucher_batch_no', type='string', state='form', description='凭证批次ID'),
            DeclarationEntry(name='operation', path=f'$.operation', type='string', state='form', description='业务操作'),
            DeclarationEntry(name='business_guest_id', path=f'$.business_guest_id', type='string', state='form'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', default='0', description='发起人ID'),
            DeclarationEntry(name='settle_object_id', path=f'$.settle_object_id', type='integer', state='form', default='0', description='超期应收结算对象'),
            DeclarationEntry(name='log_status', path=f'$.log_status', type='string', state='form', default='0', description='0 生成中  1 已生成  2生成失败'),
            DeclarationEntry(name='priority', path=f'$.priority', type='string', state='form', default='0', description='优先级  1优先'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', description='操作目的'),
            DeclarationEntry(name='generate_time_start', path=f'$.generate_time_start', type='string', state='form'),
            DeclarationEntry(name='generate_time_end', path=f'$.generate_time_end', type='string', state='form'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form'),
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
