"""fin.menu.menu_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): status
溯源统计: column=20, 无zh=2 | fe_high=1, enum=0
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

MENU_MENU_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.menu.menu_edit',
    system='fin',
    service='fin-service',
    name='Menu.menuEdit',
    description='Menu.menuEdit' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/menu/menuEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='menu_name', path=f'$.menu_name', type='string', state='form', ui_kind='text', description='菜单名称'),
            DeclarationEntry(name='order_num', path=f'$.order_num', type='integer', state='form', ui_kind='number', default='0', description='显示顺序'),
            DeclarationEntry(name='menu_id', path=f'$.menu_id', type='integer', state='form', ui_kind='number', description='菜单ID'),
            DeclarationEntry(name='operator', path=f'$.operator', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='parent_id', path=f'$.parent_id', type='integer', state='form', ui_kind='number', default='0', description='父菜单ID'),
            DeclarationEntry(name='path', path=f'$.path', type='string', state='form', ui_kind='text', description='路由地址'),
            DeclarationEntry(name='component', path=f'$.component', type='string', state='form', ui_kind='text', description='组件路径'),
            DeclarationEntry(name='is_frame', path=f'$.is_frame', type='integer', state='form', ui_kind='number', default='1', description='是否为外链（0是 1否）'),
            DeclarationEntry(name='is_cache', path=f'$.is_cache', type='integer', state='form', ui_kind='number', default='0', description='是否缓存（0缓存 1不缓存）'),
            DeclarationEntry(name='menu_type', path=f'$.menu_type', type='string', state='form', ui_kind='text', description='菜单类型（M目录 C菜单 F按钮）'),
            DeclarationEntry(name='visible', path=f'$.visible', type='string', state='form', ui_kind='text', default='0', description='菜单状态（0显示 1隐藏）'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', ui_kind='number', default='0', description='状态 1未通知 2已通知'),  # zh_ambiguous
            DeclarationEntry(name='perms', path=f'$.perms', type='string', state='form', ui_kind='text', description='权限标识'),
            DeclarationEntry(name='icon', path=f'$.icon', type='string', state='form', ui_kind='text', default='#', description='菜单图标'),
            DeclarationEntry(name='apart_style', path=f'$.apart_style', type='integer', state='carry', ui_kind='number', description='隔离方式  0 无隔离  1主体  2人  3主体加人'),
            DeclarationEntry(name='is_default', path=f'$.is_default', type='integer', state='carry', ui_kind='number', description='是否是默认路由'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建者'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新者'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number', description='更新时间'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', ui_kind='text', description='备注'),
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
