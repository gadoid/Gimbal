"""fin.role.role_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

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

ROLE_ROLE_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.role.role_edit',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/role/roleEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='role_sort', path=f'$.role_sort', type='integer', state='form', required=True, default='1', description='显示顺序'),
            DeclarationEntry(name='dept_id', path=f'$.dept_id', type='integer', state='form', required=True, default='0', description='所属部门'),
            DeclarationEntry(name='role_key', path=f'$.role_key', type='string', state='form', required=True, description='角色权限字符串'),
            DeclarationEntry(name='role_name', path=f'$.role_name', type='string', state='form', required=True, description='角色名称'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='form', description='备注'),
            DeclarationEntry(name='operator', path=f'$.operator', type='string', state='form'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', default='submit', description='操作目的'),
            DeclarationEntry(name='menu_ids', path=f'$.menu_ids', type='string', state='form', description='菜单权限集合'),
            DeclarationEntry(name='role_id', path=f'$.role_id', type='integer', state='form', description='角色ID'),
            DeclarationEntry(name='menu_check_strictly', path=f'$.menu_check_strictly', type='string', state='form', default='1', description='菜单树选择项是否关联显示'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
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
