"""fin.role.role_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): status, role_no
溯源统计: column=14, 无zh=5, lang=1 | fe_high=0, enum=1
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
            DeclarationEntry(name='role_sort', path=f'$.role_sort', type='integer', state='form', ui_kind='number', default='1', description='显示顺序'),
            DeclarationEntry(name='dept_id', path=f'$.dept_id', type='integer', state='form', ui_kind='number', default='0', description='所属部门'),
            DeclarationEntry(name='role_key', path=f'$.role_key', type='string', state='form', ui_kind='text', description='角色权限字符串'),
            DeclarationEntry(name='role_name', path=f'$.role_name', type='string', state='form', ui_kind='text', description='角色名称'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='form', ui_kind='text', description='备注'),
            DeclarationEntry(name='operator', path=f'$.operator', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='submit', description='操作目的', enum=['check', 'submit']),
            DeclarationEntry(name='menu_ids', path=f'$.menu_ids', type='string', state='form', ui_kind='textarea', description='菜单权限集合'),
            DeclarationEntry(name='role_id', path=f'$.role_id', type='integer', state='form', ui_kind='number', description='角色ID'),
            DeclarationEntry(name='menu_check_strictly', path=f'$.menu_check_strictly', type='string', state='form', ui_kind='text', default='1', description='菜单树选择项是否关联显示'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', ui_kind='number', default='0', description='状态 1未通知 2已通知'),  # zh_ambiguous
            DeclarationEntry(name='role_no', path=f'$.role_no', type='string', state='carry', ui_kind='text', description='角色编号'),  # needs_capture:value_source
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建者'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新者'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number', description='更新时间'),
            DeclarationEntry(name='delete_time', path=f'$.delete_time', type='integer', state='carry', ui_kind='number'),
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
