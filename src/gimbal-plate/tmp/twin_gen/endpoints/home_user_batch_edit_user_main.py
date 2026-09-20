"""fin.user.batch_edit_user_main —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): main_id, user_no, nick_name
溯源统计: column=25, 无zh=5 | fe_high=0, enum=1
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

USER_BATCH_EDIT_USER_MAIN: Final[EndpointSpec] = EndpointSpec(
    id='fin.user.batch_edit_user_main',
    system='fin',
    service='fin-service',
    name='User.batchEditUserMain',
    description='User.batchEditUserMain' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/user/batchEditUserMain',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='user_id', path=f'$.user_id', type='integer', state='form', ui_kind='number', required=True, default='0', description='用户ID'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='number', required=True, default='0', description='费用主体ID'),  # zh_ambiguous
            DeclarationEntry(name='change_type', path=f'$.change_type', type='integer', state='form', ui_kind='select', required=True, description='订单变更类型 1变更服务政策 2变更服务策略', enum=['add', 'del']),
            DeclarationEntry(name='user_name', path=f'$.user_name', type='string', state='carry', ui_kind='text', description='用户账号'),
            DeclarationEntry(name='user_no', path=f'$.user_no', type='string', state='carry', ui_kind='text', description='用户编号'),  # needs_capture:value_source
            DeclarationEntry(name='nick_name', path=f'$.nick_name', type='string', state='carry', ui_kind='text', description='用户昵称'),  # needs_capture:value_source
            DeclarationEntry(name='name_en', path=f'$.name_en', type='string', state='carry', ui_kind='text', description='英文名称'),
            DeclarationEntry(name='user_type', path=f'$.user_type', type='string', state='carry', ui_kind='text', description='用户类型（00系统用户）'),
            DeclarationEntry(name='email', path=f'$.email', type='string', state='carry', ui_kind='text', description='用户邮箱'),
            DeclarationEntry(name='phone', path=f'$.phone', type='string', state='carry', ui_kind='text', description='手机号码'),
            DeclarationEntry(name='sex', path=f'$.sex', type='string', state='carry', ui_kind='text', description='用户性别（0男 1女 2未知）'),
            DeclarationEntry(name='avatar', path=f'$.avatar', type='string', state='carry', ui_kind='text', description='头像地址'),
            DeclarationEntry(name='password', path=f'$.password', type='string', state='carry', ui_kind='text', description='可逆密码'),
            DeclarationEntry(name='password_value', path=f'$.password_value', type='string', state='carry', ui_kind='text', description='密码'),
            DeclarationEntry(name='expire_start', path=f'$.expire_start', type='string', state='carry', ui_kind='text', description='有效期开始时间'),
            DeclarationEntry(name='expire_end', path=f'$.expire_end', type='string', state='carry', ui_kind='text', description='有效期结束时间'),
            DeclarationEntry(name='is_super', path=f'$.is_super', type='integer', state='carry', ui_kind='number', description='是否是超管  1 是  2否'),
            DeclarationEntry(name='status', path=f'$.status', type='string', state='carry', ui_kind='text', description='帐号状态（2正常 1停用）'),
            DeclarationEntry(name='login_ip', path=f'$.login_ip', type='string', state='carry', ui_kind='text', description='最后登录IP'),
            DeclarationEntry(name='login_date', path=f'$.login_date', type='integer', state='carry', ui_kind='number', description='最后登录时间'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建者'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新者'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number', description='更新时间'),
            DeclarationEntry(name='delete_time', path=f'$.delete_time', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', ui_kind='text', description='备注'),
            DeclarationEntry(name='king_dee_id', path=f'$.king_dee_id', type='integer', state='carry', ui_kind='number'),
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
