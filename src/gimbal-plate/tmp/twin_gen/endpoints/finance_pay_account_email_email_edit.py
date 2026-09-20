"""fin.pay_account_email.email_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): receive_email, pay_account_email_order_ids, pay_account_email_no, atd_month, cc_email, send_by, send_fail_desc
溯源统计: column=19, 无zh=7, lang=4 | fe_high=0, enum=2
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
    name='操作',
    description='操作' + ' [generated:fin-test@2026-09-15]',
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
            DeclarationEntry(name='pay_account_email_id', path=f'$.pay_account_email_id', type='integer', state='form', ui_kind='number', description='催对账邮件ID'),
            DeclarationEntry(name='receive_email', path=f'$.receive_email', type='string', state='carry', ui_kind='text', description='收件人邮箱'),  # needs_capture:value_source
            DeclarationEntry(name='pay_account_email_order_ids', path=f'$.pay_account_email_order_ids', type='string', state='carry', ui_kind='text', description='关联提单ID'),  # needs_capture:value_source
            DeclarationEntry(name='is_send', path=f'$.is_send', type='string', state='form', ui_kind='select', description='是否发送', enum=['0', '1']),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', description='操作', enum=['check', 'submit']),
            DeclarationEntry(name='pay_account_email_no', path=f'$.pay_account_email_no', type='string', state='carry', ui_kind='text', description='邮件编号'),  # needs_capture:value_source
            DeclarationEntry(name='supplier_id', path=f'$.supplier_id', type='integer', state='carry', ui_kind='number', description='供应商ID'),
            DeclarationEntry(name='supplier_name', path=f'$.supplier_name', type='string', state='carry', ui_kind='text', description='供应商名称'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='carry', ui_kind='number', description='下单客户ID'),
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='carry', ui_kind='text', description='下单客户名称'),
            DeclarationEntry(name='pay_month', path=f'$.pay_month', type='integer', state='carry', ui_kind='number', description='应付月份'),
            DeclarationEntry(name='atd_month', path=f'$.atd_month', type='string', state='carry', ui_kind='text', description='订单ATD月份'),  # needs_capture:value_source
            DeclarationEntry(name='order_count', path=f'$.order_count', type='integer', state='carry', ui_kind='number', description='关联订单数'),
            DeclarationEntry(name='cc_email', path=f'$.cc_email', type='string', state='carry', ui_kind='text', description='收件方抄送邮箱'),  # needs_capture:value_source
            DeclarationEntry(name='is_email_manual', path=f'$.is_email_manual', type='integer', state='carry', ui_kind='number', description='邮箱是否手动编辑：0否 1是'),
            DeclarationEntry(name='file_name', path=f'$.file_name', type='string', state='carry', ui_kind='text', description='附件地址'),
            DeclarationEntry(name='original_name', path=f'$.original_name', type='string', state='carry', ui_kind='text', description='附件原始名称'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='carry', ui_kind='number', description='发送状态：0生成中 1待发送 2发送成功 3异常 4发送失败'),
            DeclarationEntry(name='send_id', path=f'$.send_id', type='integer', state='carry', ui_kind='number', description='发送人ID'),
            DeclarationEntry(name='send_by', path=f'$.send_by', type='string', state='carry', ui_kind='text', description='发送人'),  # needs_capture:value_source
            DeclarationEntry(name='send_time', path=f'$.send_time', type='string', state='carry', ui_kind='text', description='发送时间'),
            DeclarationEntry(name='send_fail_desc', path=f'$.send_fail_desc', type='string', state='carry', ui_kind='text', description='发送失败原因'),  # needs_capture:value_source
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='customer_service_email', path=f'$.customer_service_email', type='string', state='carry', ui_kind='text', description='客服邮箱'),
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
