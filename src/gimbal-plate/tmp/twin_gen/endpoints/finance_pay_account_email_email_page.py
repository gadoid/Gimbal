"""fin.pay_account_email.email_page —— 孪生生成器产物(请求面;行为面归场景用例)。

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

PAY_ACCOUNT_EMAIL_EMAIL_PAGE: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_account_email.email_page',
    system='fin',
    service='fin-service',
    name='PayAccountEmail.emailPage',
    description='PayAccountEmail.emailPage' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payAccountEmail/emailPage',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='page_no', path=f'$.page_no', type='string', state='form'),
            DeclarationEntry(name='page_size', path=f'$.page_size', type='string', state='form'),
            DeclarationEntry(name='supplier_id', path=f'$.supplier_id', type='integer', state='form', default='0', description='变更账期供应商ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
            DeclarationEntry(name='pay_month', path=f'$.pay_month', type='integer', state='form', default='0', description='应付月份'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
            DeclarationEntry(name='send_id', path=f'$.send_id', type='integer', state='form', default='0', description='消息发送人ID'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form'),
            DeclarationEntry(name='send_time_start', path=f'$.send_time_start', type='string', state='form'),
            DeclarationEntry(name='send_time_end', path=f'$.send_time_end', type='string', state='form'),
            DeclarationEntry(name='atd_month', path=f'$.atd_month', type='string', state='form', description='订单ATD月份'),
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
