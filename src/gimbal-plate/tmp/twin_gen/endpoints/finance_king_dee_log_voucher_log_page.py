"""fin.king_dee_log.voucher_log_page —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): create_id, create_time, settle_object_id, sort_field, sort_order
溯源统计: frontend=9, builtin=4, derived=4, 无zh=1 | fe_high=9, enum=2
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

KING_DEE_LOG_VOUCHER_LOG_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.king_dee_log.voucher_log_page',
    system='fin',
    service='fin-service',
    name='生成凭证类型',
    description='生成凭证类型' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/kingDeeLog/voucherLogPage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='voucher_batch_no', path=f'$.voucher_batch_no', type='string', state='form', ui_kind='text', description='凭证批次ID'),
            DeclarationEntry(name='operation', path=f'$.operation', type='string', state='form', ui_kind='select', description='业务操作'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', description='生成凭证类型', enum=['check', 'submit']),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', ui_kind='select', default='0', description='操作人'),  # zh_ambiguous
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='业务操作时间'),  # zh_ambiguous
            DeclarationEntry(name='settle_object_id', path=f'$.settle_object_id', type='integer', state='form', ui_kind='select', default='0', description='关联客商名称'),  # zh_ambiguous
            DeclarationEntry(name='log_status', path=f'$.log_status', type='string', state='form', ui_kind='select', default='0', description='凭证生成状态'),
            DeclarationEntry(name='priority', path=f'$.priority', type='string', state='form', ui_kind='select', default='0', description='生成进度'),
            DeclarationEntry(name='generate_time', path=f'$.generate_time', type='integer', state='carry', ui_kind='text', description='凭证生成时间'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form', ui_kind='text', required=True, description='页码'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form', ui_kind='text', required=True, description='每页条数'),
            DeclarationEntry(name='business_guest_id', path=f'$.business_guest_id', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='generate_time_start', path=f'$.generate_time_start', type='string', state='form', ui_kind='text', description='凭证生成时间开始'),
            DeclarationEntry(name='generate_time_end', path=f'$.generate_time_end', type='string', state='form', ui_kind='text', description='凭证生成时间结束'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form', ui_kind='text', description='业务操作时间开始'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form', ui_kind='text', description='业务操作时间结束'),
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
