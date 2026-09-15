"""fin.pay_account_email.email_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): receive_email, pay_account_email_order_ids
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

PAY_ACCOUNT_EMAIL_EMAIL_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_account_email.email_edit',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payAccountEmail/emailEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_account_email_id', path=f'$.pay_account_email_id', type='integer', state='form', required=True),
            DeclarationEntry(name='receive_email', path=f'$.receive_email', type='string', state='carry', description='收件人邮箱'),  # needs_capture:value_source
            DeclarationEntry(name='pay_account_email_order_ids', path=f'$.pay_account_email_order_ids', type='string', state='carry'),  # needs_capture:value_source
            DeclarationEntry(name='is_send', path=f'$.is_send', type='string', state='form', required=True, enum=['0', '1']),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', required=True, description='操作目的', enum=['check', 'submit']),
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
