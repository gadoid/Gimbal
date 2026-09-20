"""fin.dept.dept_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): status
溯源统计: column=15, 无zh=3 | fe_high=1, enum=0
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
            DeclarationEntry(name='dept_name', path=f'$.dept_name', type='string', state='form', ui_kind='text', description='部门名称'),
            DeclarationEntry(name='order_num', path=f'$.order_num', type='integer', state='form', ui_kind='number', default='0', description='显示顺序'),
            DeclarationEntry(name='dept_id', path=f'$.dept_id', type='integer', state='form', ui_kind='number', default='0', description='所属部门'),
            DeclarationEntry(name='operator', path=f'$.operator', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='parent_id', path=f'$.parent_id', type='integer', state='form', ui_kind='number', default='0', description='父菜单ID'),
            DeclarationEntry(name='menu_ids', path=f'$.menu_ids', type='string', state='form', ui_kind='textarea', description='菜单权限集合'),
            DeclarationEntry(name='ancestors', path=f'$.ancestors', type='string', state='form', ui_kind='text', description='祖级列表'),
            DeclarationEntry(name='leader', path=f'$.leader', type='string', state='form', ui_kind='text', description='负责人'),
            DeclarationEntry(name='phone', path=f'$.phone', type='string', state='form', ui_kind='text', description='电话'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', ui_kind='number', default='0', description='状态 1未通知 2已通知'),  # zh_ambiguous
            DeclarationEntry(name='email', path=f'$.email', type='string', state='form', ui_kind='text', description='邮箱'),
            DeclarationEntry(name='is_super', path=f'$.is_super', type='integer', state='carry', ui_kind='number', description='超级部门   1  是  2否'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建者'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
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
