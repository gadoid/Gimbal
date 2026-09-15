"""fin.voucher.voucher_sync_export —— 孪生生成器产物(请求面;行为面归场景用例)。

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

VOUCHER_VOUCHER_SYNC_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.voucher.voucher_sync_export',
    system='fin',
    service='fin-service',
    name='Voucher.voucherSyncExport',
    description='Voucher.voucherSyncExport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/voucher/voucherSyncExport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='is_all', path=f'$.is_all', type='string', state='form'),
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
            DeclarationEntry(name='voucher_class', path=f'$.voucher_class', type='string', state='form', description='凭证二级分类'),
            DeclarationEntry(name='push_status', path=f'$.push_status', type='string', state='form', default='0', description='推送状态 0 未推送  1推送成功  2推送失败'),
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
