"""fin.user.user_add —— 孪生生成器产物(请求面;行为面归场景用例)。

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

USER_USER_ADD: Final[EndpointSpec] = EndpointSpec(
    id='fin.user.user_add',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/user/userAdd',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='user_name', path=f'$.user_name', type='string', state='form', required=True, description='操作人员'),
            DeclarationEntry(name='name_en', path=f'$.name_en', type='string', state='form', description='英文名称'),
            DeclarationEntry(name='main_ids', path=f'$.main_ids', type='string', state='form', required=True, description='主体顺序ID'),
            DeclarationEntry(name='phone', path=f'$.phone', type='string', state='form', required=True, description='电话'),
            DeclarationEntry(name='role_ids', path=f'$.role_ids', type='string', state='form', required=True),
            DeclarationEntry(name='expire_start', path=f'$.expire_start', type='string', state='form', required=True, description='有效期开始时间'),
            DeclarationEntry(name='expire_end', path=f'$.expire_end', type='string', state='form', required=True, description='有效期结束时间'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='form', description='备注'),
            DeclarationEntry(name='operator', path=f'$.operator', type='string', state='form'),
            DeclarationEntry(name='operator_id', path=f'$.operator_id', type='integer', state='form', default='0', description='操作ID'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', default='submit', description='操作目的'),
            DeclarationEntry(name='user_id', path=f'$.user_id', type='integer', state='form', default='0', description='用户ID'),
            DeclarationEntry(name='password', path=f'$.password', type='string', state='form'),
            DeclarationEntry(name='email', path=f'$.email', type='string', state='form', description='用户邮箱'),
            DeclarationEntry(name='superior_ids', path=f'$.superior_ids', type='string', state='form'),
            DeclarationEntry(name='sex', path=f'$.sex', type='string', state='form', default='0', description='用户性别（0男 1女 2未知）'),
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
