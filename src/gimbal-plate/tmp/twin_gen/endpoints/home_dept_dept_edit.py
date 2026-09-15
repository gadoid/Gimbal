"""fin.dept.dept_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

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

DEPT_DEPT_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.dept.dept_edit',
    system='fin',
    service='fin-service',
    name='Dept.deptEdit',
    description='Dept.deptEdit' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/dept/deptEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='dept_name', path=f'$.dept_name', type='string', state='form', required=True, description='部门名称'),
            DeclarationEntry(name='order_num', path=f'$.order_num', type='integer', state='form', required=True, default='0', description='显示顺序'),
            DeclarationEntry(name='operator', path=f'$.operator', type='string', state='form'),
            DeclarationEntry(name='parent_id', path=f'$.parent_id', type='integer', state='form', default='0', description='父菜单ID'),
            DeclarationEntry(name='dept_id', path=f'$.dept_id', type='integer', state='form', default='0', description='所属部门'),
            DeclarationEntry(name='menu_ids', path=f'$.menu_ids', type='string', state='form', description='菜单权限集合'),
            DeclarationEntry(name='ancestors', path=f'$.ancestors', type='string', state='form', description='祖级列表'),
            DeclarationEntry(name='leader', path=f'$.leader', type='string', state='form', description='负责人'),
            DeclarationEntry(name='phone', path=f'$.phone', type='string', state='form', description='电话'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
            DeclarationEntry(name='email', path=f'$.email', type='string', state='form', description='用户邮箱'),
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
